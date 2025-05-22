from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.utils.graph import Graph
from math import sqrt, atan2, degrees
import logging

logger = logging.getLogger(__name__)

VALID_TYPES = {"room", "segment", "outdoor"}

def parse_vertex_id(vertex: str):
    """Парсит ID вершины и возвращает тип и числовой ID"""
    parts = vertex.split("_")
    if len(parts) < 2:
        raise ValueError(f"Неверный формат вершины: {vertex}")
    return parts[0], int(parts[1])

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple, prev_coords: tuple = None) -> tuple:
    rx, ry, rfloor = room_coords
    sx, sy, sfloor = segment_start
    ex, ey, efloor = segment_end

    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return sx, sy, sfloor

    length = sqrt(length_squared)
    nx, ny = dx / length, dy / length

    dot_product = (rx - sx) * nx + (ry - sy) * ny
    t = max(0, min(1, dot_product / length))

    phantom_x = sx + t * dx
    phantom_y = sy + t * dy
    phantom_floor = rfloor if abs(rfloor - sfloor) <= 1 else sfloor

    if prev_coords:
        px, py, _ = prev_coords
        dx1, dy1 = sx - px, sy - py
        dx2, dy2 = ex - px, ey - py
        dist_to_start = sqrt(dx1 * dx1 + dy1 * dy1)
        dist_to_end = sqrt(dx2 * dx2 + dy2 * dy2)
        if dist_to_start < dist_to_end:
            return sx, sy, sfloor
        return ex, ey, efloor

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

    # Добавляем начальную и конечную точки
    for vertex in [start, end]:
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room:
                graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
                logger.info(f"Added {vertex} -> ({room.cab_x}, {room.cab_y}, {room.floor_id})")

    # Получаем все соединения
    connections = db.query(Connection).all()
    
    # Создаем множества для отслеживания всех сегментов и комнат
    segment_ids = set()
    room_ids = set()
    outdoor_ids = set()

    # Собираем все ID из соединений
    for conn in connections:
        if conn.room_id:
            room_ids.add(conn.room_id)
        if conn.segment_id:
            segment_ids.add(conn.segment_id)
        if conn.from_segment_id:
            segment_ids.add(conn.from_segment_id)
        if conn.to_segment_id:
            segment_ids.add(conn.to_segment_id)
        if conn.from_outdoor_id:
            outdoor_ids.add(conn.from_outdoor_id)
        if conn.to_outdoor_id:
            outdoor_ids.add(conn.to_outdoor_id)

    # Добавляем все задействованные комнаты
    rooms = db.query(Room).filter(Room.id.in_(room_ids)).all()
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
            logger.info(f"Added room vertex: {vertex} -> ({room.cab_x}, {room.cab_y}, {room.floor_id})")

    # Добавляем все задействованные сегменты
    segments = db.query(Segment).filter(Segment.id.in_(segment_ids)).all()
    segment_dict = {s.id: s for s in segments}
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        # Соединяем начало и конец сегмента
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.info(f"Added segment: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Добавляем все задействованные уличные сегменты
    outdoors = db.query(OutdoorSegment).filter(OutdoorSegment.id.in_(outdoor_ids)).all()
    for outdoor in outdoors:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 1))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 1))
        # Соединяем начало и конец уличного сегмента
        weight = outdoor.weight if outdoor.weight else sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.info(f"Added outdoor segment: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Обрабатываем все соединения из таблицы Connections
    for conn in connections:
        weight = conn.weight if conn.weight else 2  # Используем вес из таблицы или дефолтный

        # Соединение комната-сегмент
        if conn.room_id and conn.segment_id:
            room_vertex = f"room_{conn.room_id}"
            segment = segment_dict.get(conn.segment_id)
            if segment and room_vertex in graph.vertices:
                # Соединяем комнату с обоими концами сегмента
                for segment_end in [f"segment_{conn.segment_id}_start", f"segment_{conn.segment_id}_end"]:
                    if segment_end in graph.vertices:
                        graph.add_edge(room_vertex, segment_end, weight)
                        logger.info(f"Added room-segment connection: {room_vertex} <-> {segment_end}, weight={weight}")

        # Соединение сегмент-сегмент
        elif conn.from_segment_id and conn.to_segment_id:
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.info(f"Added segment-segment connection: {from_vertex} <-> {to_vertex}, weight={weight}")

        # Соединения с уличными сегментами
        if conn.from_segment_id and conn.to_outdoor_id:
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"outdoor_{conn.to_outdoor_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.info(f"Added segment-outdoor connection: {from_vertex} <-> {to_vertex}, weight={weight}")

        if conn.from_outdoor_id and conn.to_segment_id:
            from_vertex = f"outdoor_{conn.from_outdoor_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                graph.add_edge(from_vertex, to_vertex, weight)
                logger.info(f"Added outdoor-segment connection: {from_vertex} <-> {to_vertex}, weight={weight}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph