# backend/app/map/utils/route.py
from app.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.map.utils.graph import Graph
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.floor import Floor
from app.map.models.connection import Connection
from math import atan2, degrees, sqrt
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def get_direction(prev_prev_coords: tuple, prev_coords: tuple, curr_coords: tuple, prev_direction: str = None,
                  i: int = 0) -> str:
    curr_dx = curr_coords[0] - prev_coords[0]
    curr_dy = curr_coords[1] - prev_coords[1]
    distance = sqrt(curr_dx ** 2 + curr_dy ** 2)
    if distance < 15:
        return "вперёд" if prev_direction in ["вперёд", None] else prev_direction

    curr_angle = degrees(atan2(curr_dy, curr_dx))
    curr_angle = ((curr_angle + 180) % 360) - 180
    base_direction = "направо" if -45 <= curr_angle <= 45 else \
                     "вперёд" if 45 < curr_angle <= 135 else \
                     "налево" if 135 < curr_angle <= 180 or -180 <= curr_angle < -135 else "назад"

    if prev_prev_coords is None:
        return base_direction

    prev_dx = prev_coords[0] - prev_prev_coords[0]
    prev_dy = prev_coords[1] - prev_prev_coords[1]
    if prev_dx == 0 and prev_dy == 0:
        return base_direction

    prev_angle = degrees(atan2(prev_dy, prev_dx))
    prev_angle = ((prev_angle + 180) % 360) - 180

    angle_diff = ((curr_angle - prev_angle + 180) % 360) - 180
    if abs(angle_diff) < 15:
        return "вперёд" if prev_direction in ["вперёд", None] else base_direction
    return "поверните налево" if -180 < angle_diff <= -15 else "поверните направо"

def get_vertex_details(vertex: str, db: Session) -> tuple:
    vertex_type, vertex_id = vertex.split("_", 1)
    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        return room.name, room.cab_id if room else (vertex, None)
    elif vertex_type == "segment":
        return "лестницы", None
    elif vertex_type == "outdoor":
        return f"Уличный сегмент {vertex_id}", None
    elif vertex_type == "phantom":
        parts = vertex_id.split("_")
        room_id = parts[1]
        room = db.query(Room).filter(Room.id == int(room_id)).first()
        return f"Фантомная точка у {room.name if room else 'комнаты'}", None
    return vertex, None

def generate_text_instructions(path: list, graph: Graph, db: Session, view_floor: int = None) -> list:
    instructions = []
    prev_prev_coords = None
    prev_coords = None
    prev_vertex = None
    prev_floor = None
    current_instruction = []
    last_turn = None

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        coords = vertex_data["coords"]
        floor_id = coords[2]
        building_id = vertex_data["building_id"]
        try:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            if floor:
                floor_number = floor.floor_number if building_id is not None else 1
            else:
                logger.warning(f"Floor with id {floor_id} not found, assuming floor_id as floor number")
                floor_number = floor_id if building_id is not None else 1
        except Exception as e:
            logger.error(f"Error retrieving floor for floor_id {floor_id}: {e}")
            floor_number = floor_id if building_id is not None else 1

        logger.info(f"Processing vertex {vertex}, coords={coords}, floor={floor_number}, building_id={building_id}")

        if view_floor is not None and floor_number != view_floor and vertex.startswith("outdoor_"):
            continue

        vertex_name, vertex_number = get_vertex_details(vertex, db)

        if i == 0:
            current_instruction.append(f"При выходе из {vertex_name}")
            prev_coords = (coords[0], coords[1])
            prev_vertex = vertex
            prev_floor = floor_number
            continue

        if prev_floor != floor_number and i > 1:
            if current_instruction:
                instructions.append(" ".join(current_instruction) if not last_turn else f"{current_instruction[0]} {last_turn}")
                current_instruction = []
            if prev_floor != 1 and floor_number == 1:
                instructions.append("Выйдите из здания на улицу")
            elif prev_floor == 1 and floor_number != 1:
                instructions.append(f"Войдите в здание и поднимитесь на {floor_number}-й этаж")
            prev_prev_coords = None
            last_turn = None

        if prev_coords:
            try:
                direction = get_direction(prev_prev_coords, prev_coords, (coords[0], coords[1]), last_turn, i)
                logger.info(f"Direction for {vertex}: {direction}")
                if direction.startswith("поверните"):
                    if last_turn and "поверните" in last_turn.lower():
                        current_instruction[-1] = direction
                    else:
                        current_instruction.append(direction)
                    last_turn = direction
                elif direction != "вперёд" and not last_turn:
                    current_instruction.append(direction)
            except Exception as e:
                logger.error(f"Error calculating direction for vertex {vertex}: {e}")
                direction = "вперёд"
                current_instruction.append(direction)

        if i == len(path) - 1:
            destination = f"{vertex_name} номер {vertex_number}" if vertex_number else vertex_name
            current_instruction = [current_instruction[0] if current_instruction else ""] + \
                                 ([last_turn] if last_turn and "поверните" in last_turn.lower() else []) + \
                                 [f"пройдите вперёд до {destination}"]
            instructions.append(" ".join(filter(None, current_instruction)))

        prev_prev_coords = prev_coords
        prev_coords = (coords[0], coords[1])
        prev_floor = floor_number
        prev_vertex = vertex

    logger.info(f"Generated instructions: {instructions}")
    return instructions

def simplify_route(points: list) -> list:
    if len(points) < 2:
        return points
    simplified = [points[0]]
    for i in range(1, len(points)):
        if points[i]["vertex"] != simplified[-1]["vertex"]:  # Удаляем только дубликаты
            simplified.append(points[i])
    return simplified

@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, view_floor: int = None, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")
    try:
        path, weight, graph = find_path(db, start, end, return_graph=True)
        logger.info(f"Pathfinding completed: path={path}, weight={weight}")
    except Exception as e:
        logger.error(f"Error during pathfinding: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при поиске пути: {e}")

    if not path:
        logger.warning(f"No path found from {start} to {end}")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"Path: {path}, Weight: {weight}")
    try:
        instructions = generate_text_instructions(path, graph, db, view_floor)
    except Exception as e:
        logger.error(f"Error generating instructions: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации инструкций: {e}")

    route = []
    current_floor_number = None
    floor_points = []
    prev_vertex = None

    for i, vertex in enumerate(path):
        vertex_data = graph.get_vertex_data(vertex)
        coords = vertex_data["coords"]
        floor_id = coords[2]
        building_id = vertex_data["building_id"]
        try:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            if floor:
                floor_number = floor.floor_number if building_id is not None else 1
            else:
                logger.warning(f"Floor with id {floor_id} not found, assuming floor_id as floor number")
                floor_number = floor_id if building_id is not None else 1
        except Exception as e:
            logger.error(f"Error retrieving floor for floor_id {floor_id}: {e}")
            floor_number = floor_id if building_id is not None else 1

        logger.info(f"Processing vertex {vertex}, coords={coords}, floor={floor_number}, building_id={building_id}")

        # Включаем все вершины сегментов и outdoor при переходах
        if i > 0 and prev_vertex:
            prev_data = graph.get_vertex_data(prev_vertex)
            curr_data = vertex_data
            prev_is_outdoor = prev_data["building_id"] is None
            curr_is_outdoor = building_id is None
            prev_is_segment = prev_vertex.startswith("segment_")
            curr_is_segment = vertex.startswith("segment_")

            if (prev_is_segment and curr_is_outdoor) or (prev_is_outdoor and curr_is_segment):
                # Добавляем недостающие start/end вершины сегмента или outdoor
                if prev_is_segment:
                    seg_id = int(prev_vertex.split("_")[1])
                    start_vertex = f"segment_{seg_id}_start"
                    end_vertex = f"segment_{seg_id}_end"
                    if start_vertex in graph.vertices and start_vertex not in [p["vertex"] for p in floor_points]:
                        start_data = graph.get_vertex_data(start_vertex)
                        floor_points.append({"x": start_data["coords"][0], "y": start_data["coords"][1], "vertex": start_vertex})
                    if end_vertex in graph.vertices and end_vertex not in [p["vertex"] for p in floor_points]:
                        end_data = graph.get_vertex_data(end_vertex)
                        floor_points.append({"x": end_data["coords"][0], "y": end_data["coords"][1], "vertex": end_vertex})
                elif curr_is_segment:
                    seg_id = int(vertex.split("_")[1])
                    start_vertex = f"segment_{seg_id}_start"
                    end_vertex = f"segment_{seg_id}_end"
                    if start_vertex in graph.vertices and start_vertex not in [p["vertex"] for p in floor_points]:
                        start_data = graph.get_vertex_data(start_vertex)
                        floor_points.append({"x": start_data["coords"][0], "y": start_data["coords"][1], "vertex": start_vertex})
                    if end_vertex in graph.vertices and end_vertex not in [p["vertex"] for p in floor_points]:
                        end_data = graph.get_vertex_data(end_vertex)
                        floor_points.append({"x": end_data["coords"][0], "y": end_data["coords"][1], "vertex": end_vertex})

        point = {"x": coords[0], "y": coords[1], "vertex": vertex}
        if current_floor_number is None:
            current_floor_number = floor_number
            floor_points.append(point)
        elif floor_number != current_floor_number:
            if floor_points:
                route.append({"floor": current_floor_number, "points": simplify_route(floor_points)})
            floor_points = [point]
            current_floor_number = floor_number
        else:
            floor_points.append(point)

        prev_vertex = vertex

    if floor_points:
        route.append({"floor": current_floor_number, "points": simplify_route(floor_points)})

    logger.info(f"Generated route: {route}")
    return {"path": route, "weight": weight, "instructions": instructions}