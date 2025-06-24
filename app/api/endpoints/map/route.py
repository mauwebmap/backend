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
PIXEL_TO_METER = 0.05  # 1 пиксель = 0.05 метра

def filter_path_points(graph: Graph, path: list) -> list:
    """Фильтрует точки пути, убирая лишние лестничные точки."""
    filtered_points = []
    seen_vertices = set()
    skip_next = False
    for i, vertex in enumerate(path):
        if skip_next:
            skip_next = False
            continue
        vertex_data = graph.get_vertex_data(vertex)
        if not vertex_data or "coords" not in vertex_data:
            logger.error(f"Отсутствуют данные для вершины {vertex}")
            raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")
        x, y, floor = vertex_data["coords"]
        if vertex not in seen_vertices and (not filtered_points or all(
            abs(x - fp["x"]) > 5 or abs(y - fp["y"]) > 5 or fp["floor"] != floor
            for fp in filtered_points
        )):
            filtered_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})
            seen_vertices.add(vertex)
        if "stair_end" in vertex and "from" in vertex and i < len(path) - 1:
            next_vertex = path[i + 1]
            if "stair_start" in next_vertex and "from" in next_vertex:
                skip_next = True
    return filtered_points

def generate_directions(graph: Graph, filtered_points: list, rooms: dict, start: str, end: str, end_floor_number: int) -> list:
    """Генерирует инструкции для маршрута."""
    instructions = []
    directions = []
    current_floor = None
    result = []
    floor_points = []
    start_room_added = False

    for i, point in enumerate(filtered_points):
        vertex = point["vertex"]
        x, y, floor = point["x"], point["y"], point["floor"]

        if floor != current_floor:
            if floor_points:
                result.append({"floor": current_floor, "points": floor_points})
            floor_points = []
            current_floor = floor
        floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

        if i < len(filtered_points) - 1:
            next_point = filtered_points[i + 1]
            next_vertex = next_point["vertex"]
            edge_data = graph.get_edge_data(vertex, next_vertex)
            if edge_data.get("type") == "лестница" and "stair_end" in next_vertex and "from" in next_vertex:
                prev_floor = filtered_points[i - 1]["floor"] if i > 0 else floor
                if prev_floor != next_point["floor"]:
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

    for floor_data in result:
        floor_points = floor_data["points"]
        for j in range(len(floor_points) - 1):
            current = floor_points[j]
            next_point = floor_points[j + 1]
            prev_point = floor_points[j - 1] if j > 0 else None

            dx = next_point["x"] - current["x"]
            dy = next_point["y"] - current["y"]
            distance = round(math.sqrt(dx**2 + dy**2) * PIXEL_TO_METER)
            if distance < 1:
                continue
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
                    direction = f"Идите прямо {distance} метров"
                elif -135 <= turn_angle < -45:
                    direction = f"Поверните налево и идите {distance} метров"
                elif 45 < turn_angle <= 135:
                    direction = f"Поверните направо и идите {distance} метров"
                else:
                    continue
            else:
                if not start_room_added:
                    room = rooms.get(start)
                    direction = f"На {floor_data['floor']}-м этаже начните движение из {room.name} {room.cab_id} кабинет"
                    start_room_added = True
                else:
                    continue
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

    return final_instructions, result

@router.get("/route")
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
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

    rooms = {f"room_{room.id}": room for room in db.query(Room).all()}
    try:
        end_id = int(end.replace("room_", ""))
        end_room = db.query(Room).filter(Room.id == end_id).first()
        end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
        end_floor_number = end_floor.floor_number if end_floor else end_room.floor_id
        logger.info(f"end_floor_number={end_floor_number} для комнаты {end}")
    except Exception as e:
        logger.error(f"Ошибка при получении end_floor_number для {end}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при получении этажа конечной комнаты: {str(e)}")

    filtered_points = filter_path_points(graph, path)
    final_instructions, result = generate_directions(graph, filtered_points, rooms, start, end, end_floor_number)

    logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
    return {"path": result, "weight": weight, "instructions": final_instructions}