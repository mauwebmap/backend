import math
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.builder import build_graph
from app.map.utils.pathfinder import find_path
from app.map.models.connection import Connection
from app.map.models.room import Room  # Предполагается, что модель Room определена для таблицы rooms

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/route")
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Получен запрос на построение маршрута от {start} до {end}")

    # Получение названий кабинетов из таблицы rooms
    try:
        start_room = db.query(Room).filter(Room.cab_id == start).first()
        end_room = db.query(Room).filter(Room.cab_id == end).first()
        start_name = start_room.name if start_room else f"точки {start}"
        end_name = end_room.name if end_room else f"точки {end}"
    except Exception as e:
        logger.error(f"Ошибка при получении названий кабинетов: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при получении данных о кабинетах")

    # Построение графа
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Граф успешно построен: {len(graph.vertices)} вершин")
    except Exception as e:
        logger.error(f"Ошибка при построении графа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при построении графа: {str(e)}")

    # Поиск пути
    try:
        path, weight = find_path(graph, start, end)
        logger.info(f"Поиск пути завершён: путь={path}, вес={weight}")
    except Exception as e:
        logger.error(f"Ошибка при поиске пути: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {str(e)}")

    if not path:
        logger.info(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    # Формирование маршрута
    result = []
    current_floor = None
    floor_points = []
    instructions = []
    seen_vertices = set()

    # Загружаем соединения из базы данных
    connections = db.query(Connection).all()
    stair_connections = {}
    for conn in connections:
        if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            stair_connections[(conn.from_segment_id, conn.to_segment_id)] = conn

    try:
        # Начальная инструкция с названием кабинета
        instructions.append(f"Начните движение из {start_name}")

        for i, vertex in enumerate(path):
            vertex_data = graph.get_vertex_data(vertex)
            if not vertex_data or "coords" not in vertex_data:
                logger.error(f"Отсутствуют данные для вершины {vertex}")
                raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")

            floor = vertex_data["coords"][2] if vertex_data["coords"][2] is not None else 1
            x, y = vertex_data["coords"][0], vertex_data["coords"][1]

            # Добавляем точку, только если её ещё не добавляли
            if vertex not in seen_vertices:
                if floor != current_floor:
                    if floor_points:
                        result.append({"floor": current_floor, "points": floor_points})
                    floor_points = []
                    current_floor = floor
                floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})
                seen_vertices.add(vertex)

            # Генерация инструкций для лестниц и дверей
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                edge_data = graph.get_edge_data(vertex, next_vertex)
                if edge_data.get("type") == "лестница":
                    prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                    direction = "поднимитесь" if floor > prev_floor else "спуститесь"

                    # Извлекаем from_segment_id и to_segment_id из вершины
                    if "stair" in vertex:
                        parts = vertex.split("_")
                        if len(parts) >= 4:
                            from_seg = int(parts[2])
                            to_seg = int(parts[4])
                            conn = stair_connections.get((from_seg, to_seg))
                            if conn and conn.from_floor_id is not None and conn.to_floor_id is not None:
                                # Разделяем лестницу на две части
                                if "to" in vertex:  # Это phantom_stair_from_seg_to_seg
                                    if floor_points and floor_points[-1]["floor"] != conn.from_floor_id:
                                        result.append({"floor": current_floor, "points": floor_points})
                                        floor_points = []
                                        current_floor = conn.from_floor_id
                                    floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": conn.from_floor_id})
                                elif "from" in vertex:  # Это phantom_stair_to_seg_from_seg
                                    if floor_points and floor_points[-1]["floor"] != conn.to_floor_id:
                                        result.append({"floor": current_floor, "points": floor_points})
                                        floor_points = []
                                        current_floor = conn.to_floor_id
                                    floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": conn.to_floor_id})

                    if not any("лестнице" in instr for instr in instructions[-2:]):  # Избегаем дублирования
                        instructions.append(f"{direction.title()} по лестнице с {prev_floor}-го на {floor}-й этаж")
                elif edge_data.get("type") == "дверь":
                    if "outdoor" in next_vertex and not any("выйдите" in instr for instr in instructions[-2:]):
                        instructions.append("Выйдите из здания через дверь")
                    elif "outdoor" in vertex and not any("войдите" in instr for instr in instructions[-2:]):
                        instructions.append("Войдите в здание через дверь")

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        # Генерация направлений
        directions = []
        for floor_data in result:
            floor_points = floor_data["points"]
            for j in range(len(floor_points) - 1):
                current = floor_points[j]
                next_point = floor_points[j + 1]
                prev_point = floor_points[j - 1] if j > 0 else None

                dx = next_point["x"] - current["x"]
                dy = next_point["y"] - current["y"]
                angle = math.degrees(math.atan2(dy, dx))

                if prev_point:
                    prev_dx = current["x"] - prev_point["x"]
                    prev_dy = current["y"] - prev_point["y"]
                    prev_angle = math.degrees(math.atan2(prev_dy, prev_dx))
                    turn_angle = (angle - prev_angle + 180) % 360 - 180
                    if -45 <= turn_angle <= 45:
                        direction = "идите прямо"
                    elif 45 < turn_angle <= 135:
                        direction = "поверните налево"
                    elif -135 <= turn_angle < -45:
                        direction = "поверните направо"
                    else:
                        direction = "развернитесь"
                else:
                    direction = "начните движение"

                directions.append(direction)

        # Добавляем направления в инструкции
        direction_idx = 0
        final_instructions = []
        for instr in instructions:
            final_instructions.append(instr)
            if "лестнице" not in instr and "здания" not in instr and direction_idx < len(directions):
                final_instructions.append(f"{directions[direction_idx].title()}")
                direction_idx += 1
        while direction_idx < len(directions):
            final_instructions.append(directions[direction_idx].title())
            direction_idx += 1

        # Завершающая инструкция с указанием конечного кабинета
        final_instructions.append(f"Вы прибыли в {end_name}")

        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")