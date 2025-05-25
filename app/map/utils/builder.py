from .graph import Graph
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.models.floor import Floor
from sqlalchemy.orm import Session
import logging
import math

logger = logging.getLogger(__name__)

def find_closest_point_on_segment(x: float, y: float, start_x: float, start_y: float, end_x: float, end_y: float) -> tuple:
    seg_dx = end_x - start_x
    seg_dy = end_y - start_y
    seg_len_sq = seg_dx ** 2 + seg_dy ** 2
    if seg_len_sq == 0:
        logger.warning(f"Нулевая длина сегмента от ({start_x}, {start_y}) до ({end_x}, {end_y})")
        return start_x, start_y
    dx = x - start_x
    dy = y - start_y
    t = max(0, min(1, (dx * seg_dx + dy * seg_dy) / seg_len_sq))
    return start_x + t * seg_dx, start_y + t * seg_dy

def align_coordinates(from_coords: tuple, to_coords: tuple, from_seg_start: tuple, from_seg_end: tuple, to_seg_start: tuple, to_seg_end: tuple) -> tuple:
    from_x, from_y, from_z = from_coords
    to_x, to_y, to_z = to_coords
    if abs(from_x - to_x) < 1e-6 and abs(from_y - to_y) < 1e-6:
        return from_coords, to_coords
    aligned_x = (from_x + to_x) / 2 if abs(from_x - to_x) > 10 else from_x
    aligned_y = (from_y + to_y) / 2 if abs(from_y - to_y) > 10 else from_y
    return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Начало построения графа для {start} -> {end}")
    graph = Graph()

    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
        start_room = db.query(Room).filter(Room.id == start_id).first()
        end_room = db.query(Room).filter(Room.id == end_id).first()
        if not start_room or not end_room:
            raise ValueError(f"Комната {start_id} или {end_id} не найдена")
    except ValueError as e:
        logger.error(f"Ошибка парсинга ID: {e}")
        raise

    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    start_floor_number = start_floor.floor_number if start_floor else start_room.floor_id
    end_floor_number = end_floor.floor_number if end_floor else end_room.floor_id

    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_floor_number), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_floor_number), "building_id": end_room.building_id})

    building_ids = {start_room.building_id, end_room.building_id} - {None}
    segments = {}
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        floor_number = seg_floor.floor_number if seg_floor else segment.floor_id
        start_v = f"segment_{segment.id}_start"
        end_v = f"segment_{segment.id}_end"
        if start_v not in graph.vertices:  # Предотвращение дубликатов
            graph.add_vertex(start_v, {"coords": (segment.start_x, segment.start_y, floor_number), "building_id": segment.building_id})
        if end_v not in graph.vertices:
            graph.add_vertex(end_v, {"coords": (segment.end_x, segment.end_y, floor_number), "building_id": segment.building_id})
        segments[segment.id] = (start_v, end_v)
        weight = math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        if (start_v, end_v) not in graph.edges and (end_v, start_v) not in graph.edges:
            graph.add_edge(start_v, end_v, weight, {"type": "segment"})
            graph.add_edge(end_v, start_v, weight, {"type": "segment"})
        logger.debug(f"Сегмент: {start_v} ↔ {end_v}, вес={weight}")

    outdoor_segments = {}
    for outdoor in db.query(OutdoorSegment).all():
        start_v = f"outdoor_{outdoor.id}_start"
        end_v = f"outdoor_{outdoor.id}_end"
        if start_v not in graph.vertices:
            graph.add_vertex(start_v, {"coords": (outdoor.start_x, outdoor.start_y, 1), "building_id": None})
        if end_v not in graph.vertices:
            graph.add_vertex(end_v, {"coords": (outdoor.end_x, outdoor.end_y, 1), "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        if (start_v, end_v) not in graph.edges and (end_v, start_v) not in graph.edges:
            graph.add_edge(start_v, end_v, weight, {"type": "outdoor"})
            graph.add_edge(end_v, start_v, weight, {"type": "outdoor"})
        outdoor_segments[outdoor.id] = (start_v, end_v)
        logger.debug(f"Уличный сегмент: {start_v} ↔ {end_v}, вес={weight}")

    for room_id, room in [(start_id, start_room), (end_id, end_room)]:
        room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        floor_number = room_floor.floor_number if room_floor else room.floor_id
        room_v = f"room_{room_id}"
        for conn in db.query(Connection).filter(Connection.room_id == room_id).all():
            if conn.segment_id and conn.segment_id in segments:
                seg_start, seg_end = segments[conn.segment_id]
                closest_x, closest_y = find_closest_point_on_segment(
                    room.cab_x, room.cab_y,
                    graph.get_vertex_data(seg_start)["coords"][0],
                    graph.get_vertex_data(seg_start)["coords"][1],
                    graph.get_vertex_data(seg_end)["coords"][0],
                    graph.get_vertex_data(seg_end)["coords"][1]
                )
                phantom_v = f"phantom_room_{room_id}_segment_{conn.segment_id}"
                if phantom_v not in graph.vertices:
                    graph.add_vertex(phantom_v, {"coords": (closest_x, closest_y, floor_number), "building_id": room.building_id})
                weight = conn.weight or 2.0
                if (room_v, phantom_v) not in graph.edges and (phantom_v, room_v) not in graph.edges:
                    graph.add_edge(room_v, phantom_v, weight, {"type": "phantom"})
                    graph.add_edge(phantom_v, room_v, weight, {"type": "phantom"})
                logger.debug(f"Фантом: {phantom_v} ↔ {room_v}, вес={weight}")

    for conn in db.query(Connection).all():
        if conn.from_segment_id and conn.to_segment_id and conn.from_segment_id in segments and conn.to_segment_id in segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_coords = graph.get_vertex_data(from_end)["coords"]
            to_coords = graph.get_vertex_data(to_start)["coords"]
            (from_x, from_y, from_z), (to_x, to_y, to_z) = align_coordinates(
                from_coords, to_coords,
                graph.get_vertex_data(from_start)["coords"][:2],
                from_coords[:2],
                to_coords[:2],
                graph.get_vertex_data(to_end)["coords"][:2]
            )
            phantom_from = f"phantom_stair_{conn.from_segment_id}_to_{conn.to_segment_id}"
            phantom_to = f"phantom_stair_{conn.to_segment_id}_from_{conn.from_segment_id}"
            if phantom_from not in graph.vertices:
                graph.add_vertex(phantom_from, {"coords": (from_x, from_y, from_z), "building_id": None})
            if phantom_to not in graph.vertices:
                graph.add_vertex(phantom_to, {"coords": (to_x, to_y, to_z), "building_id": None})
            weight = max(conn.weight or 10.0, 0.1)
            if (phantom_from, phantom_to) not in graph.edges and (phantom_to, phantom_from) not in graph.edges:
                graph.add_edge(phantom_from, phantom_to, weight, {"type": "лестница"})
                graph.add_edge(phantom_to, phantom_from, weight, {"type": "лестница"})
            logger.debug(f"Лестница: {phantom_from} ↔ {phantom_to}, вес={weight}")

        elif conn.from_segment_id and conn.to_outdoor_id and conn.from_segment_id in segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            door_x, door_y = (graph.get_vertex_data(to_start)["coords"][0] + graph.get_vertex_data(to_end)["coords"][0]) / 2, \
                             (graph.get_vertex_data(to_start)["coords"][1] + graph.get_vertex_data(to_end)["coords"][1]) / 2
            from_closest_x, from_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                graph.get_vertex_data(from_start)["coords"][0],
                graph.get_vertex_data(from_start)["coords"][1],
                graph.get_vertex_data(from_end)["coords"][0],
                graph.get_vertex_data(from_end)["coords"][1]
            )
            from_coords = (from_closest_x, from_closest_y, graph.get_vertex_data(from_end)["coords"][2])
            to_coords = graph.get_vertex_data(to_start)["coords"]
            (from_x, from_y, from_z), (to_x, to_y, to_z) = align_coordinates(
                from_coords, to_coords,
                graph.get_vertex_data(from_start)["coords"][:2],
                from_coords[:2],
                to_coords[:2],
                graph.get_vertex_data(to_end)["coords"][:2]
            )
            phantom_v = f"phantom_segment_{conn.from_segment_id}_to_outdoor_{conn.to_outdoor_id}"
            if phantom_v not in graph.vertices:
                graph.add_vertex(phantom_v, {"coords": (from_x, from_y, from_z), "building_id": None})
            weight = conn.weight or 10.0
            if (phantom_v, to_start) not in graph.edges and (to_start, phantom_v) not in graph.edges:
                graph.add_edge(phantom_v, to_start, weight, {"type": "переход"})
                graph.add_edge(to_start, phantom_v, weight, {"type": "переход"})
            logger.debug(f"Переход: {phantom_v} ↔ {to_start}, вес={weight}")

        elif conn.from_outdoor_id and conn.to_segment_id and conn.from_outdoor_id in outdoor_segments and conn.to_segment_id in segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = segments[conn.to_segment_id]
            door_x, door_y = (graph.get_vertex_data(from_start)["coords"][0] + graph.get_vertex_data(from_end)["coords"][0]) / 2, \
                             (graph.get_vertex_data(from_start)["coords"][1] + graph.get_vertex_data(from_end)["coords"][1]) / 2
            to_closest_x, to_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                graph.get_vertex_data(to_start)["coords"][0],
                graph.get_vertex_data(to_start)["coords"][1],
                graph.get_vertex_data(to_end)["coords"][0],
                graph.get_vertex_data(to_end)["coords"][1]
            )
            from_coords = graph.get_vertex_data(from_end)["coords"]
            to_coords = (to_closest_x, to_closest_y, graph.get_vertex_data(to_start)["coords"][2])
            (from_x, from_y, from_z), (to_x, to_y, to_z) = align_coordinates(
                from_coords, to_coords,
                from_coords[:2],
                graph.get_vertex_data(from_start)["coords"][:2],
                to_coords[:2],
                graph.get_vertex_data(to_end)["coords"][:2]
            )
            phantom_v = f"phantom_segment_{conn.to_segment_id}_from_outdoor_{conn.from_outdoor_id}"
            if phantom_v not in graph.vertices:
                graph.add_vertex(phantom_v, {"coords": (to_x, to_y, to_z), "building_id": None})
            weight = conn.weight or 10.0
            if (from_end, phantom_v) not in graph.edges and (phantom_v, from_end) not in graph.edges:
                graph.add_edge(from_end, phantom_v, weight, {"type": "переход"})
                graph.add_edge(phantom_v, from_end, weight, {"type": "переход"})
            logger.debug(f"Переход: {from_end} ↔ {phantom_v}, вес={weight}")

    logger.info(f"Граф построен с {len(graph.vertices)} вершинами")
    return graph