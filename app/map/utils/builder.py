from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt, atan2, degrees
import logging

logger = logging.getLogger(__name__)

VALID_TYPES = {"room", "segment", "outdoor"}

def parse_vertex_id(vertex: str):
    type_, id_ = vertex.split("_", 1)
    if type_ not in VALID_TYPES:
        raise ValueError(f"Неверный тип вершины: {type_}")
    return type_, int(id_)

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple) -> tuple:
    rx, ry, rfloor = room_coords
    sx, sy, sfloor = segment_start
    ex, ey, efloor = segment_end

    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return sx, sy, sfloor

    # Нормализованный вектор сегмента
    length = sqrt(length_squared)
    nx, ny = dx / length, dy / length

    # Проекция комнаты на линию сегмента
    dot_product = (rx - sx) * nx + (ry - sy) * ny
    t = max(0, min(1, dot_product / length))

    # Фантомная точка с небольшим смещением вдоль сегмента
    phantom_x = sx + t * dx
    phantom_y = sy + t * dy
    # Учитываем этаж комнаты, если он отличается
    phantom_floor = rfloor if abs(rfloor - sfloor) <= 1 else sfloor

    # Корректировка, чтобы избежать слишком близкого примыкания
    offset = 10  # Минимальное расстояние от конца сегмента
    if t < offset / length:
        phantom_x, phantom_y = sx + nx * offset, sy + ny * offset
    elif t > 1 - offset / length:
        phantom_x, phantom_y = ex - nx * offset, ey - ny * offset

    return phantom_x, phantom_y, phantom_floor

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room:
            logger.error(f"Комната {vertex} не найдена в базе")
            raise ValueError(f"Комната {vertex} не найдена")
        graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
        logger.info(f"Added room vertex: {vertex} -> {(room.cab_x, room.cab_y, room.floor_id)}")
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment:
            logger.error(f"Сегмент {vertex} не найден в базе")
            raise ValueError(f"Сегмент {vertex} не найден")
        graph.add_vertex(f"segment_{id_}_start", (segment.start_x, segment.start_y, segment.floor_id))
        graph.add_vertex(f"segment_{id_}_end", (segment.end_x, segment.end_y, segment.floor_id))
        logger.info(f"Added segment vertices: segment_{id_}_start -> {(segment.start_x, segment.start_y, segment.floor_id)}, segment_{id_}_end -> {(segment.end_x, segment.end_y, segment.floor_id)}")
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor:
            logger.error(f"Уличный сегмент {vertex} не найден в базе")
            raise ValueError(f"Уличный сегмент {vertex} не найден")
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, 1))
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, 1))
        logger.info(f"Added outdoor segment vertices: outdoor_{id_}_start -> {(outdoor.start_x, outdoor.start_y, 1)}, outdoor_{id_}_end -> {(outdoor.end_x, outdoor.end_y, 1)}")

def get_relevant_buildings(db: Session, start: str, end: str) -> set:
    building_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room and room.building_id:
                building_ids.add(room.building_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment and segment.building_id:
                building_ids.add(segment.building_id)
    logger.info(f"Relevant building IDs: {building_ids}")
    return building_ids

def get_relevant_floors(db: Session, start: str, end: str) -> set:
    floor_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room and room.floor_id:
                floor_ids.add(room.floor_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment and segment.floor_id:
                floor_ids.add(segment.floor_id)
    floor_ids.add(1)
    logger.info(f"Relevant floor IDs: {floor_ids}")
    return floor_ids

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()
    try:
        add_vertex_to_graph(graph, db, start)
        add_vertex_to_graph(graph, db, end)
    except ValueError as e:
        logger.error(f"Failed to add start/end vertices: {e}")
        raise

    building_ids = get_relevant_buildings(db, start, end)
    floor_ids = get_relevant_floors(db, start, end)

    rooms = db.query(Room).filter(
        Room.building_id.in_(building_ids),
        Room.floor_id.in_(floor_ids)
    ).all()
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))

    segments = db.query(Segment).filter(
        Segment.building_id.in_(building_ids),
        Segment.floor_id.in_(floor_ids)
    ).all()
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        graph.add_edge(end_vertex, start_vertex, weight)  # Двунаправленное ребро
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    outdoor_segments = db.query(OutdoorSegment).all()
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 1))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 1))
        weight = sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.end_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        graph.add_edge(end_vertex, start_vertex, weight)  # Двунаправленное ребро
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    connections = db.query(Connection).all()
    for conn in connections:
        weight = conn.weight if conn.weight else 1
        if conn.type == "дверь" and conn.room_id and conn.segment_id:
            room_vertex = f"room_{conn.room_id}"
            segment = next((s for s in segments if s.id == conn.segment_id), None)
            if segment and room_vertex in graph.vertices:
                segment_start = f"segment_{conn.segment_id}_start"
                segment_end = f"segment_{conn.segment_id}_end"
                if segment_start in graph.vertices and segment_end in graph.vertices:
                    room_coords = graph.vertices[room_vertex]
                    start_coords = graph.vertices[segment_start]
                    end_coords = graph.vertices[segment_end]
                    phantom_coords = find_phantom_point(room_coords, start_coords, end_coords)
                    phantom_vertex = f"phantom_room_{conn.room_id}_segment_{conn.segment_id}"
                    graph.add_vertex(phantom_vertex, phantom_coords)
                    dist_to_phantom = sqrt((room_coords[0] - phantom_coords[0]) ** 2 + (room_coords[1] - phantom_coords[1]) ** 2)
                    graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom / 2)
                    dist_phantom_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2) / 2
                    dist_phantom_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2) / 2
                    graph.add_edge(phantom_vertex, segment_start, dist_phantom_to_start)
                    graph.add_edge(phantom_vertex, segment_end, dist_phantom_to_end)
                    logger.info(f"Added phantom vertex: {phantom_vertex} -> {phantom_coords}")

        elif conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
            to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
            if from_segment and to_segment:
                from_vertex = f"segment_{conn.from_segment_id}_end"
                to_vertex = f"segment_{conn.to_segment_id}_start"
                if from_vertex in graph.vertices and to_vertex in graph.vertices:
                    if (from_vertex, to_vertex) not in graph.edges:
                        graph.add_edge(from_vertex, to_vertex, weight)
                        graph.add_edge(to_vertex, from_vertex, weight)  # Двунаправленное ребро
                        logger.info(f"Added edge (ladder): {from_vertex} <-> {to_vertex}, weight={weight}")

        elif (conn.type in ["улица", "дверь"]) and ((conn.from_segment_id and conn.to_outdoor_id) or (conn.from_outdoor_id and conn.to_segment_id)):
            if conn.from_segment_id and conn.to_outdoor_id:
                from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
                to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
                if from_segment and to_outdoor:
                    from_vertex = f"segment_{conn.from_segment_id}_end"
                    to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
                    if from_vertex in graph.vertices and to_vertex in graph.vertices:
                        if (from_vertex, to_vertex) not in graph.edges:
                            graph.add_edge(from_vertex, to_vertex, weight)
                            graph.add_edge(to_vertex, from_vertex, weight)  # Двунаправленное ребро
                            logger.info(f"Added edge (outdoor start): {from_vertex} <-> {to_vertex}, weight={weight}")
            if conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
                to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
                if from_outdoor and to_segment:
                    from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                    to_vertex = f"segment_{conn.to_segment_id}_start"
                    if from_vertex in graph.vertices and to_vertex in graph.vertices:
                        if (from_vertex, to_vertex) not in graph.edges:
                            graph.add_edge(from_vertex, to_vertex, weight)
                            graph.add_edge(to_vertex, from_vertex, weight)  # Двунаправленное ребро
                            logger.info(f"Added edge (outdoor end): {from_vertex} <-> {to_vertex}, weight={weight}")

        elif conn.type == "улица" and conn.from_outdoor_id and conn.to_outdoor_id:
            from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
            to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
            if from_outdoor and to_outdoor:
                from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
                if from_vertex in graph.vertices and to_vertex in graph.vertices:
                    if (from_vertex, to_vertex) not in graph.edges:
                        graph.add_edge(from_vertex, to_vertex, weight)
                        graph.add_edge(to_vertex, from_vertex, weight)  # Двунаправленное ребро
                        logger.info(f"Added edge (street): {from_vertex} <-> {to_vertex}, weight={weight}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    logger.info(f"Final vertices: {list(graph.vertices.keys())}")
    logger.info(f"Final edges: {dict(graph.edges)}")
    return graph