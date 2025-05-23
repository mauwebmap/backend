# backend/app/map/routes/route.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
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

    # Формируем маршрут с этажами
    result = []
    current_floor = None
    floor_points = []

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        floor = vertex_data["coords"][2]
        x, y = vertex_data["coords"][0], vertex_data["coords"][1]

        # Определяем тип перехода
        transition_type = None
        if i > 0:
            prev_vertex = path[i - 1]
            edge_data = graph.get_edge_data(prev_vertex, vertex)
            transition_type = edge_data["type"] if edge_data else None

        # Проверяем, является ли переход "улица-дверь" или "дверь-улица"
        include_point = True
        if transition_type and transition_type not in ["phantom"]:
            if i < len(path) - 1:
                next_vertex = path[i + 1]
                next_edge_data = graph.get_edge_data(vertex, next_vertex)
                next_transition_type = next_edge_data["type"] if next_edge_data else None
                # Если это не "улица-дверь" или "дверь-улица", можно пропустить промежуточные точки внутри сегмента
                if not (
                    (transition_type == "улица" and next_transition_type == "дверь") or
                    (transition_type == "дверь" and next_transition_type == "улица")
                ):
                    include_point = transition_type in ["phantom", "лестница"]

        if include_point:
            if floor != current_floor:
                if floor_points:
                    result.append({"floor": current_floor, "points": floor_points})
                floor_points = []
                current_floor = floor

            floor_points.append({"x": x, "y": y, "vertex": vertex, "floor": floor})

    if floor_points:
        result.append({"floor": current_floor, "points": floor_points})

    logger.info(f"Pathfinding completed: path={path}, weight={weight}")
    return {"path": result, "weight": weight, "instructions": []}