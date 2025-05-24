# backend/app/map/utils/builder.py
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
        logger.warning(f"Segment length is zero for start ({start_x}, {start_y}) to end ({end_x}, {end_y})")
        return start_x, start_y
    dx = x - start_x
    dy = y - start_y
    t = max(0, min(1, (dx * seg_dx + dy * seg_dy) / seg_len_sq))
    closest_x = start_x + t * seg_dx
    closest_y = start_y + t * seg_dy
    logger.debug(f"Closest point: ({closest_x}, {closest_y})")
    return closest_x, closest_y

def find_midpoint(start_x: float, start_y: float, end_x: float, end_y: float) -> tuple:
    mid_x = (start_x + end_x) / 2
    mid_y = (start_y + end_y) / 2
    return mid_x, mid_y

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()

    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
        start_room = db.query(Room).filter(Room.id == start_id).first()
        end_room = db.query(Room).filter(Room.id == end_id).first()
        if not start_room or not end_room:
            raise ValueError(f"Room with id {start_id} or {end_id} not found")
    except ValueError as e:
        logger.error(f"Failed to parse room IDs from {start} or {end}: {e}")
        raise ValueError(f"Invalid room format, expected room_<id>, got {start} or {end}")

    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    start_floor_number = start_room.floor_id if not start_floor else start_floor.floor_number
    end_floor_number = end_room.floor_id if not end_floor else end_floor.floor_number
    logger.info(f"Assigned floor_number: room_{start_id}={start_floor_number}, room_{end_id}={end_floor_number}")

    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_floor_number), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_floor_number), "building_id": end_room.building_id})

    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Relevant building IDs: {building_ids}")
    logger.info(f"Relevant floor IDs: {floor_ids}")

    segments = {}
    floor_numbers = {}
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        seg_floor_number = segment.floor_id if not seg_floor else seg_floor.floor_number
        floor_numbers[segment.id] = seg_floor_number
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        mid_x, mid_y = find_midpoint(segment.start_x, segment.start_y, segment.end_x, segment.end_y)
        mid_vertex = f"segment_{segment.id}_mid"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(mid_vertex, {"coords": (mid_x, mid_y, seg_floor_number), "building_id": segment.building_id})
        segments[segment.id] = (start_vertex, end_vertex, mid_vertex)
        logger.info(f"Added segment vertices: {start_vertex}, {end_vertex}, {mid_vertex}")

    outdoor_segments = {}
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        coords_start = (outdoor.start_x, outdoor.start_y, 1)
        coords_end = (outdoor.end_x, outdoor.end_y, 1)
        graph.add_vertex(start_vertex, {"coords": coords_start, "building_id": None})
        graph.add_vertex(end_vertex, {"coords": coords_end, "building_id": None})
        outdoor_segments[outdoor.id] = (start_vertex, end_vertex)
        logger.info(f"Added outdoor vertices: {start_vertex}, {end_vertex}")

    # Фантомные точки для комнат
    for room_id, room in [(start_id, start_room), (end_id, end_room)]:
        room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        room_floor_number = room.floor_id if not room_floor else room_floor.floor_number
        room_vertex = f"room_{room_id}"
        connections = db.query(Connection).filter(Connection.room_id == room_id).all()
        for conn in connections:
            if conn.segment_id and conn.segment_id in segments:
                segment_start, segment_end, segment_mid = segments[conn.segment_id]
                closest_x, closest_y = find_closest_point_on_segment(
                    room.cab_x, room.cab_y,
                    graph.get_vertex_data(segment_start)["coords"][0],
                    graph.get_vertex_data(segment_start)["coords"][1],
                    graph.get_vertex_data(segment_end)["coords"][0],
                    graph.get_vertex_data(segment_end)["coords"][1]
                )
                phantom_vertex = f"phantom_room_{room_id}_segment_{conn.segment_id}"
                graph.add_vertex(phantom_vertex, {"coords": (closest_x, closest_y, room_floor_number), "building_id": room.building_id})
                weight_to_room = conn.weight or 2.0
                graph.add_edge(room_vertex, phantom_vertex, weight_to_room, {"type": "phantom"})
                graph.add_edge(phantom_vertex, room_vertex, weight_to_room, {"type": "phantom"})
                # Привязка к середине сегмента
                graph.add_edge(phantom_vertex, segment_mid, 0, {"type": "phantom"})
                graph.add_edge(segment_mid, phantom_vertex, 0, {"type": "phantom"})
                logger.info(f"Added phantom vertex for room: {phantom_vertex} -> ({closest_x}, {closest_y}, {room_floor_number})")

    # Соединения через таблицу connections
    for conn in db.query(Connection).all():
        # Пропускаем лестницы, если этажи одинаковые
        if start_floor_number == end_floor_number and conn.type == "лестница":
            continue

        # Соединения между сегментами
        if conn.from_segment_id and conn.to_segment_id and conn.from_segment_id in segments and conn.to_segment_id in segments:
            from_start, from_end, from_mid = segments[conn.from_segment_id]
            to_start, to_end, to_mid = segments[conn.to_segment_id]
            from_floor = floor_numbers[conn.from_segment_id]
            to_floor = floor_numbers[conn.to_segment_id]

            if start_floor_number == end_floor_number and from_floor != to_floor:
                continue

            # Фантомные точки для соединения сегментов
            from_coords = graph.get_vertex_data(from_mid)["coords"]
            to_coords = graph.get_vertex_data(to_mid)["coords"]
            phantom_from = f"phantom_segment_{conn.from_segment_id}_to_{conn.to_segment_id}"
            phantom_to = f"phantom_segment_{conn.to_segment_id}_from_{conn.from_segment_id}"
            graph.add_vertex(phantom_from, {"coords": from_coords, "building_id": None})
            graph.add_vertex(phantom_to, {"coords": to_coords, "building_id": None})
            weight = conn.weight or 10.0
            graph.add_edge(phantom_from, phantom_to, weight, {"type": conn.type})
            graph.add_edge(phantom_to, phantom_from, weight, {"type": conn.type})

            # Привязка фантомов к середине сегментов
            graph.add_edge(phantom_from, from_mid, 0, {"type": "phantom"})
            graph.add_edge(from_mid, phantom_from, 0, {"type": "phantom"})
            graph.add_edge(phantom_to, to_mid, 0, {"type": "phantom"})
            graph.add_edge(to_mid, phantom_to, 0, {"type": "phantom"})
            logger.info(f"Added connection: {phantom_from} -> {phantom_to}, weight={weight}")

            # Привязка фантомов комнат
            for room_id, room in [(start_id, start_room), (end_id, end_room)]:
                room_connections = db.query(Connection).filter(Connection.room_id == room_id, Connection.segment_id == conn.from_segment_id).all()
                for rc in room_connections:
                    phantom_room = f"phantom_room_{room_id}_segment_{rc.segment_id}"
                    if phantom_room in graph.vertices:
                        graph.add_edge(phantom_room, phantom_from, 0, {"type": "phantom"})
                        graph.add_edge(phantom_from, phantom_room, 0, {"type": "phantom"})
                room_connections = db.query(Connection).filter(Connection.room_id == room_id, Connection.segment_id == conn.to_segment_id).all()
                for rc in room_connections:
                    phantom_room = f"phantom_room_{room_id}_segment_{rc.segment_id}"
                    if phantom_room in graph.vertices:
                        graph.add_edge(phantom_room, phantom_to, 0, {"type": "phantom"})
                        graph.add_edge(phantom_to, phantom_room, 0, {"type": "phantom"})

        # Улица-дверь (выход из здания)
        elif conn.from_segment_id and conn.to_outdoor_id and conn.from_segment_id in segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end, from_mid = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_coords_mid = graph.get_vertex_data(from_mid)["coords"]
            to_coords_start = graph.get_vertex_data(to_start)["coords"]
            to_coords_end = graph.get_vertex_data(to_end)["coords"]

            # Фантомные точки для полного прохода
            phantom_from = f"phantom_segment_{conn.from_segment_id}_to_outdoor_{conn.to_outdoor_id}"
            phantom_to_start = f"phantom_outdoor_{conn.to_outdoor_id}_start"
            phantom_to_end = f"phantom_outdoor_{conn.to_outdoor_id}_end"

            graph.add_vertex(phantom_from, {"coords": from_coords_mid, "building_id": None})
            graph.add_vertex(phantom_to_start, {"coords": to_coords_start, "building_id": None})
            graph.add_vertex(phantom_to_end, {"coords": to_coords_end, "building_id": None})

            # Полный путь: сегмент → переход → уличный сегмент (start → end)
            weight_transition = conn.weight or 10.0
            weight_outdoor = math.sqrt((to_coords_end[0] - to_coords_start[0]) ** 2 + (to_coords_end[1] - to_coords_start[1]) ** 2)
            graph.add_edge(phantom_from, phantom_to_start, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to_start, phantom_to_end, weight_outdoor, {"type": "улица"})
            graph.add_edge(phantom_to_end, phantom_to_start, weight_outdoor, {"type": "улица"})

            # Привязка к середине сегмента и концам уличного сегмента
            graph.add_edge(phantom_from, from_mid, 0, {"type": "phantom"})
            graph.add_edge(from_mid, phantom_from, 0, {"type": "phantom"})
            graph.add_edge(to_start, phantom_to_start, 0, {"type": "phantom"})
            graph.add_edge(phantom_to_start, to_start, 0, {"type": "phantom"})
            graph.add_edge(to_end, phantom_to_end, 0, {"type": "phantom"})
            graph.add_edge(phantom_to_end, to_end, 0, {"type": "phantom"})
            logger.info(f"Added transition (дверь-улица): {phantom_from} -> {phantom_to_end}")

            # Привязка фантомов комнат
            for room_id, room in [(start_id, start_room), (end_id, end_room)]:
                room_connections = db.query(Connection).filter(Connection.room_id == room_id, Connection.segment_id == conn.from_segment_id).all()
                for rc in room_connections:
                    phantom_room = f"phantom_room_{room_id}_segment_{rc.segment_id}"
                    if phantom_room in graph.vertices:
                        graph.add_edge(phantom_room, phantom_from, 0, {"type": "phantom"})
                        graph.add_edge(phantom_from, phantom_room, 0, {"type": "phantom"})

        # Дверь-улица (вход в здание)
        elif conn.from_outdoor_id and conn.to_segment_id and conn.from_outdoor_id in outdoor_segments and conn.to_segment_id in segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end, to_mid = segments[conn.to_segment_id]
            from_coords_start = graph.get_vertex_data(from_start)["coords"]
            from_coords_end = graph.get_vertex_data(from_end)["coords"]
            to_coords_mid = graph.get_vertex_data(to_mid)["coords"]

            # Фантомные точки для полного прохода
            phantom_from_start = f"phantom_outdoor_{conn.from_outdoor_id}_start"
            phantom_from_end = f"phantom_outdoor_{conn.from_outdoor_id}_end"
            phantom_to = f"phantom_outdoor_{conn.from_outdoor_id}_to_segment_{conn.to_segment_id}"

            graph.add_vertex(phantom_from_start, {"coords": from_coords_start, "building_id": None})
            graph.add_vertex(phantom_from_end, {"coords": from_coords_end, "building_id": None})
            graph.add_vertex(phantom_to, {"coords": to_coords_mid, "building_id": None})

            # Полный путь: уличный сегмент (start → end) → переход → сегмент
            weight_outdoor = math.sqrt((from_coords_end[0] - from_coords_start[0]) ** 2 + (from_coords_end[1] - from_coords_start[1]) ** 2)
            weight_transition = conn.weight or 10.0
            graph.add_edge(phantom_from_start, phantom_from_end, weight_outdoor, {"type": "улица"})
            graph.add_edge(phantom_from_end, phantom_to, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to, phantom_from_end, weight_transition, {"type": "переход"})

            # Привязка к концам уличного сегмента и середине сегмента
            graph.add_edge(from_start, phantom_from_start, 0, {"type": "phantom"})
            graph.add_edge(phantom_from_start, from_start, 0, {"type": "phantom"})
            graph.add_edge(from_end, phantom_from_end, 0, {"type": "phantom"})
            graph.add_edge(phantom_from_end, from_end, 0, {"type": "phantom"})
            graph.add_edge(phantom_to, to_mid, 0, {"type": "phantom"})
            graph.add_edge(to_mid, phantom_to, 0, {"type": "phantom"})
            logger.info(f"Added transition (улица-дверь): {phantom_from_start} -> {phantom_to}")

            # Привязка фантомов комнат
            for room_id, room in [(start_id, start_room), (end_id, end_room)]:
                room_connections = db.query(Connection).filter(Connection.room_id == room_id, Connection.segment_id == conn.to_segment_id).all()
                for rc in room_connections:
                    phantom_room = f"phantom_room_{room_id}_segment_{rc.segment_id}"
                    if phantom_room in graph.vertices:
                        graph.add_edge(phantom_room, phantom_to, 0, {"type": "phantom"})
                        graph.add_edge(phantom_to, phantom_room, 0, {"type": "phantom"})

        # Outdoor-to-outdoor
        elif conn.from_outdoor_id and conn.to_outdoor_id and conn.from_outdoor_id in outdoor_segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_coords_start = graph.get_vertex_data(from_start)["coords"]
            from_coords_end = graph.get_vertex_data(from_end)["coords"]
            to_coords_start = graph.get_vertex_data(to_start)["coords"]
            to_coords_end = graph.get_vertex_data(to_end)["coords"]

            # Фантомные точки для полного прохода
            phantom_from_start = f"phantom_outdoor_{conn.from_outdoor_id}_start"
            phantom_from_end = f"phantom_outdoor_{conn.from_outdoor_id}_end"
            phantom_to_start = f"phantom_outdoor_{conn.to_outdoor_id}_start"
            phantom_to_end = f"phantom_outdoor_{conn.to_outdoor_id}_end"

            graph.add_vertex(phantom_from_start, {"coords": from_coords_start, "building_id": None})
            graph.add_vertex(phantom_from_end, {"coords": from_coords_end, "building_id": None})
            graph.add_vertex(phantom_to_start, {"coords": to_coords_start, "building_id": None})
            graph.add_vertex(phantom_to_end, {"coords": to_coords_end, "building_id": None})

            # Полный путь: уличный сегмент → переход → уличный сегмент
            weight_outdoor_from = math.sqrt((from_coords_end[0] - from_coords_start[0]) ** 2 + (from_coords_end[1] - from_coords_start[1]) ** 2)
            weight_outdoor_to = math.sqrt((to_coords_end[0] - to_coords_start[0]) ** 2 + (to_coords_end[1] - to_coords_start[1]) ** 2)
            weight_transition = conn.weight or 10.0
            graph.add_edge(phantom_from_start, phantom_from_end, weight_outdoor_from, {"type": "улица"})
            graph.add_edge(phantom_from_end, phantom_to_start, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to_start, phantom_to_end, weight_outdoor_to, {"type": "улица"})
            graph.add_edge(phantom_to_end, phantom_to_start, weight_outdoor_to, {"type": "улица"})

            # Привязка к концам
            graph.add_edge(from_start, phantom_from_start, 0, {"type": "phantom"})
            graph.add_edge(phantom_from_start, from_start, 0, {"type": "phantom"})
            graph.add_edge(from_end, phantom_from_end, 0, {"type": "phantom"})
            graph.add_edge(phantom_from_end, from_end, 0, {"type": "phantom"})
            graph.add_edge(to_start, phantom_to_start, 0, {"type": "phantom"})
            graph.add_edge(phantom_to_start, to_start, 0, {"type": "phantom"})
            graph.add_edge(to_end, phantom_to_end, 0, {"type": "phantom"})
            graph.add_edge(phantom_to_end, to_end, 0, {"type": "phantom"})
            logger.info(f"Added transition (улица-улица): {phantom_from_start} -> {phantom_to_end}")

        # Лестницы
        if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id and start_floor_number != end_floor_number:
            from_start, from_end, from_mid = segments[conn.from_segment_id]
            to_start, to_end, to_mid = segments[conn.to_segment_id]
            from_floor = floor_numbers[conn.from_segment_id]
            to_floor = floor_numbers[conn.to_segment_id]
            from_coords = graph.get_vertex_data(from_mid)["coords"]
            to_coords = graph.get_vertex_data(to_mid)["coords"]

            # Фантомные точки лестницы, привязанные к середине сегмента
            phantom_from = f"phantom_stair_{conn.from_segment_id}_to_{conn.to_segment_id}"
            phantom_to = f"phantom_stair_{conn.to_segment_id}_from_{conn.from_segment_id}"
            stair_from_x = from_coords[0]
            stair_from_y = from_coords[1] - 5  # Смещение перед лестницей
            stair_to_x = to_coords[0] + 20    # Смещение после лестницы
            stair_to_y = to_coords[1]
            graph.add_vertex(phantom_from, {"coords": (stair_from_x, stair_from_y, from_floor), "building_id": None})
            graph.add_vertex(phantom_to, {"coords": (stair_to_x, stair_to_y, to_floor), "building_id": None})

            # Вес лестницы
            weight_stair = conn.weight or 10.0
            graph.add_edge(phantom_from, phantom_to, weight_stair, {"type": "лестница"})
            graph.add_edge(phantom_to, phantom_from, weight_stair, {"type": "лестница"})

            # Привязка к середине сегментов
            graph.add_edge(phantom_from, from_mid, 0, {"type": "phantom"})
            graph.add_edge(from_mid, phantom_from, 0, {"type": "phantom"})
            graph.add_edge(phantom_to, to_mid, 0, {"type": "phantom"})
            graph.add_edge(to_mid, phantom_to, 0, {"type": "phantom"})
            logger.info(f"Added stair transition: {phantom_from} -> {phantom_to}, weight={weight_stair}, floors {from_floor} -> {to_floor}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph