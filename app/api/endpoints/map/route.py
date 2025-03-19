from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.graph import Graph
from app.map.utils.pathfinder import a_star
from app.map.utils.builder import build_graph, parse_vertex_id
from app.map.models.floor import Floor
from app.map.models.floor import Room
from app.map.models.floor import Segment

router = APIRouter()

@router.get("/route")
def get_route(start: str, end: str, db: Session = Depends(get_db)):
    """Получить маршрут от start до end (любые типы точек: room, segment, outdoor)."""
    try:
        # Проверяем формат идентификаторов
        start_type, start_id = parse_vertex_id(start)
        end_type, end_id = parse_vertex_id(end)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Строим граф
    graph = build_graph(db, start, end)

    # Определяем конечные вершины для A*
    start_vertex = start if start_type != "segment" else f"segment_{start_id}_start"
    end_vertex = end if end_type != "segment" else f"segment_{end_id}_end"

    if start_vertex not in graph.vertices or end_vertex not in graph.vertices:
        raise HTTPException(status_code=400, detail="Неверная начальная или конечная точка")

    # Ищем путь
    path, weight = a_star(graph, start_vertex, [end_vertex])
    if not path:
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    # Разделяем путь по этажам
    path_by_floor = []
    current_floor = None
    current_points = []

    for vertex in path:
        floor_id = None
        if "room" in vertex:
            room = db.query(Room).filter(Room.id == int(vertex.split('_')[1])).first()
            floor_id = room.floor_id if room else None
        elif "segment" in vertex:
            segment = db.query(Segment).filter(Segment.id == int(vertex.split('_')[1])).first()
            floor_id = segment.floor_id if segment else None
        elif "outdoor" in vertex:
            floor_id = "outdoor"

        if floor_id != current_floor:
            if current_points:
                floor_num = "outdoor" if current_floor == "outdoor" else (
                    db.query(Floor).filter(Floor.id == current_floor).first().floor_number if current_floor else "unknown"
                )
                path_by_floor.append({"floor": floor_num, "points": current_points})
            current_points = []
            current_floor = floor_id

        current_points.append({"x": graph.vertices[vertex][0], "y": graph.vertices[vertex][1]})

    if current_points:
        floor_num = "outdoor" if current_floor == "outdoor" else (
            db.query(Floor).filter(Floor.id == current_floor).first().floor_number if current_floor else "unknown"
        )
        path_by_floor.append({"floor": floor_num, "points": current_points})

    return {"path": path_by_floor, "weight": weight}