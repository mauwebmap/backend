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
from collections import defaultdict

logger = logging.getLogger(__name__)

def find_closest_point_on_segment(room_x: float, room_y: float, start_x: float, start_y: float, end_x: float, end_y: float) -> tuple:
    """Находит ближайшую точку на сегменте от (start_x, start_y) до (end_x, end_y) к точке (room_x, room_y)."""
    seg_dx = end_x - start_x
    seg_dy = end_y - start_y
    seg_len_sq = seg_dx ** 2 + seg_dy ** 2

    if seg_len_sq == 0:
        logger.warning(f"Segment length is zero for start ({start_x}, {start_y}) to end ({end_x}, {end_y})")
        return start_x, start_y

    dx = room_x - start_x
    dy = room_y - start_y
    t = max(0, min(1, (dx * seg_dx + dy * seg_dy) / seg_len_sq))
    logger.debug(f"Calculated t={t} for room ({room_x}, {room_y}) on segment ({start_x}, {start_y}) to ({end_x}, {end_y})")

    closest_x = start_x + t * seg_dx
    closest_y = start_y + t * seg_dy
    logger.debug(f"Closest point: ({closest_x}, {closest_y})")
    return closest_x, closest_y

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()

    # Извлекаем комнаты по ID
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

    # Извлекаем floor_number
    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    if not start_floor or not end_floor:
        logger.warning(f"Floor data missing for floor_id {start_room.floor_id} or {end_room.floor_id}, using floor_id as floor_number")
        start_floor_number = start_room.floor_id
        end_floor_number = end_room.floor_id
    else:
        start_floor_number = start_floor.floor_number
        end_floor_number = end_floor.floor_number
    logger.info(f"Assigned floor_number: room_{start_id}={start_floor_number}, room_{end_id}={end_floor_number}")

    # Добавляем вершины для начальной и конечной комнаты
    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_floor_number), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_floor_number), "building_id": end_room.building_id})

    # Определяем этажи и здания
    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Relevant building IDs: {building_ids}")
    logger.info(f"Relevant floor IDs: {floor_ids}")

    # Добавляем сегменты и phantom-вершины
    segments_by_floor = defaultdict(list)
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        if not seg_floor:
            logger.warning(f"Floor data missing for segment floor_id {segment.floor_id}, using floor_id as floor_number")
            seg_floor_number = segment.floor_id
        else:
            seg_floor_number = seg_floor.floor_number
        logger.info(f"Segment {segment.id} assigned floor_number: {seg_floor_number}")

        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, seg_floor_number), "building_id": segment.building_id})
        weight = math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

        # Phantom-вершины для start и end с ближайшей точкой на сегменте
        for room_id, room in [(start_id, start_room), (end_id, end_room)]:
            room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
            room_floor_number = room.floor_id if not room_floor else room_floor.floor_number
            if room_floor_number == seg_floor_number and room.building_id == segment.building_id:
                room_vertex = f"room_{room_id}"
                phantom_vertex = f"phantom_room_{room_id}_segment_{segment.id}"

                # Находим ближайшую точку на сегменте
                closest_x, closest_y = find_closest_point_on_segment(
                    room.cab_x, room.cab_y,
                    segment.start_x, segment.start_y,
                    segment.end_x, segment.end_y
                )
                graph.add_vertex(phantom_vertex, {"coords": (closest_x, closest_y, seg_floor_number), "building_id": segment.building_id})

                # Вес от комнаты до phantom-вершины
                dist_to_phantom = math.sqrt((room.cab_x - closest_x) ** 2 + (room.cab_y - closest_y) ** 2)
                graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom, {"type": "phantom"})

                # Веса от phantom-вершины до start и end сегмента
                dist_to_start = math.sqrt((closest_x - segment.start_x) ** 2 + (closest_y - segment.start_y) ** 2)
                dist_to_end = math.sqrt((closest_x - segment.end_x) ** 2 + (closest_y - segment.end_y) ** 2)
                graph.add_edge(phantom_vertex, start_vertex, dist_to_start, {"type": "phantom"})
                graph.add_edge(phantom_vertex, end_vertex, dist_to_end, {"type": "phantom"})
                logger.info(f"Added phantom vertex: {phantom_vertex} -> ({closest_x}, {closest_y}, {seg_floor_number})")

        segments_by_floor[(seg_floor_number, segment.building_id)].append((segment.id, start_vertex, end_vertex))

    # Универсальное соединение сегментов на одном этаже
    for (floor_number, building_id), segments in segments_by_floor.items():
        existing_connections = {(conn.from_segment_id, conn.to_segment_id) for conn in db.query(Connection).filter(Connection.type == "лестница").all() if conn.from_segment_id and conn.to_segment_id}
        for i, (seg_id1, start1, end1) in enumerate(segments):
            for j, (seg_id2, start2, end2) in enumerate(segments):
                if i != j and (seg_id1, seg_id2) not in existing_connections:
                    end1_coords = graph.get_vertex_data(end1)["coords"]
                    start2_coords = graph.get_vertex_data(start2)["coords"]
                    weight = math.sqrt((end1_coords[0] - start2_coords[0]) ** 2 + (end1_coords[1] - start2_coords[1]) ** 2)
                    if weight < 100:
                        graph.add_edge(end1, start2, weight, {"type": "corridor"})
                        logger.info(f"Added universal corridor edge: {end1} <-> {start2}, weight={weight}")

    # Добавляем outdoor-сегменты
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        graph.add_vertex(start_vertex, {"coords": (outdoor.start_x, outdoor.start_y, 1), "building_id": None})
        graph.add_vertex(end_vertex, {"coords": (outdoor.end_x, outdoor.end_y, 1), "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Соединения строго по базе
    for conn in db.query(Connection).filter(Connection.type.in_(["улица", "дверь", "лестница"])).all():
        if conn.from_segment_id and conn.to_outdoor_id:
            seg_vertex = f"segment_{conn.from_segment_id}_end"
            out_vertex = f"outdoor_{conn.to_outdoor_id}_start"
            if seg_vertex in graph.vertices and out_vertex in graph.vertices:
                graph.add_edge(seg_vertex, out_vertex, conn.weight or 2.0, {"type": "outdoor start"})
                logger.info(f"Added edge (outdoor start): {seg_vertex} <-> {out_vertex}, weight={conn.weight or 2.0}")
        if conn.from_outdoor_id and conn.to_segment_id:
            out_vertex = f"outdoor_{conn.from_outdoor_id}_end"
            seg_vertex = f"segment_{conn.to_segment_id}_start"
            if out_vertex in graph.vertices and seg_vertex in graph.vertices:
                graph.add_edge(out_vertex, seg_vertex, conn.weight or 2.0, {"type": "outdoor end"})
                logger.info(f"Added edge (outdoor end): {out_vertex} <-> {seg_vertex}, weight={conn.weight or 2.0}")
        if conn.from_segment_id and conn.to_segment_id:
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, conn.weight or 2.0, {"type": "ladder"})
                logger.info(f"Added edge (ladder): {from_vertex} <-> {to_vertex}, weight={conn.weight or 2.0}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph