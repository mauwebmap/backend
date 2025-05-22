# backend/app/map/utils/builder.py
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.utils.graph import Graph
from math import sqrt
import logging

logger = logging.getLogger(__name__)

VALID_TYPES = {"room", "segment", "outdoor"}

def parse_vertex_id(vertex: str):
    type_, id_ = vertex.split("_", 1)
    if type_ not in VALID_TYPES:
        raise ValueError(f"Неверный тип вершины: {type_}")
    return type_, int(id_)

def find_phantom_point(start_coords: tuple, end_coords: tuple, ref_coords: tuple = None) -> tuple:
    sx, sy, sfloor = start_coords
    ex, ey, efloor = end_coords

    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return sx, sy, sfloor

    length = sqrt(length_squared)
    nx, ny = dx / length, dy / length

    if ref_coords:
        rx, ry, rfloor = ref_coords
        dot_product = (rx - sx) * nx + (ry - sy) * ny
        t = max(0, min(1, dot_product / length))
        phantom_x = sx + t * dx
        phantom_y = sy + t * dy
        phantom_floor = rfloor if abs(rfloor - sfloor) <= 1 else sfloor
        return phantom_x, phantom_y, phantom_floor

    t = 0.5
    phantom_x = sx + t * dx
    phantom_y = sy + t * dy
    phantom_floor = sfloor
    return phantom_x, phantom_y, phantom_floor

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room:
            logger.error(f"Комната {vertex} не найдена в базе")
            raise ValueError(f"Комната {vertex} не найдена")
        graph.add_vertex(vertex, {
            "coords": (room.cab_x, room.cab_y, room.floor_id),
            "building_id": room.building_id
        })
        logger.info(f"Added room vertex: {vertex} -> {(room.cab_x, room.cab_y, room.floor_id)}")
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment:
            logger.error(f"Сегмент {vertex} не найден в базе")
            raise ValueError(f"Сегмент {vertex} не найден")
        graph.add_vertex(f"segment_{id_}_start", {
            "coords": (segment.start_x, segment.start_y, segment.floor_id),
            "building_id": segment.building_id
        })
        graph.add_vertex(f"segment_{id_}_end", {
            "coords": (segment.end_x, segment.end_y, segment.floor_id),
            "building_id": segment.building_id
        })
        logger.info(f"Added segment vertices: segment_{id_}_start -> {(segment.start_x, segment.start_y, segment.floor_id)}, segment_{id_}_end -> {(segment.end_x, segment.end_y, segment.floor_id)}")
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor:
            logger.error(f"Уличный сегмент {vertex} не найден в базе")
            raise ValueError(f"Уличный сегмент {vertex} не найден")
        graph.add_vertex(f"outdoor_{id_}_start", {
            "coords": (outdoor.start_x, outdoor.start_y, 1),
            "building_id": None
        })
        graph.add_vertex(f"outdoor_{id_}_end", {
            "coords": (outdoor.end_x, outdoor.end_y, 1),
            "building_id": None
        })
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
    floor_ids.add(1)  # Добавляем floor для outdoor
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

    # Добавляем все комнаты
    rooms = db.query(Room).filter(
        Room.building_id.in_(building_ids),
        Room.floor_id.in_(floor_ids)
    ).all()
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, {
                "coords": (room.cab_x, room.cab_y, room.floor_id),
                "building_id": room.building_id
            })

    # Добавляем все сегменты
    segments = db.query(Segment).filter(
        Segment.building_id.in_(building_ids),
        Segment.floor_id.in_(floor_ids)
    ).all()
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, {
                "coords": (segment.start_x, segment.start_y, segment.floor_id),
                "building_id": segment.building_id
            })
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, {
                "coords": (segment.end_x, segment.end_y, segment.floor_id),
                "building_id": segment.building_id
            })
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        graph.add_edge(end_vertex, start_vertex, weight)
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Добавляем все outdoor сегменты
    outdoor_segments = db.query(OutdoorSegment).all()
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, {
                "coords": (outdoor.start_x, outdoor.start_y, 1),
                "building_id": None
            })
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, {
                "coords": (outdoor.end_x, outdoor.end_y, 1),
                "building_id": None
            })
        weight = outdoor.weight if outdoor.weight else sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.end_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        graph.add_edge(end_vertex, start_vertex, weight)
        logger.info(f"Added edge: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Добавляем phantom точки
    for outdoor in outdoor_segments:
        if outdoor.id == 3:  # Пример с phantom_outdoor_3
            start_vertex = f"outdoor_{outdoor.id}_start"
            end_vertex = f"outdoor_{outdoor.id}_end"
            start_coords = graph.vertices[start_vertex]["coords"]
            end_coords = graph.vertices[end_vertex]["coords"]
            phantom_coords = find_phantom_point(start_coords, end_coords)
            phantom_vertex = f"phantom_outdoor_{outdoor.id}"
            graph.add_vertex(phantom_vertex, {
                "coords": phantom_coords,
                "building_id": None
            })
            dist_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2)
            dist_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2)
            graph.add_edge(phantom_vertex, start_vertex, dist_to_start)
            graph.add_edge(phantom_vertex, end_vertex, dist_to_end)
            logger.info(f"Added phantom vertex: {phantom_vertex} -> {phantom_coords}")

    for segment in segments:
        if segment.id == 11:  # Пример с phantom_segment_11
            end_vertex = f"segment_{segment.id}_end"
            start_vertex = f"segment_{segment.id}_start"
            end_coords = graph.vertices[end_vertex]["coords"]
            start_coords = graph.vertices[start_vertex]["coords"]
            phantom_coords = find_phantom_point(start_coords, end_coords)
            phantom_vertex = f"phantom_segment_{segment.id}"
            graph.add_vertex(phantom_vertex, {
                "coords": phantom_coords,
                "building_id": segment.building_id
            })
            dist_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2)
            dist_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2)
            graph.add_edge(phantom_vertex, end_vertex, dist_to_end)
            graph.add_edge(phantom_vertex, start_vertex, dist_to_start)
            logger.info(f"Added phantom vertex: {phantom_vertex} -> {phantom_coords}")

    connections = db.query(Connection).all()
    for conn in connections:
        weight = conn.weight if conn.weight else 1
        if conn.type == "дверь" and conn.room_id and conn.segment_id:
            room_vertex = f"room_{conn.room_id}"
            segment = next((s for s in segments if s.id == conn.segment_id), None)
            if segment and room_vertex in graph.vertices:
                segment_start = f"segment_{conn.segment_id}_start"
                segment_end = f"segment_{conn.segment_id}_end"
                room_coords = graph.vertices[room_vertex]["coords"]
                start_coords = graph.vertices[segment_start]["coords"]
                end_coords = graph.vertices[segment_end]["coords"]
                phantom_coords = find_phantom_point(start_coords, end_coords, room_coords)
                phantom_vertex = f"phantom_room_{conn.room_id}_segment_{conn.segment_id}"
                graph.add_vertex(phantom_vertex, {
                    "coords": phantom_coords,
                    "building_id": segment.building_id
                })
                dist_to_phantom = sqrt((room_coords[0] - phantom_coords[0]) ** 2 + (room_coords[1] - phantom_coords[1]) ** 2)
                graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom)
                dist_phantom_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2)
                dist_phantom_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2)
                graph.add_edge(phantom_vertex, segment_start, dist_phantom_to_start)
                graph.add_edge(phantom_vertex, segment_end, dist_phantom_to_end)
                logger.info(f"Added phantom vertex: {phantom_vertex} -> {phantom_coords}")

        elif conn.type == "дверь" and conn.from_segment_id and conn.to_segment_id:
            from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
            to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
            if from_segment and to_segment:
                from_vertex = f"segment_{conn.from_segment_id}_end"
                to_vertex = f"segment_{conn.to_segment_id}_start"
                if from_vertex in graph.vertices and to_vertex in graph.vertices:
                    if (from_vertex, to_vertex) not in [(e[0], e[1]) for e in graph.edges.get(from_vertex, [])]:
                        graph.add_edge(from_vertex, to_vertex, weight)
                        graph.add_edge(to_vertex, from_vertex, weight)
                        logger.info(f"Added edge (segment door): {from_vertex} <-> {to_vertex}, weight={weight}")

        elif conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
            to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
            if from_segment and to_segment:
                from_vertex = f"segment_{conn.from_segment_id}_end"
                to_vertex = f"segment_{conn.to_segment_id}_start"
                if from_vertex in graph.vertices and to_vertex in graph.vertices:
                    if (from_vertex, to_vertex) not in [(e[0], e[1]) for e in graph.edges.get(from_vertex, [])]:
                        graph.add_edge(from_vertex, to_vertex, weight)
                        graph.add_edge(to_vertex, from_vertex, weight)
                        logger.info(f"Added edge (ladder): {from_vertex} <-> {to_vertex}, weight={weight}")

        elif (conn.type in ["улица", "дверь"]) and ((conn.from_segment_id and conn.to_outdoor_id) or (conn.from_outdoor_id and conn.to_segment_id)):
            if conn.from_segment_id and conn.to_outdoor_id:
                from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
                to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
                if from_segment and to_outdoor:
                    from_vertex = f"segment_{conn.from_segment_id}_end"
                    to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
                    if from_vertex in graph.vertices and to_vertex in graph.vertices:
                        if (from_vertex, to_vertex) not in [(e[0], e[1]) for e in graph.edges.get(from_vertex, [])]:
                            graph.add_edge(from_vertex, to_vertex, weight)
                            graph.add_edge(to_vertex, from_vertex, weight)
                            logger.info(f"Added edge (outdoor start): {from_vertex} <-> {to_vertex}, weight={weight}")
            if conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
                to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
                if from_outdoor and to_segment:
                    from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                    to_vertex = f"segment_{conn.to_segment_id}_start"
                    if from_vertex in graph.vertices and to_vertex in graph.vertices:
                        if (from_vertex, to_vertex) not in [(e[0], e[1]) for e in graph.edges.get(from_vertex, [])]:
                            graph.add_edge(from_vertex, to_vertex, weight)
                            graph.add_edge(to_vertex, from_vertex, weight)
                            logger.info(f"Added edge (outdoor end): {from_vertex} <-> {to_vertex}, weight={weight}")

        elif conn.type == "улица" and conn.from_outdoor_id and conn.to_outdoor_id:
            from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
            to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
            if from_outdoor and to_outdoor:
                from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
                if from_vertex in graph.vertices and to_vertex in graph.vertices:
                    if (from_vertex, to_vertex) not in [(e[0], e[1]) for e in graph.edges.get(from_vertex, [])]:
                        graph.add_edge(from_vertex, to_vertex, weight)
                        graph.add_edge(to_vertex, from_vertex, weight)
                        logger.info(f"Added edge (street): {from_vertex} <-> {to_vertex}, weight={weight}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    logger.info(f"Final vertices: {list(graph.vertices.keys())}")
    logger.info(f"Final edges: {dict(graph.edges)}")
    return graph