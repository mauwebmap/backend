from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.connection import Connection
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.utils.graph import Graph
from math import sqrt

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

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple) -> tuple:
    """Находит ближайшую точку на сегменте (проекцию точки комнаты на линию сегмента)."""
    rx, ry, _ = room_coords
    sx, sy, sfloor = segment_start
    ex, ey, _ = segment_end

    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return sx, sy, sfloor

    length_squared = dx * dx + dy * dy
    px = rx - sx
    py = ry - sy
    dot_product = px * dx + py * dy
    t = max(0, min(1, dot_product / length_squared))

    phantom_x = sx + t * dx
    phantom_y = sy + t * dy

    return phantom_x, phantom_y, sfloor

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    """Добавление вершины в граф."""
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room:
            raise ValueError(f"Комната {vertex} не найдена")
        graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment:
            raise ValueError(f"Сегмент {vertex} не найден")
        graph.add_vertex(f"segment_{id_}_start", (segment.start_x, segment.start_y, segment.floor_id))
        graph.add_vertex(f"segment_{id_}_end", (segment.end_x, segment.end_y, segment.floor_id))
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor:
            raise ValueError(f"Уличный сегмент {vertex} не найден")
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, 0))
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, 0))

def get_relevant_buildings(db: Session, start: str, end: str) -> set:
    """Получение списка зданий, связанных с начальной и конечной точками."""
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
    return building_ids

def get_relevant_floors(db: Session, start: str, end: str) -> set:
    """Получение списка этажей, связанных с начальной и конечной точками."""
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
    floor_ids.add(0)  # Добавляем floor_id=0 для outdoor и первого этажа
    return floor_ids

def build_graph(db: Session, start: str, end: str) -> Graph:
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
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))

    # Загрузка всех сегментов в зданиях и на этажах
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

    # Загрузка всех уличных сегментов
    outdoor_segments = db.query(OutdoorSegment).all()
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 0))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 0))
        weight = sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)

    # Загрузка всех соединений
    connections = db.query(Connection).filter(
        (Connection.room_id.in_([r.id for r in rooms])) |
        (Connection.segment_id.in_([s.id for s in segments])) |
        (Connection.from_segment_id.in_([s.id for s in segments])) |
        (Connection.to_segment_id.in_([s.id for s in segments])) |
        (Connection.from_outdoor_id.in_([o.id for o in outdoor_segments])) |
        (Connection.to_outdoor_id.in_([o.id for o in outdoor_segments]))
    ).all()

    # Добавление рёбер на основе соединений
    for conn in connections:
        weight = conn.weight if conn.weight is not None else 1

        # Соединение между комнатой и сегментом (дверь)
        if conn.type == "дверь" and conn.room_id and conn.segment_id:
            room_vertex = f"room_{conn.room_id}"
            segment = next((s for s in segments if s.id == conn.segment_id), None)
            if not segment or room_vertex not in graph.vertices:
                continue
            segment_start = f"segment_{conn.segment_id}_start"
            segment_end = f"segment_{conn.segment_id}_end"
            if segment_start not in graph.vertices or segment_end not in graph.vertices:
                continue

            room_coords = graph.vertices[room_vertex]
            start_coords = graph.vertices[segment_start]
            end_coords = graph.vertices[segment_end]
            phantom_coords = find_phantom_point(room_coords, start_coords, end_coords)

            phantom_vertex = f"phantom_room_{conn.room_id}_segment_{conn.segment_id}"
            graph.add_vertex(phantom_vertex, phantom_coords)
            dist_to_phantom = sqrt((room_coords[0] - phantom_coords[0]) ** 2 + (room_coords[1] - phantom_coords[1]) ** 2)
            graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom)
            dist_phantom_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2)
            dist_phantom_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2)
            graph.add_edge(phantom_vertex, segment_start, dist_phantom_to_start)
            graph.add_edge(phantom_vertex, segment_end, dist_phantom_to_end)

        # Соединение между сегментами (лестница)
        elif conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
            to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
            if not from_segment or not to_segment:
                continue
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, weight)

        # Соединение между сегментом и outdoor_segment (улица или дверь)
        elif (conn.type in ["улица", "дверь"]) and ((conn.from_segment_id and conn.to_outdoor_id) or (conn.from_outdoor_id and conn.to_segment_id)):
            if conn.from_segment_id and conn.to_outdoor_id:
                from_segment = next((s for s in segments if s.id == conn.from_segment_id), None)
                to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
                if from_segment and to_outdoor and f"segment_{conn.from_segment_id}_end" in graph.vertices and f"outdoor_{conn.to_outdoor_id}_start" in graph.vertices:
                    graph.add_edge(f"segment_{conn.from_segment_id}_end", f"outdoor_{conn.to_outdoor_id}_start", weight)
            if conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
                to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
                if from_outdoor and to_segment and f"outdoor_{conn.from_outdoor_id}_end" in graph.vertices and f"segment_{conn.to_segment_id}_start" in graph.vertices:
                    graph.add_edge(f"outdoor_{conn.from_outdoor_id}_end", f"segment_{conn.to_segment_id}_start", weight)

    return graph