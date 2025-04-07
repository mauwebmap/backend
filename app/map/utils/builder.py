from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt

VALID_TYPES = {"room", "segment", "outdoor"}


def parse_vertex_id(vertex: str) -> tuple[str, str]:
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
    vertex_type, vertex_id = parse_vertex_id(vertex)

    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        if room and vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0, room.floor)
    elif vertex_type == "segment":
        segment = db.query(Segment).filter(Segment.id == int(vertex_id)).first()
        if segment:
            start_key = f"segment_{segment.id}_start"
            end_key = f"segment_{segment.id}_end"
            if start_key not in graph.vertices:
                start_coords = (segment.start_x, segment.start_y, segment.floor)
                end_coords = (segment.end_x, segment.end_y, segment.floor)
                graph.vertices[start_key] = start_coords
                graph.vertices[end_key] = end_coords
                weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
                try:
                    graph.add_edge(start_key, end_key, weight, start_coords, end_coords)
                except Exception:
                    pass
    elif vertex_type == "outdoor":
        os = db.query(OutdoorSegment).filter(OutdoorSegment.id == int(vertex_id)).first()
        if os:
            start_key = f"outdoor_{os.id}_start"
            end_key = f"outdoor_{os.id}_end"
            if start_key not in graph.vertices:
                start_coords = (os.start_x, os.start_y, "outdoor")
                end_coords = (os.end_x, os.end_y, "outdoor")
                graph.vertices[start_key] = start_coords
                graph.vertices[end_key] = end_coords
                try:
                    graph.add_edge(start_key, end_key, os.weight, start_coords, end_coords)
                except Exception:
                    pass


def build_graph(db: Session, start: str, end: str) -> Graph:
    graph = Graph()

    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    building_ids = get_relevant_buildings(db, start, end)

    start_type, _ = parse_vertex_id(start)
    end_type, _ = parse_vertex_id(end)
    is_outdoor_only = start_type == "outdoor" and end_type == "outdoor"

    if not is_outdoor_only and building_ids:
        rooms = db.query(Room).filter(Room.building_id.in_(building_ids)).all()
        segments = db.query(Segment).filter(Segment.building_id.in_(building_ids)).all()
    else:
        rooms = []
        segments = []

    outdoor_segments = db.query(OutdoorSegment).filter(
        (OutdoorSegment.start_building_id.in_(building_ids)) |
        (OutdoorSegment.end_building_id.in_(building_ids)) |
        ((OutdoorSegment.start_building_id.is_(None)) & (OutdoorSegment.end_building_id.is_(None)))
    ).all()

    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0, room.floor)

    for segment in segments:
        start_key = f"segment_{segment.id}_start"
        end_key = f"segment_{segment.id}_end"
        if start_key not in graph.vertices:
            start_coords = (segment.start_x, segment.start_y, segment.floor)
            end_coords = (segment.end_x, segment.end_y, segment.floor)
            graph.vertices[start_key] = start_coords
            graph.vertices[end_key] = end_coords
            weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
            try:
                graph.add_edge(start_key, end_key, weight, start_coords, end_coords)
            except Exception:
                pass

    for os in outdoor_segments:
        start_key = f"outdoor_{os.id}_start"
        end_key = f"outdoor_{os.id}_end"
        if start_key not in graph.vertices:
            start_coords = (os.start_x, os.start_y, "outdoor")
            end_coords = (os.end_x, os.end_y, "outdoor")
            graph.vertices[start_key] = start_coords
            graph.vertices[end_key] = end_coords
            try:
                graph.add_edge(start_key, end_key, os.weight, start_coords, end_coords)
            except Exception:
                pass

    connections = db.query(Connection).filter(
        (Connection.room_id.in_([r.id for r in rooms])) |
        (Connection.segment_id.in_([s.id for s in segments])) |
        (Connection.from_segment_id.in_([s.id for s in segments])) |
        (Connection.to_segment_id.in_([s.id for s in segments])) |
        (Connection.from_outdoor_id.in_([o.id for o in outdoor_segments])) |
        (Connection.to_outdoor_id.in_([o.id for o in outdoor_segments]))
    ).all()

    for conn in connections:
        try:
            if conn.type == "door" and conn.room_id and conn.segment_id:
                from_key = f"room_{conn.room_id}"
                to_key = f"segment_{conn.segment_id}_start"
            elif conn.type == "segment-to-segment" and conn.from_segment_id and conn.to_segment_id:
                from_key = f"segment_{conn.from_segment_id}_end"
                to_key = f"segment_{conn.to_segment_id}_start"
            elif conn.type == "exit" and conn.segment_id and conn.from_outdoor_id:
                from_key = f"segment_{conn.segment_id}_end"
                to_key = f"outdoor_{conn.from_outdoor_id}_start"
            elif conn.type == "exit" and conn.segment_id and conn.to_outdoor_id:
                from_key = f"outdoor_{conn.to_outdoor_id}_end"
                to_key = f"segment_{conn.segment_id}_start"
            elif conn.type == "outdoor" and conn.from_outdoor_id and conn.to_outdoor_id:
                from_key = f"outdoor_{conn.from_outdoor_id}_end"
                to_key = f"outdoor_{conn.to_outdoor_id}_start"
            elif conn.type == "stair" and conn.from_segment_id and conn.to_segment_id:
                from_key = f"segment_{conn.from_segment_id}_end"
                to_key = f"segment_{conn.to_segment_id}_start"
            else:
                continue

            from_coords = graph.vertices.get(from_key, (0, 0, 0))
            to_coords = graph.vertices.get(to_key, (0, 0, 0))
            graph.add_edge(from_key, to_key, conn.weight, from_coords, to_coords)
        except Exception:
            pass

    return graph
