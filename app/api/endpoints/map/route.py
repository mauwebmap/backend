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
async def get_route(start: str, end: str, db: Session = Depends(get_db), end_floor_number=None):
    logger.info(f"Получен запрос на построение маршрута от {start} до {end}")

    try:
        graph = build_graph(db, start, end)
        logger.info(f"Граф успешно построен: {len(graph.vertices)} вершин")
    except Exception as e:
        logger.error(f"Ошибка при построении графа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при построении графа: {str(e)}")

    try:
        path, weight = find_path(graph, start, end)
        logger.info(f"Поиск пути завершён: путь={path}, вес={weight}")
    except Exception as e:
        logger.error(f"Ошибка при поиске пути: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {str(e)}")

    if not path:
        logger.info(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    result = []
    current_floor = None
    floor_points = []
    instructions = []
    seen_vertices = set()

    connections = db.query(Connection).all()
    rooms = {f"room_{room.id}": room for room in db.query(Room).all()}
    # Масштаб: 1 пиксель = 0.1 метра
    PIXEL_TO_METER = 0.1

    try:
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
                if edge_data.get("type") == "лестница" and "stair_end" in next_vertex:
                    prev_floor = filtered_points[i - 1]["floor"] if i > 0 else floor
                    direction = "вверх" if next_point["floor"] > prev_floor else "вниз"
                    if not any("лестнице" in instr.lower() for instr in instructions[-1:]):
                        instructions.append(f"На {prev_floor}-м этаже спуститесь по лестнице на {next_point['floor']}-й этаж" if direction == "вниз" else f"На {prev_floor}-м этаже поднимитесь по лестнице на {next_point['floor']}-й этаж")
                elif edge_data.get("type") == "дверь":
                    if "outdoor" in next_vertex and not any("выйдите" in instr.lower() for instr in instructions[-1:]):
                        instructions.append(f"На {floor}-м этаже выйдите из здания через дверь")
                    elif "outdoor" in vertex and not any("войдите" in instr.lower() for instr in instructions[-1:]):
                        instructions.append(f"На {floor}-м этаже войдите в здание через дверь")

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        directions = []
        start_room_added = False
        for floor_data in result:
            floor_points = floor_data["points"]
            for j in range(len(floor_points) - 1):
                current = floor_points[j]
                next_point = floor_points[j + 1]
                prev_point = floor_points[j - 1] if j > 0 else None

                dx = next_point["x"] - current["x"]
                dy = next_point["y"] - current["y"]
                distance = round(math.sqrt(dx**2 + dy**2) * PIXEL_TO_METER, 1)
                angle = math.degrees(math.atan2(dy, dx))

                if prev_point:
                    prev_dx = current["x"] - prev_point["x"]
                    prev_dy = current["y"] - prev_point["y"]
                    prev_angle = math.degrees(math.atan2(prev_dy, prev_dx))
                    turn_angle = (angle - prev_angle + 180) % 360 - 180
                    if abs(dx) > 5 and abs(dy) > 5:
                        logger.warning(f"Непрямой угол между {current['vertex']} и {next_point['vertex']}: dx={dx}, dy={dy}")
                        continue
                    if -45 <= turn_angle <= 45:
                        direction = f"На {floor_data['floor']}-м этаже идите прямо {distance} метров"
                    elif -135 <= turn_angle < -45:
                        direction = f"На {floor_data['floor']}-м этаже поверните налево и идите {distance} метров"
                    elif 45 < turn_angle <= 135:
                        direction = f"На {floor_data['floor']}-м этаже поверните направо и идите {distance} метров"
                    else:
                        continue  # Пропускаем "Развернитесь"
                else:
                    if not start_room_added:
                        room = rooms.get(start)
                        direction = f"На {floor_data['floor']}-м этаже начните движение из {room.name} {room.cab_id} кабинет"
                        start_room_added = True
                    else:
                        continue  # Пропускаем повторное "Начните движение"

                directions.append(direction)

        final_instructions = []
        if directions:
            final_instructions.append(directions[0])
            directions = directions[1:]
        instr_idx = 0
        dir_idx = 0
        while instr_idx < len(instructions) or dir_idx < len(directions):
            if instr_idx < len(instructions):
                final_instructions.append(instructions[instr_idx])
                instr_idx += 1
            if dir_idx < len(directions):
                final_instructions.append(directions[dir_idx])
                dir_idx += 1

        if end in rooms:
            final_instructions.append(f"На {end_floor_number}-м этаже вы прибыли в {rooms[end].name} {rooms[end].cab_id} кабинет")

        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")