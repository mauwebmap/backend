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

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple) -> tuple:
    """
    Находит ближайшую точку на сегменте (проекцию точки комнаты на линию сегмента).
    room_coords: (x, y, floor) - координаты комнаты
    segment_start: (x, y, floor) - начало сегмента
    segment_end: (x, y, floor) - конец сегмента
    Возвращает: (x, y, floor) - координаты фантомной точки
    """
    rx, ry, _ = room_coords
    sx, sy, _ = segment_start
    ex, ey, _ = segment_end

    # Вектор сегмента
    dx = ex - sx
    dy = ey - sy

    # Если сегмент - точка (начало и конец совпадают)
    if dx == 0 and dy == 0:
        return sx, sy, 0  # Возвращаем 0 как заглушку для floor

    # Длина сегмента (квадрат)
    length_squared = dx * dx + dy * dy

    # Вектор от начала сегмента к точке комнаты
    px = rx - sx
    py = ry - sy

    # Скалярное произведение для нахождения параметра t проекции
    dot_product = px * dx + py * dy
    t = dot_product / length_squared

    # Ограничиваем t в диапазоне [0, 1], чтобы точка была на сегменте
    t = max(0, min(1, t))

    # Координаты проекции
    phantom_x = sx + t * dx
    phantom_y = sy + t * dy

    return phantom_x, phantom_y, 0  # Возвращаем 0 как заглушку для floor

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
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, None))  # None вместо floor_id
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, None))  # None вместо floor_id
        logger.debug(f"[add_vertex_to_graph] Added outdoor segment vertices: outdoor_{id_}_start -> {(outdoor.start_x, outdoor.start_y, None)}, outdoor_{id_}_end -> {(outdoor.end_x, outdoor.end_y, None)}")

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
    """Получение списка этажей, связанных с начальной и конечной точками (только для комнат и сегментов)"""
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
    graph = Graph()
    add_vertex_to_graph(graph, db, start)
    add_vertex_to_graph(graph, db, end)

    # Сначала загрузим все соединения, чтобы определить необходимые сегменты
    all_connections = db.query(Connection).all()
    logger.debug(f"[build_graph] Loaded all connections: {[f'id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}, from_segment_id={conn.from_segment_id}, to_segment_id={conn.to_segment_id}, from_outdoor_id={conn.from_outdoor_id}, to_outdoor_id={conn.to_outdoor_id}' for conn in all_connections]}")

    # Соберем все segment_id, участвующие в соединениях
    relevant_segment_ids = set()
    for conn in all_connections:
        if conn.segment_id:
            relevant_segment_ids.add(conn.segment_id)
        if conn.from_segment_id:
            relevant_segment_ids.add(conn.from_segment_id)
        if conn.to_segment_id:
            relevant_segment_ids.add(conn.to_segment_id)

    # Соберем все outdoor_id
    relevant_outdoor_ids = set()
    for conn in all_connections:
        if conn.from_outdoor_id:
            relevant_outdoor_ids.add(conn.from_outdoor_id)
        if conn.to_outdoor_id:
            relevant_outdoor_ids.add(conn.to_outdoor_id)

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

    # Загрузка всех сегментов, участвующих в соединениях
    segments = db.query(Segment).filter(
        Segment.id.in_(relevant_segment_ids)
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
    outdoor_segments = db.query(OutdoorSegment).filter(
        OutdoorSegment.id.in_(relevant_outdoor_ids)
    ).all()
    logger.debug(f"[build_graph] Loaded outdoor segments: {[f'id={outdoor.id}, start_x={outdoor.start_x}, start_y={outdoor.start_y}, end_x={outdoor.end_x}, end_y={outdoor.end_y}' for outdoor in outdoor_segments]}")
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            if outdoor.start_x is None or outdoor.start_y is None:
                logger.warning(f"[build_graph] Outdoor segment {outdoor.id} has invalid start coordinates: start_x={outdoor.start_x}, start_y={outdoor.start_y}")
                continue
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, None))
        if end_vertex not in graph.vertices:
            if outdoor.end_x is None or outdoor.end_y is None:
                logger.warning(f"[build_graph] Outdoor segment {outdoor.id} has invalid end coordinates: end_x={outdoor.end_x}, end_y={outdoor.end_y}")
                continue
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, None))
        weight = sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.debug(f"[build_graph] Added outdoor segment vertices: {start_vertex} -> {(outdoor.start_x, outdoor.start_y, None)}, {end_vertex} -> {(outdoor.end_x, outdoor.end_y, None)}")
        logger.debug(f"[build_graph] Added edge: {start_vertex} -> {end_vertex}, weight={weight}")

    # Фильтрация соединений
    connections = [conn for conn in all_connections if (
        (conn.room_id and conn.room_id in [r.id for r in rooms]) or
        (conn.segment_id and conn.segment_id in [s.id for s in segments]) or
        (conn.from_segment_id and conn.from_segment_id in [s.id for s in segments]) or
        (conn.to_segment_id and conn.to_segment_id in [s.id for s in segments]) or
        (conn.from_outdoor_id and conn.from_outdoor_id in [o.id for o in outdoor_segments]) or
        (conn.to_outdoor_id and conn.to_outdoor_id in [o.id for o in outdoor_segments])
    )]
    logger.debug(f"[build_graph] Filtered connections: {[f'id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}, from_segment_id={conn.from_segment_id}, to_segment_id={conn.to_segment_id}, from_outdoor_id={conn.from_outdoor_id}, to_outdoor_id={conn.to_outdoor_id}' for conn in connections]}")

    # Список сегментов, участвующих в переходах (лестницах)
    transition_segments = set()
    for conn in connections:
        if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            transition_segments.add(conn.from_segment_id)
            transition_segments.add(conn.to_segment_id)

    # Добавление рёбер на основе соединений
    for conn in connections:
        logger.debug(f"[build_graph] Processing connection: id={conn.id}, type={conn.type}, room_id={conn.room_id}, segment_id={conn.segment_id}, from_segment_id={conn.from_segment_id}, to_segment_id={conn.to_segment_id}, from_outdoor_id={conn.from_outdoor_id}, to_outdoor_id={conn.to_outdoor_id}")
        weight = conn.weight if conn.weight is not None else 1

        # Соединение между комнатой и сегментом (дверь)
        if conn.type == "дверь" and conn.room_id and conn.segment_id:
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

            # Находим фантомную точку на сегменте для всех дверей
            room_coords = graph.vertices[room_vertex]
            start_coords = graph.vertices[segment_start]
            end_coords = graph.vertices[segment_end]
            phantom_coords = find_phantom_point(room_coords, start_coords, end_coords)

            # Добавляем фантомную точку как новую вершину
            phantom_vertex = f"phantom_room_{conn.room_id}_segment_{conn.segment_id}"
            graph.add_vertex(phantom_vertex, phantom_coords)
            logger.debug(f"[build_graph] Added phantom vertex: {phantom_vertex} -> {phantom_coords}")

            # Соединяем комнату с фантомной точкой
            dist_to_phantom = sqrt((room_coords[0] - phantom_coords[0]) ** 2 + (room_coords[1] - phantom_coords[1]) ** 2)
            graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom)
            logger.debug(f"[build_graph] Adding edge: {room_vertex} -> {phantom_vertex}, weight={dist_to_phantom}, from_coords={room_coords}, to_coords={phantom_coords}")

            # Соединяем фантомную точку с началом и концом сегмента
            dist_phantom_to_start = sqrt((phantom_coords[0] - start_coords[0]) ** 2 + (phantom_coords[1] - start_coords[1]) ** 2)
            dist_phantom_to_end = sqrt((phantom_coords[0] - end_coords[0]) ** 2 + (phantom_coords[1] - end_coords[1]) ** 2)
            graph.add_edge(phantom_vertex, segment_start, dist_phantom_to_start)
            graph.add_edge(phantom_vertex, segment_end, dist_phantom_to_end)
            logger.debug(f"[build_graph] Adding edge: {phantom_vertex} -> {segment_start}, weight={dist_phantom_to_start}")
            logger.debug(f"[build_graph] Adding edge: {phantom_vertex} -> {segment_end}, weight={dist_phantom_to_end}")

        # Соединение между сегментами (лестница)
        elif conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
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

        # Соединение между сегментом и уличным сегментом (улица)
        elif conn.type == "улица":
            if conn.from_segment_id and conn.to_outdoor_id:
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
            if conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == conn.from_outdoor_id).first()
                to_segment = db.query(Segment).filter(Segment.id == conn.to_segment_id).first()
                if not from_outdoor or not to_segment:
                    logger.warning(f"[build_graph] Outdoor {conn.from_outdoor_id} or segment {conn.to_segment_id} not found for connection {conn.id}")
                    continue
                from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                to_vertex = f"segment_{conn.to_segment_id}_start"
                if from_vertex not in graph.vertices or to_vertex not in graph.vertices:
                    logger.warning(f"[build_graph] Outdoor vertex {from_vertex} or segment vertex {to_vertex} not in graph for connection {conn.id}")
                    continue
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.debug(f"[build_graph] Adding edge: {from_vertex} -> {to_vertex}, weight={weight}")

        # Соединение между сегментом и уличным сегментом (дверь)
        elif conn.type == "дверь":
            if conn.segment_id and conn.to_outdoor_id:
                from_segment = db.query(Segment).filter(Segment.id == conn.segment_id).first()
                to_outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == conn.to_outdoor_id).first()
                if not from_segment:
                    logger.warning(f"[build_graph] Segment {conn.segment_id} not found for connection {conn.id}")
                    continue
                if not to_outdoor:
                    logger.warning(f"[build_graph] Outdoor {conn.to_outdoor_id} not found for connection {conn.id}")
                    continue
                from_vertex = f"segment_{conn.segment_id}_end"
                to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
                if from_vertex not in graph.vertices:
                    logger.warning(f"[build_graph] Segment vertex {from_vertex} not in graph for connection {conn.id}")
                    continue
                if to_vertex not in graph.vertices:
                    logger.warning(f"[build_graph] Outdoor vertex {to_vertex} not in graph for connection {conn.id}")
                    continue
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.debug(f"[build_graph] Adding edge: {from_vertex} -> {to_vertex}, weight={weight}")
            elif conn.from_outdoor_id and conn.to_segment_id:
                from_outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == conn.from_outdoor_id).first()
                to_segment = db.query(Segment).filter(Segment.id == conn.to_segment_id).first()
                if not from_outdoor:
                    logger.warning(f"[build_graph] Outdoor {conn.from_outdoor_id} not found for connection {conn.id}")
                    continue
                if not to_segment:
                    logger.warning(f"[build_graph] Segment {conn.to_segment_id} not found for connection {conn.id}")
                    continue
                from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
                to_vertex = f"segment_{conn.to_segment_id}_start"
                if from_vertex not in graph.vertices:
                    logger.warning(f"[build_graph] Outdoor vertex {from_vertex} not in graph for connection {conn.id}")
                    continue
                if to_vertex not in graph.vertices:
                    logger.warning(f"[build_graph] Segment vertex {to_vertex} not in graph for connection {conn.id}")
                    continue
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.debug(f"[build_graph] Adding edge: {from_vertex} -> {to_vertex}, weight={weight}")

    # Соединяем фантомные точки напрямую, если они на одном сегменте и сегмент не участвует в переходе
    phantom_vertices = [v for v in graph.vertices if v.startswith("phantom_")]
    for i, pv1 in enumerate(phantom_vertices):
        for pv2 in phantom_vertices[i + 1:]:
            # Извлекаем segment_id из названий вершин
            segment_id1 = int(pv1.split("_")[4])
            segment_id2 = int(pv2.split("_")[4])
            if segment_id1 == segment_id2:
                # Соединяем фантомные точки напрямую
                weight = sqrt(
                    (graph.vertices[pv1][0] - graph.vertices[pv2][0]) ** 2 +
                    (graph.vertices[pv1][1] - graph.vertices[pv2][1]) ** 2
                )
                graph.add_edge(pv1, pv2, weight)
                logger.debug(f"[build_graph] Direct connection between phantom vertices: {pv1} -> {pv2}, weight={weight}")

    # Соединяем точки перехода (после лестницы) с фантомными точками на том же этаже
    for conn in connections:
        if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            from_segment = db.query(Segment).filter(Segment.id == conn.from_segment_id).first()
            to_segment = db.query(Segment).filter(Segment.id == conn.to_segment_id).first()
            if not from_segment or not to_segment:
                continue
            # Точка входа на следующем этаже
            entry_point = f"segment_{conn.to_segment_id}_start"
            entry_floor = to_segment.floor_id

            # Находим все фантомные точки на этом этаже
            for pv in phantom_vertices:
                pv_segment_id = int(pv.split("_")[4])
                pv_segment = db.query(Segment).filter(Segment.id == pv_segment_id).first()
                if not pv_segment:
                    continue
                if pv_segment.floor_id == entry_floor:
                    # Соединяем точку входа с фантомной точкой напрямую
                    weight = sqrt(
                        (graph.vertices[entry_point][0] - graph.vertices[pv][0]) ** 2 +
                        (graph.vertices[entry_point][1] - graph.vertices[pv][1]) ** 2
                    )
                    graph.add_edge(entry_point, pv, weight)
                    logger.debug(f"[build_graph] Direct connection from transition entry {entry_point} to phantom vertex {pv}, weight={weight}")

    logger.debug(f"Vertices: {graph.vertices}")
    logger.debug(f"Edges: {dict(graph.edges)}")
    return graph