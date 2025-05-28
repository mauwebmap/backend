from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.builder import build_graph
from app.map.utils.pathfinder import find_path
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/route")
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Получен запрос на построение маршрута от {start} до {end}")

    logger.info("Начало построения графа")
    try:
        graph = build_graph(db, start, end)
        logger.info("Граф успешно построен")
    except Exception as e:
        logger.info(f"Ошибка при построении графа: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при построении графа: {str(e)}")

    logger.info(f"Начало поиска пути от {start} до {end}")
    try:
        path, weight = find_path(graph, start, end)
        logger.info(f"Поиск пути завершён: путь={path}, вес={weight}")
    except Exception as e:
        logger.info(f"Ошибка при поиске пути: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {str(e)}")

    if not path:
        logger.info(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    # Формируем маршрут с этажами и улучшенными инструкциями
    result = []
    current_floor = None
    floor_points = []
    instructions = []

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        floor = vertex_data["coords"][2]
        x, y = vertex_data["coords"][0], vertex_data["coords"][1]

        # Инструкции для лестниц и переходов
        if i < len(path) - 1:
            next_vertex = path[i + 1]
            neighbors = graph.get_neighbors(vertex)
            edge_data = {}
            for neighbor, weight, data in neighbors:
                if neighbor == next_vertex:
                    edge_data = data
                    break
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

        if floor != current_floor:
            if floor_points:
                result.append({"floor": current_floor, "points": floor_points})
            floor_points = []
            current_floor = floor

        floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

    if floor_points:
        result.append({"floor": current_floor, "points": floor_points})

    logger.info(f"Маршрут успешно сформирован: путь={result}, вес={weight}, инструкции={instructions}")
    return {"path": result, "weight": weight, "instructions": instructions}