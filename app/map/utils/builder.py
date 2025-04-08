# app/map/pathfinder/builder.py
import logging
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt

logger = logging.getLogger(__name__)

VALID_TYPES = {"room", "segment", "outdoor"}

def parse_vertex_id(vertex: str):
    """Парсинг ID вершины: room_1 -> (room, 1)"""
    try:
        type_, id_ = vertex.split("_", 1)
        if type_ not in VALID_TYPES:
            raise ValueError(f"Неверный тип вершины: {type_}")
        return type_, int(id_)
    except (ValueError, IndexError) as e:
        raise ValueError(f"Неверный формат ID вершины {vertex}: {e}")

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    """Добавление вершины в граф"""
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room:
            raise ValueError(f"Комната {vertex} не найдена")
        graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
        logger.debug(f"[add_vertex_to_graph] Added room vertex: {vertex} -> {(room.cab_x, room.cab_y, room.floor_id)}")
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment:
            raise ValueError(f"Сегмент {vertex} не найден")
        graph.add_vertex(f"segment_{id_}_start", (segment.start_x, segment.start_y, segment.floor_id))
        graph.add_vertex(f"segment_{id_}_end", (segment.end_x, segment.end_y, segment.floor_id))
        logger.debug(f"[add_vertex_to_graph] Added segment vertices: segment_{id_}_start -> {(segment.start_x, segment.start_y, segment.floor_id)}, segment_{id_}_end -> {(segment.end_x, segment.end_y, segment.floor_id)}")
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor:
            raise ValueError(f"Уличный сегмент {vertex} не найден")
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, 0))
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, 0))
        logger.debug(f"[add_vertex_to_graph] Added outdoor segment vertices: outdoor_{id_}_start -> {(outdoor.start_x, outdoor.start_y, 0)}, outdoor_{id_}_end -> {(outdoor.end_x, outdoor.end_y, 0)}")

def get_relevant_buildings(db: Session, start: str, end: str) -> set:
    """Получение списка зданий, связанных с начальной и конечной точками"""
    building_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room:
                building_ids.add(room.building_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment:
                building_ids.add(segment.building_id)
    logger.debug(f"[get_relevant_buildings] Building IDs: {building_ids}")
    return building_ids

def get_relevant_floors(db: Session, start: str, end: str) -> set:
    """Получение списка этажей, связанных с начальной и конечной точками"""
    floor_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room:
                floor_ids.add(room.floor_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment:
                floor_ids.add(segment.floor_id)
    logger.debug(f"[get_relevant_floors] Floor IDs: {floor_ids}")
    return floor_ids

def build_graph(db: Session, start: str, end: str) -> Graph:
    """Построение графа для поиска пути"""
    graph = Graph()
    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    building_ids = get_relevant_buildings(db, start, end)
    floor_ids = get_relevant_floors(db, start, end)

    # Загрузка всех комнат в зданиях и на этажах
    rooms = db.query(Room).filter(
        Room.building_id.in_(building_ids),
        Room.floor_id.in_(floor_ids)
    ).all()
    logger.debug(f"[build_graph] Loaded rooms: {[f'id={room.id}, building_id={room.building_id}, floor_id={room.floor_id}' for room in rooms]}")
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
            logger.debug(f"[build_graph] Added room vertex: {vertex} -> {(room.cab_x, room.cab_y, room.floor_id)}")

    # Загрузка всех сегментов в зданиях и на этажах
    segments = db.query(Segment).filter(
        Segment.building_id.in_(building_ids),
        Segment.floor_id.in_(floor_ids)
    ).all()
    logger.debug(f"[build_graph] Loaded segments: {[f'id={segment.id}, building_id={segment.building_id}, floor_id={segment.floor_id}' for segment in segments]}")
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.debug(f"[build_graph] Added segment vertices: {start_vertex} -> {(segment.start_x, segment.start_y, segment.floor_id)}, {end_vertex} -> {(segment.end_x, segment.end_y, segment.floor_id)}")
        logger.debug(f"[build_graph] Added edge: {start_vertex} -> {end_vertex}, weight={weight}")

    # Загрузка уличных сегментов
    outdoor_segments = db.query(OutdoorSegment).all()
    logger.debug(f"[build_graph] Loaded outdoor segments: {[f'id={outdoor.id}' for outdoor in outdoor_segments]}")
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 0))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 0))
        weight = sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.debug(f"[build_graph] Added outdoor segment vertices: {start_vertex} -> {(outdoor.start_x, outdoor.start_y, 0)}, {end_vertex} -> {(outdoor.end_x, outdoor.end_y, 0)}")
        logger.debug(f"[build_graph] Added edge: {start_vertex} -> {end_vertex}, weight={weight}")

    # Загрузка всех соединений
    connections = db.query(Connection).filter(
        (Connection.room_id.in_([r.id for r in rooms])) |
        (Connection.segment_id.in_([s.id for s in segments])) |
        (Connection.from_segment_id.in_([s.id for s in segments])) |
        (Connection.to_segment_id.in_([s.id for s in segments])) |
        (Connection.from_outdoor_id.in_([o.id for o in outdoor_segments])) |
        (Connection.to_outdoor_id.in_([o.id for o in outdoor_segments]))
    ).all()
    logger.debug(f"[build_graph] Loaded connections: {[f'id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}, from_segment_id={conn.from_segment_id}, to_segment_id={conn.to_segment_id}' for conn in connections]}")

    # Добавление рёбер на основе соединений
    for conn in connections:
        logger.debug(f"[build_graph] Processing connection: id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}, from_segment_id={conn.from_segment_id}, to_segment_id={conn.to_segment_id}")
        weight = conn.weight if conn.weight is not None else 1

        if conn.type.lower() == "door" and conn.room_id and conn.segment_id:
            room_vertex = f"room_{conn.room_id}"
            segment = db.query(Segment).filter(Segment.id == conn.segment_id).first()
            if not segment:
                logger.warning(f"[build_graph] Segment {conn.segment_id} not found for connection {conn.id}")
                continue
            segment_start = f"segment_{conn.segment_id}_start"
            segment_end = f"segment_{conn.segment_id}_end"
            if room_vertex not in graph.vertices:
                logger.warning(f"[build_graph] Room vertex {room_vertex} not in graph for connection {conn.id}")
                continue
            if segment_start not in graph.vertices or segment_end not in graph.vertices:
                logger.warning(f"[build_graph] Segment vertices {segment_start} or {segment_end} not in graph for connection {conn.id}")
                continue

            room_coords = graph.vertices[room_vertex]
            start_coords = graph.vertices[segment_start]
            end_coords = graph.vertices[segment_end]
            dist_to_start = sqrt((room_coords[0] - start_coords[0]) ** 2 + (room_coords[1] - start_coords[1]) ** 2)
            dist_to_end = sqrt((room_coords[0] - end_coords[0]) ** 2 + (room_coords[1] - end_coords[1]) ** 2)
            target_vertex = segment_start if dist_to_start <= dist_to_end else segment_end
            target_coords = start_coords if dist_to_start <= dist_to_end else end_coords

            graph.add_edge(room_vertex, target_vertex, weight)
            logger.debug(f"[build_graph] Adding edge: {room_vertex} -> {target_vertex}, weight={weight}, from_coords={room_coords}, to_coords={target_coords}")

        elif conn.type.lower() == "stairs" and conn.from_segment_id and conn.to_segment_id:
            from_segment = db.query(Segment).filter(Segment.id == conn.from_segment_id).first()
            to_segment = db.query(Segment).filter(Segment.id == conn.to_segment_id).first()
            if not from_segment or not to_segment:
                logger.warning(f"[build_graph] Segment {conn.from_segment_id} or {conn.to_segment_id} not found for connection {conn.id}")
                continue
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex not in graph.vertices or to_vertex not in graph.vertices:
                logger.warning(f"[build_graph] Segment vertices {from_vertex} or {to_vertex} not in graph for connection {conn.id}")
                continue
            graph.add_edge(from_vertex, to_vertex, weight)
            logger.debug(f"[build_graph] Adding edge: {from_vertex} -> {to_vertex}, weight={weight}")

        elif conn.type.lower() == "outdoor" and conn.from_segment_id and conn.to_outdoor_id:
            from_segment = db.query(Segment).filter(Segment.id == conn.from_segment_id).first()
            to_outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == conn.to_outdoor_id).first()
            if not from_segment or not to_outdoor:
                logger.warning(f"[build_graph] Segment {conn.from_segment_id} or outdoor {conn.to_outdoor_id} not found for connection {conn.id}")
                continue
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
            if from_vertex not in graph.vertices or to_vertex not in graph.vertices:
                logger.warning(f"[build_graph] Segment vertex {from_vertex} or outdoor vertex {to_vertex} not in graph for connection {conn.id}")
                continue
            graph.add_edge(from_vertex, to_vertex, weight)
            logger.debug(f"[build_graph] Adding edge: {from_vertex} -> {to_vertex}, weight={weight}")

    logger.debug(f"Vertices: {graph.vertices}")
    logger.debug(f"Edges: {dict(graph.edges)}")
    return graph