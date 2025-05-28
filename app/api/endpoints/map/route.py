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
    logger.info("Начало построения графа")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Граф успешно построен: {len(graph.vertices)} вершин")
        for vertex in graph.vertices:
            logger.debug(f"Вершина: {vertex}, данные: {graph.get_vertex_data(vertex)}")
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

    # Проверка найденного пути
    if path is None or not path:
        logger.info(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    # Формируем маршрут с этажами и инструкциями
    logger.info("Начало формирования маршрута")
    result = []
    current_floor = None
    floor_points = []
    instructions = []

    try:
        for i, vertex in enumerate(path):
            # Проверка данных вершины
            vertex_data = graph.get_vertex_data(vertex)
            if not vertex_data or "coords" not in vertex_data:
                logger.error(f"Отсутствуют данные или координаты для вершины {vertex}: {vertex_data}")
                raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {vertex}")

            floor = vertex_data["coords"][2]
            x, y = vertex_data["coords"][0], vertex_data["coords"][1]
            logger.debug(f"Обрабатываем вершину {vertex}: floor={floor}, x={x}, y={y}")

            # Инструкции для лестниц и переходов
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                neighbors = graph.get_neighbors(vertex)
                edge_data = next((data for neighbor, weight, data in neighbors if neighbor == next_vertex), {})
                if edge_data:
                    if edge_data.get("type") == "лестница":
                        prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                        direction = "up" if floor > prev_floor else "down"
                        instructions.append(f"Go {direction} from floor {prev_floor} to floor {floor} via {vertex}")
                    elif edge_data.get("type") == "дверь" and "outdoor" in next_vertex:
                        instructions.append(f"Exit building via {vertex} to outdoor")
                    elif edge_data.get("type") == "улица" and "outdoor" in vertex and "segment" in next_vertex:
                        instructions.append(f"Follow outdoor path from {vertex} to building entry")
                    elif edge_data.get("type") == "дверь" and "segment" in vertex and "outdoor" in next_vertex:
                        instructions.append(f"Enter building from outdoor via {next_vertex}")

            # Добавляем полный путь для уличных сегментов
            if "outdoor" in vertex and i < len(path) - 1:
                next_vertex = path[i + 1]
                next_vertex_data = graph.get_vertex_data(next_vertex)
                if not next_vertex_data or "coords" not in next_vertex_data:
                    logger.error(f"Отсутствуют данные для следующей вершины {next_vertex}")
                    raise HTTPException(status_code=500, detail=f"Некорректные данные для вершины {next_vertex}")

                if "outdoor" in next_vertex or ("segment" in next_vertex and any(
                        edge[2].get("type") == "дверь" for edge in graph.get_neighbors(vertex))):
                    continue  # Пропускаем, если следующий узел тоже outdoor
                outdoor_id = int(vertex.split("_")[1])
                outdoor_start, outdoor_end = [v for v in graph.vertices if
                                              v.startswith(f"outdoor_{outdoor_id}_") and v.endswith(("_start", "_end"))]
                start_coords = graph.get_vertex_data(outdoor_start)["coords"]
                end_coords = graph.get_vertex_data(outdoor_end)["coords"]
                if vertex == outdoor_start:
                    floor_points.append({"x": start_coords[0], "y": start_coords[1], "vertex": outdoor_start, "floor": 1})
                    floor_points.append({"x": end_coords[0], "y": end_coords[1], "vertex": outdoor_end, "floor": 1})
                elif vertex == outdoor_end:
                    floor_points.append({"x": end_coords[0], "y": end_coords[1], "vertex": outdoor_end, "floor": 1})
                    floor_points.append({"x": start_coords[0], "y": start_coords[1], "vertex": outdoor_start, "floor": 1})

            if floor != current_floor:
                if floor_points:
                    result.append({"floor": current_floor, "points": floor_points})
                    logger.debug(f"Добавлен этаж {current_floor} с точками: {floor_points}")
                floor_points = []
                current_floor = floor

            floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

        if floor_points:
            result.append({"floor": current_floor, "points": floor_points})
            logger.debug(f"Добавлен последний этаж {current_floor} с точками: {floor_points}")

        # Определение направлений
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
                    direction = "вперёд" if abs(dx) > abs(dy) else "вперёд"

                directions.append((current["vertex"], direction))

        # Добавление инструкций с направлениями
        for vertex, direction in directions:
            instructions.append(f"При движении к {vertex} {direction}")

        logger.info(f"Маршрут успешно сформирован: путь={result}, вес={weight}, инструкции={instructions}")
    except Exception as e:
        logger.error(f"Ошибка при формировании маршрута: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при формировании маршрута: {str(e)}")

    return {"path": result, "weight": weight, "instructions": instructions}