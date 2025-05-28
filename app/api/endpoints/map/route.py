import math
import logging
from fastapi import APIRouter, HTTPException
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
    logger.info("Начало построения графа")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Граф успешно построен: {len(graph.vertices)} вершин")
    except Exception as e:
        logger.error(f"Ошибка при построении графа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при построении графа: {str(e)}")

    # Поиск пути
    logger.info(f"Начало поиска пути от {start} до {end}")
    try:
        path, weight = find_path(graph, start, end)
        logger.info(f"Поиск пути завершён: путь={path}, вес={weight}")
    except Exception as e:
        logger.error(f"Ошибка при поиске пути: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {str(e)}")

    if path is None or not path:
        logger.info(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    # Формирование маршрута
    logger.info("Начало формирования маршрута")
    result = []
    current_floor = None
    floor_points = []
    instructions = []

    # Добавляем промежуточные start точки для уличных сегментов
    enhanced_path = []
    for i, vertex in enumerate(path):
        enhanced_path.append(vertex)
        if vertex.endswith("_end") and i < len(path) - 1:
            segment_id = vertex.split("_end")[0]  # Например, outdoor_2 из outdoor_2_end
            start_vertex = f"{segment_id}_start"
            if start_vertex in graph.vertices and start_vertex != path[i + 1]:
                enhanced_path.append(start_vertex)

    path = enhanced_path

    try:
        for i, vertex in enumerate(path):
            logger.debug(f"Обрабатываем вершину: {vertex}")
            vertex_data = graph.get_vertex_data(vertex)
            if not vertex_data or "coords" not in vertex_data:
                logger.error(f"Отсутствуют данные или координаты для вершины {vertex}: {vertex_data}")
                raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")

            floor = vertex_data["coords"][2]
            x, y = vertex_data["coords"][0], vertex_data["coords"][1]
            logger.debug(f"Вершина {vertex}: floor={floor}, x={x}, y={y}")

            # Включаем все ключевые вершины
            if (vertex.startswith("room_") or vertex.startswith("phantom_stair_") or
                vertex.startswith("phantom_segment") or vertex.startswith("outdoor_")):
                if floor != current_floor:
                    if floor_points:
                        result.append({"floor": current_floor, "points": floor_points})
                        logger.debug(f"Добавлен этаж {current_floor} с точками: {floor_points}")
                    floor_points = []
                    current_floor = floor
                floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

            # Генерация инструкций
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                neighbors = graph.get_neighbors(vertex)
                edge_data = next((data for neighbor, weight, data in neighbors if neighbor == next_vertex), {})
                if edge_data:
                    if edge_data.get("type") == "лестница":
                        prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                        direction = "up" if floor > prev_floor else "down"
                        instructions.append(f"Go {direction} via {vertex} to floor {floor}")
                    elif edge_data.get("type") == "дверь" and vertex.startswith("outdoor_"):
                        instructions.append(f"Exit building via {vertex}")
                    elif edge_data.get("type") == "дверь" and next_vertex.startswith("outdoor_"):
                        instructions.append(f"Enter building via {next_vertex}")

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})
            logger.debug(f"Добавлен последний этаж {current_floor} с точками: {floor_points}")

        # Генерация направлений
        directions = []
        for i in range(len(result)):
            floor_points = result[i]["points"]
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
                        direction = "вперёд"
                    elif 45 < turn_angle <= 135:
                        direction = "налево"
                    elif -135 <= turn_angle < -45:
                        direction = "направо"
                    else:
                        direction = "назад"
                else:
                    direction = "вперёд"

                directions.append((next_point["vertex"], direction))

        for vertex, direction in directions:
            instructions.append(f"При движении к {vertex} {direction}")

        logger.info(f"Маршрут успешно сформирован: путь={result}, вес={weight}, инструкции={instructions}")
    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")

    return {"path": result, "weight": weight, "instructions": instructions}