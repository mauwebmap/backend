import math
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.builder import build_graph
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/route")
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Получен запрос на построение маршрута от {start} до {end}")

    # Извлечение ID комнат из start и end
    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
    except ValueError as e:
        logger.error(f"Неверный формат start или end: {start}, {end}")
        raise HTTPException(status_code=400, detail=f"Неверный формат start или end: {start}, {end}")

    # Получение данных о комнатах из базы
    start_room = db.query(Room).filter(Room.id == start_id).first()
    end_room = db.query(Room).filter(Room.id == end_id).first()
    if not start_room or not end_room:
        logger.error(f"Комната с id {start_id} или {end_id} не найдена")
        raise HTTPException(status_code=404, detail=f"Комната с id {start_id} или {end_id} не найдена")

    # Формирование названий кабинетов
    start_room_name = f"{start_room.name} {start_room.cab_id} кабинет"
    end_room_name = f"{end_room.name} {end_room.cab_id} кабинет"

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
    last_action = None  # Для отслеживания последней инструкции
    last_stair_start = None  # Для отслеживания начала лестницы

    try:
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

            # Генерация инструкций для лестниц и переходов
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                edge_data = graph.get_edge_data(vertex, next_vertex)

                # Инструкции для лестниц
                if edge_data.get("type") == "лестница":
                    prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                    if floor != prev_floor:  # Смена этажа
                        direction = "вверх" if floor > prev_floor else "вниз"
                        if "to" in vertex or "from_far" in vertex:  # Начало лестницы (на этаже отправления)
                            if last_stair_start is None:
                                instruction = f"Начните {direction} по лестнице с {prev_floor} этажа на {floor} этаж"
                                if last_action != "stairs_start" or instructions[-1] != instruction:
                                    instructions.append(instruction)
                                    last_action = "stairs_start"
                                    last_stair_start = vertex
                        elif "from" in vertex or "to_far" in vertex:  # Конец лестницы (на этаже назначения)
                            if last_stair_start:
                                instruction = f"Завершите {direction} по лестнице на {floor} этаж"
                                if last_action != "stairs_end" or instructions[-1] != instruction:
                                    instructions.append(instruction)
                                    last_action = "stairs_end"
                                    last_stair_start = None

                # Инструкции для выхода из здания
                elif edge_data.get("type") == "дверь":
                    if "outdoor" in next_vertex and last_action != "exit":
                        next_vertex_data = graph.get_vertex_data(next_vertex)
                        dx = next_vertex_data["coords"][0] - x
                        dy = next_vertex_data["coords"][1] - y
                        angle = math.degrees(math.atan2(dy, dx))
                        if -45 <= angle <= 45:
                            direction = "вправо"
                        elif 45 < angle <= 135:
                            direction = "прямо"
                        elif 135 < angle <= 225:
                            direction = "налево"
                        else:
                            direction = "прямо"
                        instructions.append(f"Выйдите из здания и поверните {direction}")
                        last_action = "exit"
                    elif "outdoor" in vertex and last_action != "enter":
                        next_vertex_data = graph.get_vertex_data(next_vertex)
                        dx = next_vertex_data["coords"][0] - x
                        dy = next_vertex_data["coords"][1] - y
                        angle = math.degrees(math.atan2(dy, dx))
                        if -45 <= angle <= 45:
                            direction = "вправо"
                        elif 45 < angle <= 135:
                            direction = "прямо"
                        elif 135 < angle <= 225:
                            direction = "налево"
                        else:
                            direction = "прямо"
                        instructions.append(f"Поверните {direction} и зайдите в здание")
                        last_action = "enter"

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        # Генерация направлений внутри здания или на улице
        directions = []
        last_direction = None  # Для исключения дублирований
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
                        direction = "пройдите вперед"
                    elif 45 < turn_angle <= 135:
                        direction = "поверните налево"
                    elif -135 <= turn_angle < -45:
                        direction = "поверните направо"
                    else:
                        direction = "развернитесь"

                    # Пропускаем дублирующиеся направления
                    if last_direction == direction:
                        continue

                    # Добавляем "На перекрестке" только при смене типа вершины
                    if j > 0 and ("outdoor" in current["vertex"] != "outdoor" in prev_point["vertex"]):
                        direction = f"На перекрестке {direction.lower()}"
                    else:
                        direction = direction.capitalize()

                    directions.append(direction)
                    last_direction = direction

        # Формирование финальных инструкций
        final_instructions = [f"Выйдите из {start_room_name} на {current_floor} этаже"]
        direction_idx = 0

        # Комбинируем инструкции и направления
        for instr in instructions:
            final_instructions.append(instr)
            if "этаж" not in instr and "здание" not in instr and direction_idx < len(directions):
                final_instructions.append(directions[direction_idx])
                direction_idx += 1
        while direction_idx < len(directions):
            final_instructions.append(directions[direction_idx])
            direction_idx += 1

        final_instructions.append(f"Вы прибыли в {end_room_name} на {current_floor} этаже")

        # Логирование и отправка маршрута
        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")