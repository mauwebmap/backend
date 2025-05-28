# app/map/utils/route.py
import math
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.builder import build_graph
from app.map.utils.pathfinder import find_path

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

            # Генерация инструкций
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                edge_data = graph.get_edge_data(vertex, next_vertex)
                if edge_data.get("type") == "лестница":
                    prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                    direction = "up" if floor > prev_floor else "down"
                    instructions.append(f"Go {direction} via stairs from floor {prev_floor} to floor {floor}")
                elif edge_data.get("type") == "дверь" and "outdoor" in next_vertex:
                    instructions.append("Exit building through the door")
                elif edge_data.get("type") == "дверь" and "outdoor" in vertex:
                    instructions.append("Enter building through the door")
                elif edge_data.get("type") == "outdoor":
                    instructions.append("Follow the outdoor path")

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
                        direction = "straight"
                    elif 45 < turn_angle <= 135:
                        direction = "turn left"
                    elif -135 <= turn_angle < -45:
                        direction = "turn right"
                    else:
                        direction = "turn around"
                else:
                    direction = "start walking"

                directions.append(direction)

        # Добавляем направления в инструкции
        direction_idx = 0
        final_instructions = []
        for instr in instructions:
            final_instructions.append(instr)
            if "via stairs" not in instr and "building" not in instr and "outdoor path" not in instr and direction_idx < len(directions):
                final_instructions.append(f"Then {directions[direction_idx]}")
                direction_idx += 1
        while direction_idx < len(directions):
            final_instructions.append(directions[direction_idx])
            direction_idx += 1

        logger.info(f"Маршрут сформирован: путь={result}, вес={weight}, инструкции={final_instructions}")
        return {"path": result, "weight": weight, "instructions": final_instructions}

    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")