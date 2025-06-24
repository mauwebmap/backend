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
    stair_connections = {(conn.from_segment_id, conn.to_segment_id): conn for conn in connections if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id}
    rooms = {f"room_{room.id}": room for room in db.query(Room).all()}

    try:
        filtered_points = []
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
            # Пропускаем segment_X_start/end, если они не являются лестничными
            if i < len(path) - 1 and "phantom_room" in vertex and "segment" in path[i + 1] and path[i + 1].endswith(("_start", "_end")):
                next_vertex = path[i + 1]
                if not any(conn.from_segment_id == int(next_vertex.split("_")[1]) and conn.type == "лестница" for conn in connections):
                    skip_next = True
                    continue
            if not filtered_points or all(
                abs(x - fp["x"]) > 5 or abs(y - fp["y"]) > 5 or floor != fp["floor"]
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
                if edge_data.get("type") == "лестница":
                    prev_floor = filtered_points[i - 1]["floor"] if i > 0 else floor
                    direction = "вверх" if next_point["floor"] > prev_floor else "вниз"
                    instructions.append(f"{'Поднимитесь' if direction == 'вверх' else 'Спуститесь'} по лестнице с {prev_floor}-го на {next_point['floor']}-й этаж")
                elif edge_data.get("type") == "дверь":
                    if "outdoor" in next_vertex and not any("выйдите" in instr.lower() for instr in instructions[-2:]):
                        instructions.append("Выйдите из здания через дверь")
                    elif "outdoor" in vertex and not any("войдите" in instr.lower() for instr in instructions[-2:]):
                        instructions.append("Войдите в здание через дверь")

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})

        directions = []
        for floor_data in result:
            floor_points = floor_data["points"]
            for j in range(len(floor_points) - 1):
                current = floor_points[j]
                next_point = floor_points[j + 1]
                prev_point = floor_points[j - 1] if j > 0 else None

                dx = next_point["x"] - current["x"]
                dy = next_point["y"] - current["y"]

                # Проверяем, что движение происходит по прямым углам
                if abs(dx) > 5 and abs(dy) > 5:
                    logger.warning(f"Непрямой угол между {current['vertex']} и {next_point['vertex']}: dx={dx}, dy={dy}")
                    continue  # Пропускаем, если не по оси X или Y

                if prev_point:
                    prev_dx = current["x"] - prev_point["x"]
                    prev_dy = current["y"] - prev_point["y"]
                    if abs(prev_dx) > 5 and abs(prev_dy) > 5:
                        logger.warning(f"Непрямой угол в предыдущем шаге: dx={prev_dx}, dy={prev_dy}")
                        continue
                    if abs(dx) > 5 and abs(prev_dx) > 5:
                        direction = "Идите прямо"
                    elif abs(dy) > 5 and abs(prev_dy) > 5:
                        direction = "Идите прямо"
                    elif (abs(dx) > 5 and abs(prev_dy) > 5) or (abs(dy) > 5 and abs(prev_dx) > 5):
                        direction = "Поверните налево" if (dx > 0 and prev_dy > 0) or (dx < 0 and prev_dy < 0) or (dy > 0 and prev_dx < 0) or (dy < 0 and prev_dx > 0) else "Поверните направо"
                    else:
                        direction = "Идите прямо"
                else:
                    room = rooms.get(start) if j == 0 else rooms.get(end) if j == len(floor_points) - 2 else None
                    direction = f"Начните движение из {room.name} {room.cab_id} кабинет" if room else "Начните движение"

                directions.append(direction)

        final_instructions = []
        if directions and "Начните движение" in directions[0]:
            final_instructions.append(directions[0])
            directions = directions[1:]
        instr_idx = 0
        dir_idx = 0
        while instr_idx < len(instructions) or dir_idx < len(directions):
            if instr_idx < len(instructions):
                final_instructions.append(instructions[instr_idx])
                instr_idx += 1
            if dir_idx < len(directions) and (instr_idx >= len(instructions) or "лестнице" not in instructions[instr_idx - 1].lower() and "дверь" not in instructions[instr_idx - 1].lower()):
                final_instructions.append(directions[dir_idx])
                dir_idx += 1

        if end in rooms:
            final_instructions.append(f"Вы прибыли в {rooms[end].name} {rooms[end].cab_id} кабинет")

        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")