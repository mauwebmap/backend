# app/map/pathfinder/builder.py
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt

VALID_TYPES = {"room", "segment", "outdoor"}


def parse_vertex_id(vertex: str) -> tuple[str, str]:
    """
    Разбирает идентификатор точки (например, 'room_1' → ('room', '1')).
    """
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
    """
    Определяет здания, связанные со стартом и концом.
    """
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

    print(f"[get_relevant_buildings] Building IDs: {building_ids}")
    return building_ids


def get_relevant_floors(db: Session, start: str, end: str) -> set[int]:
    """
    Определяет этажи, связанные со стартом и концом.
    """
    floor_ids = set()
    start_type, start_id = parse_vertex_id(start)
    end_type, end_id = parse_vertex_id(end)

    for vertex_type, vertex_id in [(start_type, start_id), (end_type, end_id)]:
        if vertex_type == "room":
            room = db.query(Room).filter(Room.id == int(vertex_id)).first()
            if room:
                floor_ids.add(room.floor_id)
        elif vertex_type == "segment":
            segment = db.query(Segment).filter(Segment.id == int(vertex_id)).first()
            if segment:
                floor_ids.add(segment.floor_id)

    print(f"[get_relevant_floors] Floor IDs: {floor_ids}")
    return floor_ids


def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    """
    Добавляет вершину в граф на основе её типа и ID.
    """
    vertex_type, vertex_id = parse_vertex_id(vertex)

    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        if room and vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0, room.floor_id)
            print(f"[add_vertex_to_graph] Added room vertex: {vertex} -> {graph.vertices[vertex]}")
    elif vertex_type == "segment":
        segment = db.query(Segment).filter(Segment.id == int(vertex_id)).first()
        if segment:
            start_key = f"segment_{segment.id}_start"
            end_key = f"segment_{segment.id}_end"
            if start_key not in graph.vertices:
                start_coords = (segment.start_x, segment.start_y, segment.floor_id)
                end_coords = (segment.end_x, segment.end_y, segment.floor_id)
                graph.vertices[start_key] = start_coords
                graph.vertices[end_key] = end_coords
                weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
                graph.add_edge(start_key, end_key, weight, start_coords, end_coords, "segment")
                print(f"[add_vertex_to_graph] Added segment vertices: {start_key} -> {start_coords}, {end_key} -> {end_coords}")
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
                graph.add_edge(start_key, end_key, os.weight, start_coords, end_coords, "outdoor")
                print(f"[add_vertex_to_graph] Added outdoor vertices: {start_key} -> {start_coords}, {end_key} -> {end_coords}")


def build_graph(db: Session, start: str, end: str) -> Graph:
    """
    Строит граф для маршрута от start до end.
    """
    graph = Graph()

    # Добавляем стартовую и конечную точки
    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    # Определяем здания и этажи
    building_ids = get_relevant_buildings(db, start, end)
    floor_ids = get_relevant_floors(db, start, end)

    start_type, _ = parse_vertex_id(start)
    end_type, _ = parse_vertex_id(end)
    is_outdoor_only = start_type == "outdoor" and end_type == "outdoor"

    # Загружаем данные
    if not is_outdoor_only and building_ids:
        rooms = db.query(Room).filter(Room.building_id.in_(building_ids)).all()
        print(f"[build_graph] Loaded rooms: {[r.id for r in rooms]}")
        # Фильтруем сегменты по building_id и floor_id
        if floor_ids:
            segments = db.query(Segment).filter(
                Segment.building_id.in_(building_ids),
                Segment.floor_id.in_(floor_ids)
            ).all()
        else:
            segments = db.query(Segment).filter(Segment.building_id.in_(building_ids)).all()
        print(f"[build_graph] Loaded segments: {[s.id for s in segments]}")
    else:
        rooms = []
        segments = []

    outdoor_segments = db.query(OutdoorSegment).filter(
        (OutdoorSegment.start_building_id.in_(building_ids)) |
        (OutdoorSegment.end_building_id.in_(building_ids)) |
        ((OutdoorSegment.start_building_id.is_(None)) & (OutdoorSegment.end_building_id.is_(None)))
    ).all()
    print(f"[build_graph] Loaded outdoor segments: {[os.id for os in outdoor_segments]}")

    # Добавляем вершины в граф
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.vertices[vertex] = (room.cab_x or 0, room.cab_y or 0, room.floor_id)
            print(f"[build_graph] Added room vertex: {vertex} -> {graph.vertices[vertex]}")

    for segment in segments:
        start_key = f"segment_{segment.id}_start"
        end_key = f"segment_{segment.id}_end"
        if start_key not in graph.vertices:
            start_coords = (segment.start_x, segment.start_y, segment.floor_id)
            end_coords = (segment.end_x, segment.end_y, segment.floor_id)
            graph.vertices[start_key] = start_coords
            graph.vertices[end_key] = end_coords
            weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
            graph.add_edge(start_key, end_key, weight, start_coords, end_coords, "segment")
            print(f"[build_graph] Added segment vertices: {start_key} -> {start_coords}, {end_key} -> {end_coords}")

    for os in outdoor_segments:
        start_key = f"outdoor_{os.id}_start"
        end_key = f"outdoor_{os.id}_end"
        if start_key not in graph.vertices:
            start_coords = (os.start_x, os.start_y, "outdoor")
            end_coords = (os.end_x, os.end_y, "outdoor")
            graph.vertices[start_key] = start_coords
            graph.vertices[end_key] = end_coords
            graph.add_edge(start_key, end_key, os.weight, start_coords, end_coords, "outdoor")
            print(f"[build_graph] Added outdoor vertices: {start_key} -> {start_coords}, {end_key} -> {end_coords}")

    # Загружаем и добавляем соединения
    connections = db.query(Connection).filter(
        (Connection.room_id.in_([r.id for r in rooms])) |
        (Connection.segment_id.in_([s.id for s in segments])) |
        (Connection.from_segment_id.in_([s.id for s in segments])) |
        (Connection.to_segment_id.in_([s.id for s in segments])) |
        (Connection.from_outdoor_id.in_([o.id for o in outdoor_segments])) |
        (Connection.to_outdoor_id.in_([o.id for o in outdoor_segments]))
    ).all()
    print(f"[build_graph] Loaded connections: {[conn.id for conn in connections]}")

    for conn in connections:
        print(f"[build_graph] Processing connection: id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}")
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
            print(f"[build_graph] Skipping connection id={conn.id}: invalid type or missing IDs")
            continue

        from_coords = graph.vertices.get(from_key, (0, 0, 0))
        to_coords = graph.vertices.get(to_key, (0, 0, 0))
        print(f"[build_graph] Adding edge: {from_key} -> {to_key}, weight={conn.weight}, from_coords={from_coords}, to_coords={to_coords}")
        graph.add_edge(from_key, to_key, conn.weight, from_coords, to_coords, conn.type)

    # Отладочный вывод
    print("Vertices:", graph.vertices)
    print("Edges:", graph.edges)

    return graph