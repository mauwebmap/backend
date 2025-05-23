# backend/app/map/utils/builder.py
from .graph import Graph
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.models.floor import Floor
from sqlalchemy.orm import Session
import logging
import math

logger = logging.getLogger(__name__)

def find_closest_point_on_segment(x: float, y: float, start_x: float, start_y: float, end_x: float, end_y: float) -> tuple:
    seg_dx = end_x - start_x
    seg_dy = end_y - start_y
    seg_len_sq = seg_dx ** 2 + seg_dy ** 2

    if seg_len_sq == 0:
        logger.warning(f"Segment length is zero for start ({start_x}, {start_y}) to end ({end_x}, {end_y})")
        return start_x, start_y

    dx = x - start_x
    dy = y - start_y
    t = max(0, min(1, (dx * seg_dx + dy * seg_dy) / seg_len_sq))
    closest_x = start_x + t * seg_dx
    closest_y = start_y + t * seg_dy
    logger.debug(f"Closest point: ({closest_x}, {closest_y})")
    return closest_x, closest_y

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()

    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
        start_room = db.query(Room).filter(Room.id == start_id).first()
        end_room = db.query(Room).filter(Room.id == end_id).first()
        if not start_room or not end_room:
            raise ValueError(f"Room with id {start_id} or {end_id} not found")
    except ValueError as e:
        logger.error(f"Failed to parse room IDs from {start} or {end}: {e}")
        raise ValueError(f"Invalid room format, expected room_<id>, got {start} or {end}")

    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    start_floor_number = start_room.floor_id if not start_floor else start_floor.floor_number
    end_floor_number = end_room.floor_id if not end_floor else end_floor.floor_number
    logger.info(f"Assigned floor_number: room_{start_id}={start_floor_number}, room_{end_id}={end_floor_number}")

    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_floor_number), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_floor_number), "building_id": end_room.building_id})

    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Relevant building IDs: {building_ids}")
    logger.info(f"Relevant floor IDs: {floor_ids}")

    # Добавляем сегменты
    segments = {}
    floor_numbers = {}
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        seg_floor_number = segment.floor_id if not seg_floor else seg_floor.floor_number
        floor_numbers[segment.id] = seg_floor_number
        logger.info(f"Segment {segment.id} assigned floor_number: {seg_floor_number}")

        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, seg_floor_number), "building_id": segment.building_id})
        weight = math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})
        graph.add_edge(end_vertex, start_vertex, weight, {"type": "segment"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")
        segments[segment.id] = (start_vertex, end_vertex)

    # Добавляем outdoor-сегменты
    outdoor_segments = {}
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        coords_start = (outdoor.start_x, outdoor.start_y, 1)
        coords_end = (outdoor.end_x, outdoor.end_y, 1)
        graph.add_vertex(start_vertex, {"coords": coords_start, "building_id": None})
        graph.add_vertex(end_vertex, {"coords": coords_end, "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
        graph.add_edge(end_vertex, start_vertex, weight, {"type": "outdoor"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")
        outdoor_segments[outdoor.id] = (start_vertex, end_vertex)

    # Добавляем фантомные точки для комнат
    for room_id, room in [(start_id, start_room), (end_id, end_room)]:
        room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        room_floor_number = room.floor_id if not room_floor else room_floor.floor_number
        room_vertex = f"room_{room_id}"
        connections = db.query(Connection).filter(Connection.room_id == room_id).all()
        for conn in connections:
            if conn.segment_id and conn.segment_id in segments:
                segment_start, segment_end = segments[conn.segment_id]
                closest_x, closest_y = find_closest_point_on_segment(
                    room.cab_x, room.cab_y,
                    graph.get_vertex_data(segment_start)["coords"][0],
                    graph.get_vertex_data(segment_start)["coords"][1],
                    graph.get_vertex_data(segment_end)["coords"][0],
                    graph.get_vertex_data(segment_end)["coords"][1]
                )
                phantom_vertex = f"phantom_room_{room_id}_segment_{conn.segment_id}"
                graph.add_vertex(phantom_vertex, {"coords": (closest_x, closest_y, room_floor_number), "building_id": room.building_id})
                weight_to_room = conn.weight or 2.0
                weight_to_start = math.sqrt((closest_x - graph.get_vertex_data(segment_start)["coords"][0]) ** 2 + (closest_y - graph.get_vertex_data(segment_start)["coords"][1]) ** 2)
                weight_to_end = math.sqrt((closest_x - graph.get_vertex_data(segment_end)["coords"][0]) ** 2 + (closest_y - graph.get_vertex_data(segment_end)["coords"][1]) ** 2)
                graph.add_edge(room_vertex, phantom_vertex, weight_to_room, {"type": "phantom"})
                graph.add_edge(phantom_vertex, room_vertex, weight_to_room, {"type": "phantom"})
                graph.add_edge(phantom_vertex, segment_start, weight_to_start, {"type": "phantom"})
                graph.add_edge(phantom_vertex, segment_end, weight_to_end, {"type": "phantom"})
                logger.info(f"Added phantom vertex: {phantom_vertex} -> ({closest_x}, {closest_y}, {room_floor_number})")

    # Добавляем фантомные точки для переходов между сегментами и лестниц
    for conn in db.query(Connection).filter(Connection.type.in_(["улица", "дверь", "лестница"])).all():
        if conn.from_segment_id and conn.to_segment_id and conn.from_segment_id in segments and conn.to_segment_id in segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_coords = graph.get_vertex_data(from_end)["coords"]
            to_coords = graph.get_vertex_data(to_start)["coords"]
            dx = to_coords[0] - from_coords[0]
            dy = to_coords[1] - from_coords[1]
            dist = math.sqrt(dx ** 2 + dy ** 2)
            if dist > 0:
                t = 1.0 / dist if dist > 1 else 0.5  # Фантомная точка ближе к to_start
                phantom_x = to_coords[0] - t * dx
                phantom_y = to_coords[1] - t * dy
                phantom_vertex = f"phantom_segment_{conn.from_segment_id}_segment_{conn.to_segment_id}"
                floor_number = floor_numbers[conn.to_segment_id]
                graph.add_vertex(phantom_vertex, {"coords": (phantom_x, phantom_y, floor_number), "building_id": None})
                weight_to_from = math.sqrt((phantom_x - from_coords[0]) ** 2 + (phantom_y - from_coords[1]) ** 2)
                weight_to_to = math.sqrt((phantom_x - to_coords[0]) ** 2 + (phantom_y - to_coords[1]) ** 2)
                graph.add_edge(from_end, phantom_vertex, weight_to_from, {"type": "phantom"})
                graph.add_edge(phantom_vertex, to_start, weight_to_to, {"type": "phantom"})
                graph.add_edge(to_end, phantom_vertex, weight_to_from, {"type": "phantom"})
                graph.add_edge(phantom_vertex, from_start, weight_to_to, {"type": "phantom"})
                logger.info(f"Added phantom vertex: {phantom_vertex} -> ({phantom_x}, {phantom_y}, {floor_number})")

        elif conn.from_segment_id and conn.to_outdoor_id and conn.from_segment_id in segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            weight = conn.weight or 10.0
            graph.add_edge(from_end, to_start, weight, {"type": conn.type})
            graph.add_edge(to_end, from_start, weight, {"type": conn.type})
            logger.info(f"Added edge ({conn.type}): {from_end} <-> {to_start}, weight={weight}")

        elif conn.from_outdoor_id and conn.to_segment_id and conn.from_outdoor_id in outdoor_segments and conn.to_segment_id in segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = segments[conn.to_segment_id]
            weight = conn.weight or 10.0
            graph.add_edge(from_end, to_start, weight, {"type": conn.type})
            graph.add_edge(to_end, from_start, weight, {"type": conn.type})
            logger.info(f"Added edge ({conn.type}): {from_end} <-> {to_start}, weight={weight}")

        elif conn.from_outdoor_id and conn.to_outdoor_id and conn.from_outdoor_id in outdoor_segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_coords = graph.get_vertex_data(from_end)["coords"]
            to_coords = graph.get_vertex_data(to_start)["coords"]
            dx = to_coords[0] - from_coords[0]
            dy = to_coords[1] - from_coords[1]
            dist = math.sqrt(dx ** 2 + dy ** 2)
            if dist > 0:
                t = 1.0 / dist if dist > 1 else 0.5
                phantom_x = to_coords[0] - t * dx
                phantom_y = to_coords[1] - t * dy
                phantom_vertex = f"phantom_outdoor_{conn.from_outdoor_id}_outdoor_{conn.to_outdoor_id}"
                graph.add_vertex(phantom_vertex, {"coords": (phantom_x, phantom_y, 1), "building_id": None})
                weight_to_from = math.sqrt((phantom_x - from_coords[0]) ** 2 + (phantom_y - from_coords[1]) ** 2)
                weight_to_to = math.sqrt((phantom_x - to_coords[0]) ** 2 + (phantom_y - to_coords[1]) ** 2)
                graph.add_edge(from_end, phantom_vertex, weight_to_from, {"type": "phantom"})
                graph.add_edge(phantom_vertex, to_start, weight_to_to, {"type": "phantom"})
                graph.add_edge(to_end, phantom_vertex, weight_to_from, {"type": "phantom"})
                graph.add_edge(phantom_vertex, from_start, weight_to_to, {"type": "phantom"})
                logger.info(f"Added phantom vertex: {phantom_vertex} -> ({phantom_x}, {phantom_y}, 1)")

        # Добавляем лестницы между этажами
        if conn.type == "лестница":
            if conn.from_segment_id and conn.to_segment_id:
                from_start, from_end = segments[conn.from_segment_id]
                to_start, to_end = segments[conn.to_segment_id]
                from_floor = floor_numbers[conn.from_segment_id]
                to_floor = floor_numbers[conn.to_segment_id]
                if from_floor != to_floor:
                    weight = conn.weight or 10.0
                    graph.add_edge(from_end, to_start, weight, {"type": "лестница"})
                    graph.add_edge(to_end, from_start, weight, {"type": "лестница"})
                    logger.info(f"Added stair edge: {from_end} <-> {to_start}, weight={weight}, floors {from_floor} -> {to_floor}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph