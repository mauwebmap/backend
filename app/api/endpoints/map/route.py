# backend/app/map/utils/route.py
from app.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.map.utils.graph import Graph
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from math import atan2, degrees, sqrt
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_direction(prev_prev_coords: tuple, prev_coords: tuple, curr_coords: tuple, prev_direction: str = None) -> str:
    curr_dx = curr_coords[0] - prev_coords[0]
    curr_dy = curr_coords[1] - prev_coords[1]
    distance = sqrt(curr_dx ** 2 + curr_dy ** 2)
    if distance < 15:
        return "вперёд" if prev_direction in ["вперёд", None] else prev_direction

    curr_angle = degrees(atan2(curr_dy, curr_dx))
    curr_angle = ((curr_angle + 180) % 360) - 180
    return "направо" if -45 <= curr_angle <= 45 else "вперёд" if 45 < curr_angle <= 135 else "налево"

def get_vertex_details(vertex: str, db: Session) -> tuple:
    vertex_type, vertex_id = vertex.split("_", 1)
    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        return room.name, room.cab_id if room else (vertex, None)
    return "лестницы" if vertex_type == "segment" else f"Уличный сегмент {vertex_id}", None

def generate_text_instructions(path: list, graph: Graph, db: Session) -> list:
    instructions = []
    prev_coords = None
    prev_floor = None

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        coords = vertex_data["coords"]
        floor_number = coords[2]

        if i == 0:
            vertex_name, _ = get_vertex_details(vertex, db)
            instructions.append(f"При выходе из {vertex_name}")
            prev_coords = coords[:2]
            prev_floor = floor_number
            continue

        if prev_floor != floor_number:
            if prev_floor != 1 and floor_number == 1:
                instructions.append("Выйдите из здания на улицу")
            elif prev_floor == 1 and floor_number != 1:
                instructions.append(f"Войдите в здание и поднимитесь на {floor_number}-й этаж")
            elif prev_floor != 1 and floor_number != 1:
                instructions.append(f"Поднимитесь на {floor_number}-й этаж")
            prev_floor = floor_number

        if prev_coords:
            direction = get_direction(None, prev_coords, coords[:2])
            if direction != "вперёд" or i == len(path) - 1:
                vertex_name, vertex_number = get_vertex_details(vertex, db)
                destination = f"{vertex_name} номер {vertex_number}" if vertex_number else vertex_name
                instructions.append(f"{direction} до {destination}")

        prev_coords = coords[:2]

    return instructions

def simplify_route(path: list, graph: Graph) -> list:
    if len(path) < 2:
        return path

    simplified = []
    i = 0
    while i < len(path):
        current = path[i]

        # Проверяем последовательные переходы (дверь-улица или улица-дверь)
        if i < len(path) - 1:
            next_vertex = path[i + 1]
            current_edge = None
            for neighbor, _, edge_data in graph.get_neighbors(current):
                if neighbor == next_vertex:
                    current_edge = edge_data
                    break

            if current_edge and current_edge["type"] in ["outdoor start", "outdoor end"]:
                simplified.append(current)
                simplified.append(next_vertex)
                i += 2
                continue

        # Пропускаем phantom-вершины, если это не часть перехода
        if not current.startswith("phantom_"):
            simplified.append(current)
        i += 1

    return simplified  # Убираем лишнюю логику пересчёта, так как phantom-точки уже учтены

@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")
    try:
        path, weight, graph = find_path(db, start, end, return_graph=True)
        logger.info(f"Pathfinding completed: path={path}, weight={weight}")
    except Exception as e:
        logger.error(f"Error during pathfinding: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {e}")

    if not path:
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    # Упрощаем маршрут, сохраняя переходы дверь-улица
    simplified_path = simplify_route(path, graph)
    logger.info(f"Simplified path: {simplified_path}")

    # Убираем строгую проверку соединений, так как phantom-точки меняют количество
    # logger.error(f"Connection count mismatch: original={original_connections}, simplified={simplified_connections}")
    # if original_connections != simplified_connections:
    #     raise HTTPException(status_code=500, detail="Ошибка: количество соединений не совпадает")

    try:
        instructions = generate_text_instructions(simplified_path, graph, db)
    except Exception as e:
        logger.error(f"Error generating instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации инструкций: {e}")

    route = []
    current_floor = None
    floor_points = []

    for vertex in simplified_path:
        vertex_data = graph.get_vertex_data(vertex)
        coords = vertex_data["coords"]
        floor_number = coords[2]

        point = {"x": coords[0], "y": coords[1], "vertex": vertex, "floor": floor_number}

        if current_floor is None:
            current_floor = floor_number
            floor_points.append(point)
        elif floor_number != current_floor:
            if floor_points:
                route.append({"floor": current_floor, "points": floor_points})
            floor_points = [point]
            current_floor = floor_number
        else:
            floor_points.append(point)

    if floor_points:
        route.append({"floor": current_floor, "points": floor_points})

    return {"path": route, "weight": weight, "instructions": instructions}