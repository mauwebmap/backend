# backend/app/map/utils/builder.py
from .graph import Graph
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from sqlalchemy.orm import Session
import logging
import math

logger = logging.getLogger(__name__)

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

    # Добавляем вершины комнат
    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_room.floor_id), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_room.floor_id), "building_id": end_room.building_id})

    # Определяем этажи и здания
    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Relevant building IDs: {building_ids}")
    logger.info(f"Relevant floor IDs: {floor_ids}")

    # Добавляем сегменты и phantom-вершины для всех комнат на соответствующих этажах
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, segment.floor_id), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, segment.floor_id), "building_id": segment.building_id})
        weight = math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

        # Phantom-вершины для всех комнат на этом этаже
        rooms = db.query(Room).filter(Room.floor_id == segment.floor_id, Room.building_id == segment.building_id).all()
        for room in rooms:
            room_vertex = f"room_{room.id}"
            if room_vertex not in graph.vertices:
                graph.add_vertex(room_vertex, {"coords": (room.cab_x, room.cab_y, room.floor_id), "building_id": room.building_id})
            phantom_vertex = f"phantom_room_{room.id}_segment_{segment.id}"
            graph.add_vertex(phantom_vertex, {"coords": (room.cab_x, room.cab_y, room.floor_id), "building_id": room.building_id})
            dist_start = math.sqrt((room.cab_x - segment.start_x) ** 2 + (room.cab_y - segment.start_y) ** 2)
            dist_end = math.sqrt((room.cab_x - segment.end_x) ** 2 + (room.cab_y - segment.end_y) ** 2)
            graph.add_edge(room_vertex, phantom_vertex, min(dist_start, dist_end), {"type": "phantom"})
            graph.add_edge(phantom_vertex, start_vertex, dist_start, {"type": 'phantom'})
            graph.add_edge(phantom_vertex, end_vertex, dist_end, {"type": 'phantom'})
            logger.info(f"Added phantom vertex: {phantom_vertex} -> ({room.cab_x}, {room.cab_y}, {room.floor_id})")

    # Добавляем outdoor-сегменты
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        graph.add_vertex(start_vertex, {"coords": (outdoor.start_x, outdoor.start_y, 1), "building_id": None})
        graph.add_vertex(end_vertex, {"coords": (outdoor.end_x, outdoor.end_y, 1), "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Соединения между outdoor-сегментами
    for conn in db.query(Connection).filter(Connection.type == "улица").all():
        if conn.from_outdoor_id and conn.to_outdoor_id:
            from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
            to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, conn.weight or 10.0, {"type": "street"})
                logger.info(f"Added edge (street): {from_vertex} <-> {to_vertex}, weight={conn.weight or 10.0}")

    # Соединения между сегментами и outdoor
    for conn in db.query(Connection).filter(Connection.type.in_(["дверь", "улица"])).all():
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

    # Лестницы между этажами
    for conn in db.query(Connection).filter(Connection.type == "лестница").all():
        if conn.from_segment_id and conn.to_segment_id:
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, conn.weight or 2.0, {"type": "ladder"})
                logger.info(f"Added edge (ladder): {from_vertex} <-> {to_vertex}, weight={conn.weight or 2.0}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    logger.info(f"Final vertices: {list(graph.vertices.keys())}")
    logger.info(f"Final edges: {graph.edges}")
    return graph