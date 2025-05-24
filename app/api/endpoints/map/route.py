# backend/app/map/routes/route.py
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
    logger.info(f"Received request to find route from {start} to {end}")

    graph = build_graph(db, start, end)
    path, weight = find_path(graph, start, end)

    if not path:
        logger.error(f"Failed to find path from {start} to {end}")
        raise HTTPException(status_code=404, detail="Path not found")

    # Формируем маршрут с этажами, фильтруем сегменты
    result = []
    current_floor = None
    floor_points = []
    instructions = []

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        floor = vertex_data["coords"][2]
        x, y = vertex_data["coords"][0], vertex_data["coords"][1]

        # Добавляем инструкции для лестниц и переходов
        if "stair" in vertex:
            if i > 0:
                prev_vertex = path[i - 1]
                prev_floor = graph.get_vertex_data(prev_vertex)["coords"][2]
                instructions.append(f"Go down/up from floor {prev_floor} to floor {floor} via {vertex}")
        elif "outdoor" in vertex and i > 0 and "transition" in graph.get_edge_data(path[i-1], vertex)["type"]:
            instructions.append(f"Exit to outdoor via {vertex}")

        if floor != current_floor:
            if floor_points:
                result.append({"floor": current_floor, "points": floor_points})
            floor_points = []
            current_floor = floor

        # Добавляем только фантомные точки или конечные точки пути
        if "phantom" in vertex or vertex == start or vertex == end:
            floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

    if floor_points:
        result.append({"floor": current_floor, "points": floor_points})

    logger.info(f"Pathfinding completed: path={path}, weight={weight}")
    return {"path": result, "weight": weight, "instructions": instructions}