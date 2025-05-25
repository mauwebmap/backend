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
        logger.info(f"Граф успешно построен с {len(graph.vertices)} вершинами")
    except Exception as e:
        logger.error(f"Ошибка при построении графа: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при построении графа")

    logger.info(f"Начало поиска пути от {start} до {end}")
    try:
        path, weight = find_path(graph, start, end)
        logger.info(f"Поиск пути завершён: путь={path[:10]}... (обрезан), вес={weight}")
    except Exception as e:
        logger.error(f"Ошибка при поиске пути: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при поиске пути")

    if not path or weight == float("inf"):
        logger.warning(f"Путь от {start} до {end} не найден")
        raise HTTPException(status_code=404, detail="Путь не найден")

    # Оптимизация данных пути: обрезаем до 20 вершин для теста
    path = path[:20] if len(path) > 20 else path

    # Формируем маршрут с этажами и инструкциями
    result = []
    current_floor = None
    floor_points = []
    instructions = []

    for i, vertex in enumerate(path):
        try:
            vertex_data = graph.get_vertex_data(vertex)
            floor = vertex_data["coords"][2]
            x, y = vertex_data["coords"][0], vertex_data["coords"][1]

            if i < len(path) - 1:
                next_vertex = path[i + 1]
                edge_data = next(graph.get_neighbors(vertex), [None, 0, {}])[2]
                if edge_data and edge_data.get("type") == "лестница":
                    prev_floor = graph.get_vertex_data(path[i - 1])["coords"][2] if i > 0 else floor
                    direction = "up" if floor > prev_floor else "down"
                    instructions.append(f"Go {direction} from floor {prev_floor} to {floor} via {vertex}")
                elif edge_data and edge_data.get("type") == "переход" and "outdoor" in next_vertex:
                    instructions.append(f"Exit to outdoor via {next_vertex}")

            if floor != current_floor:
                if floor_points:
                    result.append({"floor": current_floor, "points": floor_points})
                floor_points = []
                current_floor = floor

            floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})
        except KeyError:
            logger.warning(f"Данные вершины {vertex} отсутствуют, пропускаем")
            continue

    if floor_points:
        result.append({"floor": current_floor, "points": floor_points})

    # Упрощение данных для ответа
    simplified_result = [{"floor": r["floor"], "points": r["points"][:10]} for r in result]  # Ограничение точек
    logger.info(f"Маршрут сформирован: путь={simplified_result}, вес={weight}, инструкции={instructions}")
    return {"path": simplified_result, "weight": round(weight, 2), "instructions": instructions}