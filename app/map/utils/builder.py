# app/map/pathfinder/builder.py
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
    if not all(x is not None for x in room_coords[:2] + segment_start[:2] + segment_end[:2]):
        return segment_start  # Возвращаем начало сегмента как запасной вариант
    rx, ry, _ = room_coords
    sx, sy, _ = segment_start
    ex, ey, _ = segment_end

    dx = ex - sx
    dy = ey - sy
    if dx == 0 and dy == 0:
        return sx, sy, 0

    length_squared = dx * dx + dy * dy
    px = rx - sx
    py = ry - sy
    t = max(0, min(1, (px * dx + py * dy) / length_squared))
    phantom_x = sx + t * dx
    phantom_y = sy + t * dy

    return phantom_x, phantom_y, 0

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room or room.cab_x is None or room.cab_y is None:
            raise ValueError(f"Комната {vertex} не найдена или координаты некорректны")
        graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment or segment.start_x is None or segment.start_y is None or segment.end_x is None or segment.end_y is None:
            raise ValueError(f"Сегмент {vertex} не найден или координаты некорректны")
        graph.add_vertex(f"segment_{id_}_start", (segment.start_x, segment.start_y, segment.floor_id))
        graph.add_vertex(f"segment_{id_}_end", (segment.end_x, segment.end_y, segment.floor_id))
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor or outdoor.start_x is None or outdoor.start_y is None or outdoor.end_x is None or outdoor.end_y is None:
            raise ValueError(f"Уличный сегмент {vertex} не найден или координаты некорректны")
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, 1))  # floor_id=1 для outdoor
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, 1))      # floor_id=1 для outdoor

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
    floor_ids.add(1)  # Добавляем floor_id=1 для outdoor
    return floor_ids

def build_graph(db: Session, start: str, end: str) -> Graph:
    graph = Graph()
    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    all_connections = db.query(Connection).all()

    relevant_segment_ids = {
        conn.segment_id for conn in all_connections if conn.segment_id
    } | {
        conn.from_segment_id for conn in all_connections if conn.from_segment_id
    } | {
        conn.to_segment_id for conn in all_connections if conn.to_segment_id
    }

    relevant_outdoor_ids = {
        conn.from_outdoor_id for conn in all_connections if conn.from_outdoor_id
    } | {
        conn.to_outdoor_id for conn in all_connections if conn.to_outdoor_id
    }

    building_ids = get_relevant_buildings(db, start, end)
    floor_ids = get_relevant_floors(db, start, end)

    rooms = db.query(Room).filter(
        Room.building_id.in_(building_ids),
        Room.floor_id.in_(floor_ids)
    ).all()
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices and room.cab_x is not None and room.cab_y is not None:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))

    segments = db.query(Segment).filter(
        Segment.id.in_(relevant_segment_ids)
    ).all()
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        if start_vertex not in graph.vertices and segment.start_x is not None and segment.start_y is not None:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices and segment.end_x is not None and segment.end_y is not None:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        if (segment.start_x is not None and segment.start_y is not None and
            segment.end_x is not None and segment.end_y is not None):
            weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
            graph.add_edge(start_vertex, end_vertex, weight)

    outdoor_segments = db.query(OutdoorSegment).filter(
        OutdoorSegment.id.in_(relevant_outdoor_ids)
    ).all()
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if (outdoor.start_x is not None and outdoor.start_y is not None and
            outdoor.end_x is not None and outdoor.end_y is not None):
            if start_vertex not in graph.vertices:
                graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 1))
            if end_vertex not in graph.vertices:
                graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 1))
            weight = sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
            graph.add_edge(start_vertex, end_vertex, weight)

    # Добавляем ребра на основе соединений
    for conn in all_connections:
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

            phantom_vertex = f"phantom_room_{conn.room_id}_segment_{conn.segment_id}"
            room_coords = graph.vertices[room_vertex]
            start_coords = graph.vertices[segment_start]
            end_coords = graph.vertices[segment_end]
            phantom_coords = find_phantom_point(room_coords, start_coords, end_coords)
            if phantom_coords[0] is not None and phantom_coords[1] is not None:
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

        # Соединение между сегментом и outdoor (улица или дверь)
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

        # Дополнительная обработка соединений типа "дверь" между сегментами и outdoor
        elif conn.type == "дверь" and ((conn.segment_id and conn.to_outdoor_id) or (conn.from_outdoor_id and conn.to_segment_id)):
            if conn.segment_id and conn.to_outdoor_id:
                segment = next((s for s in segments if s.id == conn.segment_id), None)
                to_outdoor = next((o for o in outdoor_segments if o.id == conn.to_outdoor_id), None)
                if segment and to_outdoor and f"segment_{conn.segment_id}_end" in graph.vertices and f"outdoor_{conn.to_outdoor_id}_start" in graph.vertices:
                    graph.add_edge(f"segment_{conn.segment_id}_end", f"outdoor_{conn.to_outdoor_id}_start", weight)
            if conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = next((o for o in outdoor_segments if o.id == conn.from_outdoor_id), None)
                to_segment = next((s for s in segments if s.id == conn.to_segment_id), None)
                if from_outdoor and to_segment and f"outdoor_{conn.from_outdoor_id}_end" in graph.vertices and f"segment_{conn.to_segment_id}_start" in graph.vertices:
                    graph.add_edge(f"outdoor_{conn.from_outdoor_id}_end", f"segment_{conn.to_segment_id}_start", weight)

    # Добавляем ребра между outdoor-сегментами для цепочек
    outdoor_connections = {}
    for conn in all_connections:
        if conn.type == "улица" and conn.from_outdoor_id and conn.to_outdoor_id:
            from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
            to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                weight = conn.weight if conn.weight else 1
                graph.add_edge(from_vertex, to_vertex, weight)
                if conn.from_outdoor_id not in outdoor_connections:
                    outdoor_connections[conn.from_outdoor_id] = []
                outdoor_connections[conn.from_outdoor_id].append((conn.to_outdoor_id, weight))

    # Соединяем сегменты через outdoor-цепочки
    segment_to_outdoor = {}
    outdoor_to_segment = {}
    for conn in all_connections:
        weight = conn.weight if conn.weight else 1
        if (conn.from_segment_id and conn.to_outdoor_id) or (conn.segment_id and conn.to_outdoor_id):
            seg_id = conn.from_segment_id if conn.from_segment_id else conn.segment_id
            segment_to_outdoor[seg_id] = (conn.to_outdoor_id, weight)
        if conn.from_outdoor_id and conn.to_segment_id:
            outdoor_to_segment[conn.from_outdoor_id] = (conn.to_segment_id, weight)

    for seg_id, (outdoor_id, weight1) in segment_to_outdoor.items():
        current_outdoor = outdoor_id
        total_weight = weight1
        visited = set()
        while current_outdoor in outdoor_connections and current_outdoor not in visited:
            visited.add(current_outdoor)
            for next_outdoor, outdoor_weight in outdoor_connections.get(current_outdoor, []):
                if next_outdoor in outdoor_to_segment:
                    target_seg_id, weight2 = outdoor_to_segment[next_outdoor]
                    from_vertex = f"segment_{seg_id}_end"
                    to_vertex = f"segment_{target_seg_id}_start"
                    if from_vertex in graph.vertices and to_vertex in graph.vertices:
                        final_weight = total_weight + outdoor_weight + weight2
                        graph.add_edge(from_vertex, to_vertex, final_weight)
                    break
                total_weight += outdoor_weight
                current_outdoor = next_outdoor

    return graph