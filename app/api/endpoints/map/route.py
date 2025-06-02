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
    seen_vertices = set()

    try:
        for i, vertex in enumerate(path):
            vertex_data = graph.get_vertex_data(vertex)
            if not vertex_data or "coords" not in vertex_data:
                logger.error(f"Отсутствуют данные для вершины {vertex}")
                raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")

            floor = vertex_data["coords"][2] if vertex_data["coords"][2] is not None else 1
            x, y = vertex_data["coords"][0], vertex_data["coords"][1]

            if vertex not in seen_vertices:
                if floor != current_floor:
                    if floor_points:
                        result.append({"floor": current_floor, "points": floor_points})
                    floor_points = []
                    current_floor = floor
                floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})
                seen_vertices.add(vertex)

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        # Генерация инструкций на основе координат
        final_instructions = [f"Выйдите из {start_room_name} на {current_floor} этаже"]
        last_x, last_y = None, None
        last_instruction = None

        for floor_data in result:
            points = floor_data["points"]
            for i in range(len(points) - 1):
                current = points[i]
                next_point = points[i + 1]
                curr_x, curr_y = current["x"], current["y"]
                next_x, next_y = next_point["x"], next_point["y"]

                # Игнорируем точки с разницей меньше 10
                if last_x is not None and last_y is not None:
                    dx = abs(curr_x - last_x)
                    dy = abs(curr_y - last_y)
                    if dx < 10 and dy < 10:
                        continue

                # Определяем направление
                dx = next_x - curr_x
                dy = next_y - curr_y
                angle = math.degrees(math.atan2(dy, dx)) if dx != 0 or dy != 0 else 0

                if "outdoor" in current["vertex"] and "outdoor" not in next_point["vertex"]:
                    if -45 <= angle <= 45:
                        instruction = "Поверните вправо и зайдите в здание"
                    elif 45 < angle <= 135:
                        instruction = "Поверните прямо и зайдите в здание"
                    elif 135 < angle <= 225:
                        instruction = "Поверните налево и зайдите в здание"
                    else:
                        instruction = "Поверните прямо и зайдите в здание"
                elif "outdoor" not in current["vertex"] and "outdoor" in next_point["vertex"]:
                    if -45 <= angle <= 45:
                        instruction = "Выйдите из здания и поверните вправо"
                    elif 45 < angle <= 135:
                        instruction = "Выйдите из здания и поверните прямо"
                    elif 135 < angle <= 225:
                        instruction = "Выйдите из здания и поверните налево"
                    else:
                        instruction = "Выйдите из здания и поверните прямо"
                elif "stair" in current["vertex"] and "to" in current["vertex"]:
                    direction = "вверх" if next_point["floor"] > current["floor"] else "вниз"
                    instruction = f"Начните {direction} по лестнице с {current['floor']} этажа на {next_point['floor']} этаж"
                elif "stair" in current["vertex"] and "from" in current["vertex"]:
                    direction = "вверх" if current["floor"] < next_point["floor"] else "вниз"
                    instruction = f"Завершите {direction} по лестнице на {next_point['floor']} этаж"
                else:
                    if -45 <= angle <= 45:
                        instruction = "Пройдите вперед"
                    elif 45 < angle <= 135:
                        instruction = "Поверните налево"
                    elif -135 <= angle < -45:
                        instruction = "Поверните направо"
                    else:
                        instruction = "Развернитесь"

                # Добавляем "На перекрестке", если меняется тип вершины
                if i > 0 and ("outdoor" in current["vertex"] != "outdoor" in points[i - 1]["vertex"]):
                    instruction = f"На перекрестке {instruction.lower()}"

                # Убеждаемся, что инструкция не дублируется
                if instruction != last_instruction:
                    final_instructions.append(instruction)
                    last_instruction = instruction

                last_x, last_y = curr_x, curr_y

        final_instructions.append(f"Вы прибыли в {end_room_name} на {current_floor} этаже")

        # Логирование и отправка маршрута
        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")