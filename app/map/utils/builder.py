from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.utils.graph import Graph
from math import sqrt
import logging

logger = logging.getLogger(__name__)

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple) -> tuple:
    """Находит точку на сегменте, ближайшую к комнате"""
    rx, ry = room_coords[0], room_coords[1]
    sx, sy = segment_start[0], segment_start[1]
    ex, ey = segment_end[0], segment_end[1]
    
    # Вектор сегмента
    segment_dx = ex - sx
    segment_dy = ey - sy
    segment_len = sqrt(segment_dx**2 + segment_dy**2)
    
    if segment_len == 0:
        return segment_start
    
    # Нормализованный вектор сегмента
    nx = segment_dx / segment_len
    ny = segment_dy / segment_len
    
    # Вектор от начала сегмента до комнаты
    rx_rel = rx - sx
    ry_rel = ry - sy
    
    # Проекция на сегмент
    proj = rx_rel * nx + ry_rel * ny
    proj = max(0, min(segment_len, proj))  # Ограничиваем точку сегментом
    
    # Координаты фантомной точки
    px = sx + proj * nx
    py = sy + proj * ny
    
    return (px, py, segment_start[2])

def parse_vertex_id(vertex: str):
    parts = vertex.split("_")
    if len(parts) < 2:
        raise ValueError(f"Неверный формат вершины: {vertex}")
    return parts[0], int(parts[1])

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
    
    # Собираем все ID
    segment_ids = set()
    room_ids = set()
    outdoor_ids = set()

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

    # Загружаем все нужные объекты
    rooms = {r.id: r for r in db.query(Room).filter(Room.id.in_(room_ids)).all()}
    segments = {s.id: s for s in db.query(Segment).filter(Segment.id.in_(segment_ids)).all()}
    outdoors = {o.id: o for o in db.query(OutdoorSegment).filter(OutdoorSegment.id.in_(outdoor_ids)).all()}

    # Добавляем сегменты
    for segment in segments.values():
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.info(f"Added segment: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Добавляем уличные сегменты
    for outdoor in outdoors.values():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 1))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 1))
        
        weight = outdoor.weight if outdoor.weight else sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight)
        logger.info(f"Added outdoor segment: {start_vertex} <-> {end_vertex}, weight={weight}")

    # Обрабатываем соединения
    for conn in connections:
        weight = conn.weight if conn.weight else 2

        # 1. Соединение комната-сегмент
        if conn.room_id and conn.segment_id:
            room = rooms.get(conn.room_id)
            segment = segments.get(conn.segment_id)
            if room and segment:
                room_vertex = f"room_{room.id}"
                if room_vertex not in graph.vertices:
                    graph.add_vertex(room_vertex, (room.cab_x, room.cab_y, room.floor_id))
                add_phantom_connection(graph, room_vertex, segment, weight)

        # 2. Соединение сегмент-сегмент
        elif conn.from_segment_id and conn.to_segment_id:
            from_segment = segments.get(conn.from_segment_id)
            to_segment = segments.get(conn.to_segment_id)
            if from_segment and to_segment:
                from_end = f"segment_{from_segment.id}_end"
                to_start = f"segment_{to_segment.id}_start"

                if conn.type == "лестница":
                    # Создаем фантомную точку на сегменте, куда поворачиваем
                    phantom_coords = find_phantom_point(
                        (from_segment.end_x, from_segment.end_y, to_segment.floor_id),
                        (to_segment.start_x, to_segment.start_y, to_segment.floor_id),
                        (to_segment.end_x, to_segment.end_y, to_segment.floor_id)
                    )
                    phantom_vertex = f"phantom_stair_{conn.id}"
                    graph.add_vertex(phantom_vertex, phantom_coords)
                    graph.add_edge(from_end, phantom_vertex, weight)
                    graph.add_edge(phantom_vertex, to_start, weight)
                    logger.info(f"Added stair connection via phantom: {from_end} -> {phantom_vertex} -> {to_start}")
                else:
                    graph.add_edge(from_end, to_start, weight)
                    logger.info(f"Added segment connection: {from_end} <-> {to_start}")

        # 3. Соединения с уличными сегментами
        if conn.from_segment_id and conn.to_outdoor_id:
            from_segment = segments.get(conn.from_segment_id)
            to_outdoor = outdoors.get(conn.to_outdoor_id)
            if from_segment and to_outdoor:
                from_end = f"segment_{from_segment.id}_end"
                to_start = f"outdoor_{to_outdoor.id}_start"
                to_end = f"outdoor_{to_outdoor.id}_end"
                
                # Соединяем с обоими концами outdoor сегмента
                graph.add_edge(from_end, to_start, weight)
                graph.add_edge(from_end, to_end, weight)
                logger.info(f"Added segment-outdoor connection: {from_end} <-> {to_start}/{to_end}")

        if conn.from_outdoor_id and conn.to_segment_id:
            from_outdoor = outdoors.get(conn.from_outdoor_id)
            to_segment = segments.get(conn.to_segment_id)
            if from_outdoor and to_segment:
                from_start = f"outdoor_{from_outdoor.id}_start"
                from_end = f"outdoor_{from_outdoor.id}_end"
                to_start = f"segment_{to_segment.id}_start"
                
                # Соединяем с обоими концами outdoor сегмента
                graph.add_edge(from_start, to_start, weight)
                graph.add_edge(from_end, to_start, weight)
                logger.info(f"Added outdoor-segment connection: {from_start}/{from_end} <-> {to_start}")

        # 4. Соединения между outdoor сегментами
        if conn.from_outdoor_id and conn.to_outdoor_id:
            from_outdoor = outdoors.get(conn.from_outdoor_id)
            to_outdoor = outdoors.get(conn.to_outdoor_id)
            if from_outdoor and to_outdoor:
                # Соединяем все концы обоих сегментов
                for from_end in [f"outdoor_{from_outdoor.id}_start", f"outdoor_{from_outdoor.id}_end"]:
                    for to_end in [f"outdoor_{to_outdoor.id}_start", f"outdoor_{to_outdoor.id}_end"]:
                        graph.add_edge(from_end, to_end, weight)
                logger.info(f"Added outdoor-outdoor connection: outdoor_{from_outdoor.id} <-> outdoor_{to_outdoor.id}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph

def add_phantom_connection(graph: Graph, room_vertex: str, segment: Segment, weight: float):
    """Добавляет соединение комнаты с сегментом через фантомную точку"""
    room_coords = graph.vertices[room_vertex]
    segment_start = (segment.start_x, segment.start_y, segment.floor_id)
    segment_end = (segment.end_x, segment.end_y, segment.floor_id)
    
    # Создаем фантомную точку напротив двери
    phantom_coords = find_phantom_point(room_coords, segment_start, segment_end)
    phantom_vertex = f"phantom_room_{room_vertex.split('_')[1]}_segment_{segment.id}"
    graph.add_vertex(phantom_vertex, phantom_coords)
    
    # Соединяем комнату с фантомной точкой
    dist_to_phantom = sqrt((room_coords[0] - phantom_coords[0])**2 + (room_coords[1] - phantom_coords[1])**2)
    graph.add_edge(room_vertex, phantom_vertex, weight)
    
    # Соединяем фантомную точку с концами сегмента
    for end_point, end_type in [(segment_start, 'start'), (segment_end, 'end')]:
        dist = sqrt((phantom_coords[0] - end_point[0])**2 + (phantom_coords[1] - end_point[1])**2)
        end_vertex = f"segment_{segment.id}_{end_type}"
        if end_vertex in graph.vertices:
            graph.add_edge(phantom_vertex, end_vertex, dist)
    
    logger.info(f"Added phantom connection: {room_vertex} -> {phantom_vertex}")
    return phantom_vertex