from .graph import Graph
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.models.floor import Floor
from sqlalchemy.orm import Session
import math
import logging

logger = logging.getLogger(__name__)

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Начало построения графа для start={start}, end={end}")
    graph = Graph()

    # Проверка начальной и конечной комнаты
    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
        start_room = db.query(Room).filter(Room.id == start_id).first()
        end_room = db.query(Room).filter(Room.id == end_id).first()
        if not start_room or not end_room:
            logger.error(f"Комната с id {start_id} или {end_id} не найдена")
            raise ValueError(f"Комната с id {start_id} или {end_id} не найдена")
    except ValueError as e:
        logger.error(f"Ошибка при парсинге ID комнат из {start} или {end}: {e}")
        raise ValueError(f"Неверный формат комнаты, ожидается room_<id>, получено {start} или {end}")

    # Получение этажей
    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    start_floor_number = start_floor.floor_number if start_floor else start_room.floor_id
    end_floor_number = end_floor.floor_number if end_floor else end_room.floor_id
    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Актуальные ID зданий: {building_ids}, этажей: {floor_ids}")

    # Определяем, нужно ли включать уличные сегменты
    include_outdoor = len(building_ids) > 1

    # Добавление комнат
    rooms = db.query(Room).filter(Room.building_id.in_(building_ids)).all()
    for room in rooms:
        if not hasattr(room, 'floor_id'):
            logger.error(f"Объект комнаты не имеет атрибута floor_id: {room}")
            raise ValueError(f"Некорректный объект комнаты: {room}")
        floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        floor_number = floor.floor_number if floor else room.floor_id
        vertex = f"room_{room.id}"
        graph.add_vertex(vertex, {"coords": (room.cab_x, room.cab_y, floor_number), "building_id": room.building_id})

    # Добавление сегментов
    segments = {}
    floor_numbers = {}
    segment_query = db.query(Segment).filter(Segment.building_id.in_(building_ids)).all()
    for segment in segment_query:
        floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        floor_number = floor.floor_number if floor else segment.floor_id
        floor_numbers[segment.id] = floor_number
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, floor_number), "building_id": segment.building_id})
        segments[segment.id] = (start_vertex, end_vertex)
        weight = max(0.1, math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2))
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})

    # Добавление уличных сегментов
    outdoor_segments = {}
    if include_outdoor:
        for outdoor in db.query(OutdoorSegment).all():
            start_vertex = f"outdoor_{outdoor.id}_start"
            end_vertex = f"outdoor_{outdoor.id}_end"
            coords_start = (outdoor.start_x, outdoor.start_y, 1)
            coords_end = (outdoor.end_x, outdoor.end_y, 1)
            graph.add_vertex(start_vertex, {"coords": coords_start, "building_id": None})
            graph.add_vertex(end_vertex, {"coords": coords_end, "building_id": None})
            weight = outdoor.weight if outdoor.weight else max(0.1, math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2))
            graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
            outdoor_segments[outdoor.id] = (start_vertex, end_vertex)

    # Соединение комнат с сегментами
    for room in rooms:
        room_vertex = f"room_{room.id}"
        connections = db.query(Connection).filter(Connection.room_id == room.id).all()
        for conn in connections:
            if conn.segment_id and conn.segment_id in segments:
                segment_start, segment_end = segments[conn.segment_id]
                phantom_vertex = f"phantom_room_{room.id}_segment_{conn.segment_id}"
                floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
                floor_number = floor.floor_number if floor else room.floor_id
                segment_data = db.query(Segment).filter(Segment.id == conn.segment_id).first()
                if segment_data:
                    # Проверяем, является ли сегмент лестничным (на основе connections)
                    stair_conn = db.query(Connection).filter(
                        Connection.type == "лестница",
                        Connection.from_segment_id == conn.segment_id
                    ).first()
                    if stair_conn:
                        # Для лестничного сегмента используем координаты конца сегмента
                        x = segment_data.end_x
                        y = segment_data.end_y
                    else:
                        # Для обычного сегмента используем координаты комнаты, выровненные по оси
                        if segment_data.start_x == segment_data.end_x:  # Вертикальный сегмент
                            x = segment_data.start_x
                            y = room.cab_y
                        else:  # Горизонтальный сегмент
                            x = room.cab_x
                            y = segment_data.start_y
                    coords = (x, y, floor_number)
                else:
                    coords = (room.cab_x, room.cab_y, floor_number)
                graph.add_vertex(phantom_vertex, {"coords": coords, "building_id": room.building_id})
                weight = conn.weight if conn.weight else 2.0
                graph.add_edge(room_vertex, phantom_vertex, weight, {"type": "phantom"})
                segment_weight = weight * 1.5
                graph.add_edge(phantom_vertex, segment_start, segment_weight, {"type": "segment"})
                graph.add_edge(phantom_vertex, segment_end, segment_weight, {"type": "segment"})

    # Обработка соединений (лестницы, двери, улица)
    for conn in db.query(Connection).all():
        if conn.from_segment_id and conn.to_segment_id:
            if conn.from_segment_id not in segments or conn.to_segment_id not in segments:
                continue
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_floor = floor_numbers[conn.from_segment_id]
            to_floor = floor_numbers[conn.to_segment_id]
            phantom_from = f"phantom_stair_{conn.from_segment_id}_to_{conn.to_segment_id}"
            phantom_to = f"phantom_stair_{conn.to_segment_id}_from_{conn.from_segment_id}"
            from_segment = db.query(Segment).filter(Segment.id == conn.from_segment_id).first()
            to_segment = db.query(Segment).filter(Segment.id == conn.to_segment_id).first()
            if from_segment and to_segment:
                # Используем координаты конца from_segment для лестницы
                x = from_segment.end_x
                y = from_segment.end_y
                from_coords = (x, y, from_floor)
                to_coords = (x, y, to_floor)
                logger.info(f"Лестница {phantom_from}: coords={from_coords}, {phantom_to}: coords={to_coords}")
                graph.add_vertex(phantom_from, {"coords": from_coords, "building_id": None})
                graph.add_vertex(phantom_to, {"coords": to_coords, "building_id": None})
                weight = conn.weight if conn.weight else 2.0
                # Соединяем только с концом сегмента, чтобы начать движение с лестницы
                graph.add_edge(phantom_from, phantom_to, weight, {"type": "лестница"})
                graph.add_edge(from_end, phantom_from, weight, {"type": "segment"})
                graph.add_edge(phantom_to, to_end, weight, {"type": "segment"})
        elif include_outdoor and conn.from_segment_id and conn.to_outdoor_id:
            if conn.from_segment_id not in segments or conn.to_outdoor_id not in outdoor_segments:
                continue
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            phantom_from = f"phantom_segment_{conn.from_segment_id}_to_outdoor_{conn.to_outdoor_id}"
            from_coords = graph.get_vertex_data(from_end)["coords"]
            graph.add_vertex(phantom_from, {"coords": from_coords, "building_id": None})
            weight = conn.weight if conn.weight else 2.0
            graph.add_edge(from_start, phantom_from, weight, {"type": "segment"})
            graph.add_edge(from_end, phantom_from, weight, {"type": "segment"})
            graph.add_edge(phantom_from, to_start, weight, {"type": "дверь"})
            graph.add_edge(phantom_from, to_end, weight, {"type": "дверь"})
        elif include_outdoor and conn.from_outdoor_id and conn.to_segment_id:
            if conn.from_outdoor_id not in outdoor_segments or conn.to_segment_id not in segments:
                continue
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = segments[conn.to_segment_id]
            phantom_to = f"phantom_segment_{conn.to_segment_id}_from_outdoor_{conn.from_outdoor_id}"
            to_coords = graph.get_vertex_data(to_end)["coords"]
            graph.add_vertex(phantom_to, {"coords": to_coords, "building_id": None})
            weight = conn.weight if conn.weight else 2.0
            graph.add_edge(from_start, phantom_to, weight, {"type": "дверь"})
            graph.add_edge(from_end, phantom_to, weight, {"type": "дверь"})
            graph.add_edge(phantom_to, to_end, weight, {"type": "segment"})
        elif include_outdoor and conn.from_outdoor_id and conn.to_outdoor_id:
            if conn.from_outdoor_id not in outdoor_segments or conn.to_outdoor_id not in outdoor_segments:
                continue
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            weight = conn.weight if conn.weight else 10.0
            graph.add_edge(from_start, to_start, weight, {"type": "улица"})
            graph.add_edge(from_end, to_end, weight, {"type": "улица"})

    logger.info(f"Граф построен: {len(graph.vertices)} вершин, {sum(len(neighbors) for neighbors in graph.edges.values()) // 2} рёбер")
    return graph