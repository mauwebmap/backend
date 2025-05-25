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
        logger.info(f"Длина сегмента нулевая для start ({start_x}, {start_y}) to end ({end_x}, {end_y})")
        return start_x, start_y
    dx = x - start_x
    dy = y - start_y
    t = max(0, min(1, (dx * seg_dx + dy * seg_dy) / seg_len_sq))
    closest_x = start_x + t * seg_dx
    closest_y = start_y + t * seg_dy
    logger.info(f"Ближайшая точка: ({closest_x}, {closest_y})")
    return closest_x, closest_y

def align_coordinates(from_coords: tuple, to_coords: tuple, from_seg_start: tuple, from_seg_end: tuple, to_seg_start: tuple, to_seg_end: tuple) -> tuple:
    from_x, from_y, from_z = from_coords
    to_x, to_y, to_z = to_coords
    from_seg_dx = from_seg_end[0] - from_seg_start[0]
    from_seg_dy = from_seg_end[1] - from_seg_start[1]
    to_seg_dx = to_seg_end[0] - to_seg_start[0]
    to_seg_dy = to_seg_end[1] - to_seg_start[1]

    if abs(from_seg_dy) < 1e-6 and abs(to_seg_dy) < 1e-6:
        aligned_y = (from_y + to_y) / 2 if abs(from_y - to_y) > 10 else from_y
        return (from_x, aligned_y, from_z), (to_x, aligned_y, to_z)
    elif abs(from_seg_dx) < 1e-6 and abs(to_seg_dx) < 1e-6:
        aligned_x = (from_x + to_x) / 2 if abs(from_x - to_x) > 10 else from_x
        return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)
    else:
        dist_x = abs(from_x - to_x)
        dist_y = abs(from_y - to_y)
        if dist_x < dist_y:
            aligned_x = (from_x + to_x) / 2
            return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)
        else:
            aligned_y = (from_y + to_y) / 2
            return (from_x, aligned_y, from_z), (to_x, aligned_y, to_z)

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Начало построения графа для start={start}, end={end}")
    graph = Graph()

    try:
        start_id = int(start.replace("room_", ""))
        end_id = int(end.replace("room_", ""))
        start_room = db.query(Room).filter(Room.id == start_id).first()
        end_room = db.query(Room).filter(Room.id == end_id).first()
        if not start_room or not end_room:
            logger.info(f"Комната с id {start_id} или {end_id} не найдена")
            raise ValueError(f"Комната с id {start_id} или {end_id} не найдена")
    except ValueError as e:
        logger.info(f"Ошибка при парсинге ID комнат из {start} или {end}: {e}")
        raise ValueError(f"Неверный формат комнаты, ожидается room_<id>, получено {start} или {end}")

    start_floor = db.query(Floor).filter(Floor.id == start_room.floor_id).first()
    end_floor = db.query(Floor).filter(Floor.id == end_room.floor_id).first()
    start_floor_number = start_floor.floor_number if start_floor else start_room.floor_id
    end_floor_number = end_floor.floor_number if end_floor else end_room.floor_id
    logger.info(f"Назначен номер этажа: room_{start_id}={start_floor_number}, room_{end_id}={end_floor_number}")

    graph.add_vertex(start, {"coords": (start_room.cab_x, start_room.cab_y, start_floor_number), "building_id": start_room.building_id})
    graph.add_vertex(end, {"coords": (end_room.cab_x, end_room.cab_y, end_floor_number), "building_id": end_room.building_id})

    building_ids = {start_room.building_id, end_room.building_id} - {None}
    floor_ids = {start_room.floor_id, end_room.floor_id}
    logger.info(f"Актуальные ID зданий: {building_ids}")
    logger.info(f"Актуальные ID этажей: {floor_ids}")

    segments = {}
    floor_numbers = {}
    segment_phantom_points = {}
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        seg_floor_number = seg_floor.floor_number if seg_floor else segment.floor_id
        floor_numbers[segment.id] = seg_floor_number
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, seg_floor_number), "building_id": segment.building_id})
        segments[segment.id] = (start_vertex, end_vertex)
        segment_phantom_points[segment.id] = []
        weight = math.sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})
        graph.add_edge(end_vertex, start_vertex, weight, {"type": "segment"})  # Делаем сегмент двунаправленным
        logger.info(f"Добавлены вершины сегмента: {start_vertex} ↔ {end_vertex}, вес={weight}")

    outdoor_segments = {}
    outdoor_phantom_points = {}
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        coords_start = (outdoor.start_x, outdoor.start_y, 1)
        coords_end = (outdoor.end_x, outdoor.end_y, 1)
        graph.add_vertex(start_vertex, {"coords": coords_start, "building_id": None})
        graph.add_vertex(end_vertex, {"coords": coords_end, "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
        graph.add_edge(end_vertex, start_vertex, weight, {"type": "outdoor"})  # Делаем уличный сегмент двунаправленным
        outdoor_segments[outdoor.id] = (start_vertex, end_vertex)
        outdoor_phantom_points[outdoor.id] = []
        logger.info(f"Добавлены уличные вершины: {start_vertex} ↔ {end_vertex}, вес={weight}")

    for room_id, room in [(start_id, start_room), (end_id, end_room)]:
        room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        room_floor_number = room_floor.floor_number if room_floor else room.floor_id
        room_vertex = f"room_{room_id}"
        connections = db.query(Connection).filter(Connection.room_id == room_id).all()
        for conn in connections:
            if conn.segment_id and conn.segment_id in segments:
                segment_start, segment_end = segments[conn.segment_id]
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
                segment_phantom_points[conn.segment_id].append(phantom_vertex)
                logger.info(f"Добавлена фантомная вершина для комнаты: {phantom_vertex} ↔ ({closest_x}, {closest_y}, {room_floor_number})")

    for conn in db.query(Connection).all():
        if conn.from_segment_id and conn.to_segment_id and conn.from_segment_id in segments and conn.to_segment_id in segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_floor = floor_numbers[conn.from_segment_id]
            to_floor = floor_numbers[conn.to_segment_id]

            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            stair_x = (from_end_coords[0] + to_start_coords[0]) / 2
            stair_y = (from_end_coords[1] + to_start_coords[1]) / 2

            from_closest_x, from_closest_y = find_closest_point_on_segment(
                stair_x, stair_y,
                from_start_coords[0], from_start_coords[1],
                from_end_coords[0], from_end_coords[1]
            )
            to_closest_x, to_closest_y = find_closest_point_on_segment(
                stair_x, stair_y,
                to_start_coords[0], to_start_coords[1],
                to_end_coords[0], to_end_coords[1]
            )

            (from_closest_x, from_closest_y, from_floor), (to_closest_x, to_closest_y, to_floor) = align_coordinates(
                (from_closest_x, from_closest_y, from_floor),
                (to_closest_x, to_closest_y, to_floor),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_from = f"phantom_stair_{conn.from_segment_id}_to_{conn.to_segment_id}"
            phantom_to = f"phantom_stair_{conn.to_segment_id}_from_{conn.from_segment_id}"
            graph.add_vertex(phantom_from, {"coords": (from_closest_x, from_closest_y, from_floor), "building_id": None})
            graph.add_vertex(phantom_to, {"coords": (to_closest_x, to_closest_y, to_floor), "building_id": None})

            weight = max(conn.weight or 10.0, 0.1)  # Устанавливаем минимальный вес 0.1, чтобы избежать 0.0
            graph.add_edge(phantom_from, phantom_to, weight, {"type": "лестница"})
            graph.add_edge(phantom_to, phantom_from, weight, {"type": "лестница"})
            segment_phantom_points[conn.from_segment_id].append(phantom_from)
            segment_phantom_points[conn.to_segment_id].append(phantom_to)

            for other_phantom in segment_phantom_points[conn.from_segment_id]:
                if other_phantom != phantom_from:
                    coords1 = graph.get_vertex_data(phantom_from)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    if "stair" in other_phantom and str(conn.to_segment_id) not in other_phantom:
                        weight *= 5
                    graph.add_edge(phantom_from, other_phantom, weight, {"type": "segment"})
                    graph.add_edge(other_phantom, phantom_from, weight, {"type": "segment"})
            for other_phantom in segment_phantom_points[conn.to_segment_id]:
                if other_phantom != phantom_to:
                    coords1 = graph.get_vertex_data(phantom_to)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    if "stair" in other_phantom and str(conn.from_segment_id) not in other_phantom:
                        weight *= 5
                    graph.add_edge(phantom_to, other_phantom, weight, {"type": "segment"})
                    graph.add_edge(other_phantom, phantom_to, weight, {"type": "segment"})
            logger.info(f"Добавлено лестничное соединение: {phantom_from} ↔ {phantom_to}, вес={weight}")

        elif conn.from_segment_id and conn.to_outdoor_id and conn.from_segment_id in segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            door_x = (to_start_coords[0] + to_end_coords[0]) / 2
            door_y = (to_start_coords[1] + to_end_coords[1]) / 2
            from_closest_x, from_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                from_start_coords[0], from_start_coords[1],
                from_end_coords[0], from_end_coords[1]
            )

            (from_closest_x, from_closest_y, from_floor), (to_start_x, to_start_y, to_floor) = align_coordinates(
                (from_closest_x, from_closest_y, from_start_coords[2]),
                (to_start_coords[0], to_start_coords[1], 1),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_from = f"phantom_segment_{conn.from_segment_id}_to_outdoor_{conn.to_outdoor_id}"
            graph.add_vertex(phantom_from, {"coords": (from_closest_x, from_closest_y, from_start_coords[2]), "building_id": None})
            weight_transition = conn.weight or 10.0
            graph.add_edge(phantom_from, to_start, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_from, to_end, weight_transition, {"type": "переход"})
            graph.add_edge(to_start, phantom_from, weight_transition, {"type": "переход"})
            graph.add_edge(to_end, phantom_from, weight_transition, {"type": "переход"})
            segment_phantom_points[conn.from_segment_id].append(phantom_from)
            for other_phantom in segment_phantom_points[conn.from_segment_id]:
                if other_phantom != phantom_from:
                    coords1 = graph.get_vertex_data(phantom_from)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    graph.add_edge(phantom_from, other_phantom, weight, {"type": "segment"})
                    graph.add_edge(other_phantom, phantom_from, weight, {"type": "segment"})
            logger.info(f"Добавлен переход дверь-улица: {phantom_from} ↔ {to_start}/{to_end}, вес={weight_transition}")

        elif conn.from_outdoor_id and conn.to_segment_id and conn.from_outdoor_id in outdoor_segments and conn.to_segment_id in segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            door_x = (from_start_coords[0] + from_end_coords[0]) / 2
            door_y = (from_start_coords[1] + from_end_coords[1]) / 2
            to_closest_x, to_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                to_start_coords[0], to_start_coords[1],
                to_end_coords[0], to_end_coords[1]
            )

            (from_end_x, from_end_y, from_floor), (to_closest_x, to_closest_y, to_floor) = align_coordinates(
                (from_end_coords[0], from_end_coords[1], 1),
                (to_closest_x, to_closest_y, to_start_coords[2]),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_to = f"phantom_segment_{conn.to_segment_id}_from_outdoor_{conn.from_outdoor_id}"
            graph.add_vertex(phantom_to, {"coords": (to_closest_x, to_closest_y, to_start_coords[2]), "building_id": None})
            weight_transition = conn.weight or 10.0
            graph.add_edge(from_start, phantom_to, weight_transition, {"type": "переход"})
            graph.add_edge(from_end, phantom_to, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to, from_start, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to, from_end, weight_transition, {"type": "переход"})
            segment_phantom_points[conn.to_segment_id].append(phantom_to)
            for other_phantom in segment_phantom_points[conn.to_segment_id]:
                if other_phantom != phantom_to:
                    coords1 = graph.get_vertex_data(phantom_to)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    graph.add_edge(phantom_to, other_phantom, weight, {"type": "segment"})
                    graph.add_edge(other_phantom, phantom_to, weight, {"type": "segment"})
            logger.info(f"Добавлен переход улица-дверь: {from_start}/{from_end} ↔ {phantom_to}, вес={weight_transition}")

        elif conn.from_outdoor_id and conn.to_outdoor_id and conn.from_outdoor_id in outdoor_segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            weight = conn.weight or 10.0
            graph.add_edge(from_start, to_start, weight, {"type": "outdoor"})
            graph.add_edge(from_start, to_end, weight, {"type": "outdoor"})
            graph.add_edge(from_end, to_start, weight, {"type": "outdoor"})
            graph.add_edge(from_end, to_end, weight, {"type": "outdoor"})
            graph.add_edge(to_start, from_start, weight, {"type": "outdoor"})
            graph.add_edge(to_start, from_end, weight, {"type": "outdoor"})
            graph.add_edge(to_end, from_start, weight, {"type": "outdoor"})
            graph.add_edge(to_end, from_end, weight, {"type": "outdoor"})
            logger.info(f"Добавлено соединение улица-улица: {conn.from_outdoor_id} ↔ {conn.to_outdoor_id}, вес={weight}")

    logger.info(f"Граф успешно построен с {len(graph.vertices)} вершинами")
    return graph