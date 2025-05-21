from app.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
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
    if curr_dx == 0 and curr_dy == 0:
        return "вперёд"

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
    distance = sqrt(curr_dx ** 2 + curr_dy ** 2)
    # Игнорируем мелкие движения (< 10 единиц) и повороты < 30 градусов
    if distance < 10 or abs(angle_diff) < 30:
        return "вперёд" if prev_direction == "вперёд" else prev_direction
    return "поверните налево" if -180 < angle_diff <= -30 else "поверните направо"

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

def generate_text_instructions(path: list, graph: dict, db: Session) -> list:
    instructions = []
    prev_prev_coords = None
    prev_coords = None
    prev_vertex = None
    prev_floor = None
    current_instruction = []
    last_turn = None

    for i, vertex in enumerate(path):
        coords = graph.vertices[vertex]
        floor_id = coords[2]
        floor_number = db.query(Floor).filter(Floor.id == floor_id).first().floor_number if floor_id != 0 else 0
        logger.info(f"Processing vertex {vertex}, coords={coords}, floor={floor_number}")

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
            prev_segment_id = int(prev_vertex.split("_")[1]) if prev_vertex.startswith("segment_") else None
            curr_segment_id = int(vertex.split("_")[1]) if vertex.startswith("segment_") else None
            if prev_segment_id and curr_segment_id:
                connection = db.query(Connection).filter(
                    Connection.type == "лестница",
                    ((Connection.from_segment_id == prev_segment_id) & (Connection.to_segment_id == curr_segment_id)) |
                    ((Connection.from_segment_id == curr_segment_id) & (Connection.to_segment_id == prev_segment_id))
                ).first()
                if connection:
                    instructions.append(f"Дойдите до лестницы и {'поднимитесь' if prev_floor < floor_number else 'спуститесь'} на {floor_number}-й этаж")
            prev_prev_coords = None
            last_turn = None

        if prev_coords:
            direction = get_direction(prev_prev_coords, prev_coords, (coords[0], coords[1]), i=i)
            logger.info(f"Direction for {vertex}: {direction}")
            if direction.startswith("поверните"):
                if last_turn and "поверните" in last_turn.lower():
                    current_instruction[-1] = direction  # Заменяем предыдущий поворот
                else:
                    current_instruction.append(direction)
                last_turn = direction
            elif direction != "вперёд" and not last_turn:
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

    return instructions

def simplify_route(points: list) -> list:
    """Упрощает маршрут, удаляя избыточные точки с малым отклонением."""
    if len(points) < 3:
        return points
    simplified = [points[0]]
    for i in range(1, len(points) - 1):
        prev_point = points[i - 1]
        curr_point = points[i]
        next_point = points[i + 1]
        dx1, dy1 = curr_point["x"] - prev_point["x"], curr_point["y"] - prev_point["y"]
        dx2, dy2 = next_point["x"] - curr_point["x"], next_point["y"] - curr_point["y"]
        # Удаляем точку, если она близка к прямой линии (угол почти 180°)
        if abs(atan2(dy2, dx2) - atan2(dy1, dx1)) < 0.1:  # Малый угол отклонения
            continue
        simplified.append(curr_point)
    simplified.append(points[-1])
    return simplified

@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")
    path, weight, graph = find_path(db, start, end, return_graph=True)
    if not path:
        logger.warning(f"No path found from {start} to {end}")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"Path: {path}, Weight: {weight}")
    instructions = generate_text_instructions(path, graph, db)

    route = []
    current_floor_number = None
    floor_points = []

    for i, vertex in enumerate(path):
        coords = graph.vertices[vertex]
        floor_id = coords[2]
        floor_number = db.query(Floor).filter(Floor.id == floor_id).first().floor_number if floor_id != 0 else 0
        logger.info(f"Processing vertex {vertex}, coords={coords}, floor={floor_number}")

        point = {"x": coords[0], "y": coords[1]}
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

    if floor_points:
        route.append({"floor": current_floor_number, "points": simplify_route(floor_points)})

    logger.info(f"Generated route: {route}")
    return {"path": route, "weight": weight, "instructions": instructions}