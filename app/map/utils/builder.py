from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt

VALID_TYPES = {"room", "segment", "outdoor"}


def parse_vertex_id(vertex: str) -> tuple[str, str]:
    """Разбирает идентификатор точки (например, 'room_1' → ('room', '1'))."""
    try:
        type_, id_ = vertex.split('_', 1)
        if type_ not in VALID_TYPES:
            raise ValueError(f"Неверный тип объекта: {type_}")
        if not id_.isdigit():
            raise ValueError(f"ID должен быть числом: {id_}")
        return type_, id_
    except ValueError as e:
        raise ValueError(f"Неверный формат идентификатора: {vertex} ({str(e)})")


def get_relevant_buildings(db: Session, start: str, end: str) -> set[int]:
    """Определяет здания, связанные со стартом и концом."""
    building_ids = set()
    start_type, start_id = parse_vertex_id(start)
    end_type, end_id = parse_vertex_id(end)

    for vertex_type, vertex_id in [(start_type, start_id), (end_type, end_id)]:
        if vertex_type == "room":
            room = db.query(Room).filter(Room.id == int(vertex_id)).first()
            if room:
                building_ids.add(room.building_id)
        elif vertex_type == "segment":
            segment = db.query(Segment).filter(Segment.id == int(vertex_id)).first()
            if segment:
                building_ids.add(segment.building_id)
        elif vertex_type == "outdoor":
            os = db.query(OutdoorSegment).filter(OutdoorSegment.id == int(vertex_id)).first()
            if os:
                if os.start_building_id:
                    building_ids.add(os.start_building_id)
                if os.end_building_id:
                    building_ids.add(os.end_building_id)

    return building_ids


def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    """Добавляет вершину в граф на основе её типа и ID."""
    vertex_type, vertex_id = parse_vertex_id(vertex)

    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        if room and vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0)
    elif vertex_type == "segment":
        segment = db.query(Segment).filter(Segment.id == int(vertex_id)).first()
        if segment:
            start_key = f"segment_{segment.id}_start"
            end_key = f"segment_{segment.id}_end"
            if start_key not in graph.vertices:
                graph.vertices[start_key] = (segment.start_x, segment.start_y)
                graph.vertices[end_key] = (segment.end_x, segment.end_y)
                weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
                graph.add_edge(start_key, end_key, weight)
    elif vertex_type == "outdoor":
        os = db.query(OutdoorSegment).filter(OutdoorSegment.id == int(vertex_id)).first()
        if os:
            start_key = f"outdoor_{os.id}_start"
            end_key = f"outdoor_{os.id}_end"
            if start_key not in graph.vertices:
                graph.vertices[start_key] = (os.start_x, os.start_y)
                graph.vertices[end_key] = (os.end_x, os.end_y)
                graph.add_edge(start_key, end_key, os.weight)


def build_graph(db: Session, start: str, end: str) -> Graph:
    """Строит граф для маршрута от start до end."""
    graph = Graph()

    # Добавляем стартовую и конечную точки
    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    # Определяем здания
    building_ids = get_relevant_buildings(db, start, end)

    # Если обе точки — уличные, загружаем только улицу
    start_type, _ = parse_vertex_id(start)
    end_type, _ = parse_vertex_id(end)
    is_outdoor_only = start_type == "outdoor" and end_type == "outdoor"

    # Загружаем данные
    if not is_outdoor_only and building_ids:
        rooms = db.query(Room).filter(Room.building_id.in_(building_ids)).all()
        segments = db.query(Segment).filter(Segment.building_id.in_(building_ids)).all()
    else:
        rooms = []
        segments = []

    outdoor_segments = db.query(OutdoorSegment).filter(
        (OutdoorSegment.start_building_id.in_(building_ids)) |
        (OutdoorSegment.end_building_id.in_(building_ids)) |
        (OutdoorSegment.start_building_id.is_(None)) & (OutdoorSegment.end_building_id.is_(None))
    ).all()

    # Добавляем вершины в граф
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0)

    for segment in segments:
        start_key = f"segment_{segment.id}_start"
        end_key = f"segment_{segment.id}_end"
        if start_key not in graph.vertices:
            graph.vertices[start_key] = (segment.start_x, segment.start_y)
            graph.vertices[end_key] = (segment.end_x, segment.end_y)
            weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
            graph.add_edge(start_key, end_key, weight)

    for os in outdoor_segments:
        start_key = f"outdoor_{os.id}_start"
        end_key = f"outdoor_{os.id}_end"
        if start_key not in graph.vertices:
            graph.vertices[start_key] = (os.start_x, os.start_y)
            graph.vertices[end_key] = (os.end_x, os.end_y)
            graph.add_edge(start_key, end_key, os.weight)

    # Загружаем и добавляем соединения
    connections = db.query(Connection).filter(
        (Connection.room_id.in_(r.id for r in rooms)) |
        (Connection.segment_id.in_(s.id for s in segments)) |
        (Connection.from_segment_id.in_(s.id for s in segments)) |
        (Connection.to_segment_id.in_(s.id for s in segments)) |
        (Connection.from_outdoor_id.in_(os.id for os in outdoor_segments)) |
        (Connection.to_outdoor_id.in_(os.id for os in outdoor_segments))
    ).all()

    for conn in connections:
        if conn.type == "door" and conn.room_id and conn.segment_id:
            graph.add_edge(f"room_{conn.room_id}", f"segment_{conn.segment_id}_start", conn.weight)
        elif conn.type == "segment-to-segment" and conn.from_segment_id and conn.to_segment_id:
            graph.add_edge(f"segment_{conn.from_segment_id}_end", f"segment_{conn.to_segment_id}_start", conn.weight)
        elif conn.type == "exit" and conn.segment_id and conn.from_outdoor_id:
            graph.add_edge(f"segment_{conn.segment_id}_end", f"outdoor_{conn.from_outdoor_id}_start", conn.weight)
        elif conn.type == "exit" and conn.segment_id and conn.to_outdoor_id:
            graph.add_edge(f"outdoor_{conn.to_outdoor_id}_end", f"segment_{conn.segment_id}_start", conn.weight)
        elif conn.type == "outdoor" and conn.from_outdoor_id and conn.to_outdoor_id:
            graph.add_edge(f"outdoor_{conn.from_outdoor_id}_end", f"outdoor_{conn.to_outdoor_id}_start", conn.weight)
        elif conn.type == "stair" and conn.from_segment_id and conn.to_segment_id:
            graph.add_edge(f"segment_{conn.from_segment_id}_end", f"segment_{conn.to_segment_id}_start", conn.weight)

    return graph