import math
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.builder import build_graph
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.connection import Connection

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/route")
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Получен запрос на построение маршрута от {start} до {end}")

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

    # Загружаем соединения и комнаты
    connections = db.query(Connection).all()
    stair_connections = {(conn.from_segment_id, conn.to_segment_id): conn for conn in connections if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id}
    rooms = {f"room_{room.id}": room for room in db.query(Room).all()}

    try:
        # Фильтрация пути с учётом допустимого смещения (5 единиц)
        filtered_points = []
        for i, vertex in enumerate(path):
            vertex_data = graph.get_vertex_data(vertex)
            if not vertex_data or "coords" not in vertex_data:
                logger.error(f"Отсутствуют данные для вершины {vertex}")
                raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")
            x, y, floor = vertex_data["coords"]
            if not filtered_points or all(
                abs(x - fp["x"]) > 5 or abs(y - fp["y"]) > 5
                for fp in filtered_points
            ):
                filtered_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

        # Обработка отфильтрованного пути
        for i, point in enumerate(filtered_points):
            vertex = point["vertex"]
            x, y, floor = point["x"], point["y"], point["floor"]

            if vertex not in seen_vertices:
                if floor != current_floor:
                    if floor_points:
                        result.append({"floor": current_floor, "points": floor_points})
                    floor_points = []
                    current_floor = floor
                floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})
                seen_vertices.add(vertex)

            if i < len(filtered_points) - 1:
                next_point = filtered_points[i + 1]
                next_vertex = next_point["vertex"]
                edge_data = graph.get_edge_data(vertex, next_vertex)
                if edge_data.get("type") == "лестница":
                    prev_floor = filtered_points[i - 1]["floor"] if i > 0 else floor
                    direction = "вверх" if floor > prev_floor else "вниз"

                    if "stair" in vertex:
                        parts = vertex.split("_")
                        if len(parts) >= 4:
                            from_seg = int(parts[2])
                            to_seg = int(parts[4])
                            conn = stair_connections.get((from_seg, to_seg))
                            if conn and conn.from_floor_id and conn.to_floor_id:
                                stair_end_vertex = f"stair_end_{from_seg}_to_{to_seg}"
                                stair_end_coords = (x, y, conn.from_floor_id)

                                if "to" in vertex:
                                    if floor_points[-1]["floor"] != conn.from_floor_id:
                                        result.append({"floor": current_floor, "points": floor_points})
                                        floor_points = []
                                        current_floor = conn.from_floor_id
                                    if stair_end_vertex not in seen_vertices:
                                        floor_points.append({"x": x, "y": y, "vertex": stair_end_vertex, "floor": conn.from_floor_id})
                                        seen_vertices.add(stair_end_vertex)
                                elif "from" in vertex:
                                    if floor_points[-1]["floor"] != conn.to_floor_id:
                                        result.append({"floor": current_floor, "points": floor_points})
                                        floor_points = []
                                        current_floor = conn.to_floor_id
                                    if stair_end_vertex not in seen_vertices:
                                        floor_points.append({"x": x, "y": y, "vertex": stair_end_vertex, "floor": conn.to_floor_id})
                                        seen_vertices.add(stair_end_vertex)

                    if not any("лестнице" in instr.lower() for instr in instructions[-2:]):
                        instructions.append(f"Спуститесь по лестнице с {prev_floor}-го на {floor}-й этаж" if direction == "вниз" else f"Поднимитесь по лестнице с {prev_floor}-го на {floor}-й этаж")

                elif edge_data.get("type") == "дверь":
                    if "outdoor" in next_vertex and not any("выйдите" in instr.lower() for instr in instructions[-2:]):
                        instructions.append("Выйдите из здания через дверь")
                    elif "outdoor" in vertex and not any("войдите" in instr.lower() for instr in instructions[-2:]):
                        instructions.append("Войдите в здание через дверь")

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        # Генерация направлений на основе координат
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
                        direction = "Идите прямо"
                    elif 45 < turn_angle <= 135:
                        direction = "Поверните налево"
                    elif -135 <= turn_angle < -45:
                        direction = "Поверните направо"
                    else:
                        direction = "Развернитесь"
                else:
                    room = rooms.get(start) if j == 0 else rooms.get(end) if j == len(floor_points) - 2 else None
                    direction = f"Начните движение из {room.name} {room.cab_id} кабинет" if room else "Начните движение"

                directions.append(direction)

        # Формирование итоговых инструкций
        final_instructions = []
        instr_idx = 0
        dir_idx = 0
        while instr_idx < len(instructions) or dir_idx < len(directions):
            if instr_idx < len(instructions):
                final_instructions.append(instructions[instr_idx])
                instr_idx += 1
            if dir_idx < len(directions) and (instr_idx >= len(instructions) or "лестнице" not in instructions[instr_idx - 1].lower() and "дверь" not in instructions[instr_idx - 1].lower()):
                final_instructions.append(directions[dir_idx])
                dir_idx += 1

        # Добавляем пункт прибытия
        if end in rooms:
            final_instructions.append(f"Вы прибыли в {rooms[end].name} {rooms[end].cab_id} кабинет")

        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")