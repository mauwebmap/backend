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

def align_coordinates(from_coords: tuple, to_coords: tuple, from_seg_start: tuple, from_seg_end: tuple, to_seg_start: tuple, to_seg_end: tuple) -> tuple:
    """Выравниваем координаты для лестниц и переходов, чтобы путь был прямым."""
    from_x, from_y, from_z = from_coords
    to_x, to_y, to_z = to_coords
    from_seg_dx = from_seg_end[0] - from_seg_start[0]
    from_seg_dy = from_seg_end[1] - from_seg_start[1]
    to_seg_dx = to_seg_end[0] - to_seg_start[0]
    to_seg_dy = to_seg_end[1] - to_seg_start[1]

    # Выравниваем по оси, где изменение минимально
    if abs(from_seg_dy) < 1e-6 and abs(to_seg_dy) < 1e-6:  # Горизонтальные сегменты
        aligned_y = 1295.0  # Фиксируем Y для этажа 1
        return (from_x, aligned_y, from_z), (to_x, aligned_y, to_z)
    elif abs(from_seg_dx) < 1e-6 and abs(to_seg_dx) < 1e-6:  # Вертикальные сегменты
        aligned_x = (from_seg_start[0] + from_seg_end[0]) / 2
        return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)
    else:
        dist_x = abs(from_x - to_x)
        dist_y = abs(from_y - to_y)
        if dist_x < dist_y:
            aligned_x = (from_seg_start[0] + from_seg_end[0]) / 2
            return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)
        else:
            aligned_y = 1295.0 if from_z == 1 else (from_seg_start[1] + from_seg_end[1]) / 2
            return (from_x, aligned_y, from_z), (to_x, aligned_y, to_z)

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()

    # Парсинг начальной и конечной комнат
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

    # Сегменты
    segments = {}
    floor_numbers = {}
    segment_phantom_points = {}
    for segment in db.query(Segment).filter(Segment.building_id.in_(building_ids)).all():
        seg_floor = db.query(Floor).filter(Floor.id == segment.floor_id).first()
        seg_floor_number = segment.floor_id if not seg_floor else seg_floor.floor_number
        floor_numbers[segment.id] = seg_floor_number
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        graph.add_vertex(start_vertex, {"coords": (segment.start_x, segment.start_y, seg_floor_number), "building_id": segment.building_id})
        graph.add_vertex(end_vertex, {"coords": (segment.end_x, segment.end_y, seg_floor_number), "building_id": segment.building_id})
        segments[segment.id] = (start_vertex, end_vertex)
        segment_phantom_points[segment.id] = []
        logger.info(f"Added segment vertices: {start_vertex}, {end_vertex}")

    # Уличные сегменты
    outdoor_segments = {}
    for outdoor in db.query(OutdoorSegment).all():
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        coords_start = (outdoor.start_x, outdoor.start_y, 1)
        coords_end = (outdoor.end_x, outdoor.end_y, 1)
        graph.add_vertex(start_vertex, {"coords": coords_start, "building_id": None})
        graph.add_vertex(end_vertex, {"coords": coords_end, "building_id": None})
        weight = math.sqrt((outdoor.end_x - outdoor.start_x) ** 2 + (outdoor.end_y - outdoor.start_y) ** 2)
        graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
        outdoor_segments[outdoor.id] = (start_vertex, end_vertex)
        logger.info(f"Added outdoor vertices: {start_vertex} -> {end_vertex}, weight={weight}")

    # Фантомные точки для комнат
    for room_id, room in [(start_id, start_room), (end_id, end_room)]:
        room_floor = db.query(Floor).filter(Floor.id == room.floor_id).first()
        room_floor_number = room.floor_id if not room_floor else room_floor.floor_number
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
                segment_phantom_points[conn.segment_id].append(phantom_vertex)
                logger.info(f"Added phantom vertex for room: {phantom_vertex} -> ({closest_x}, {closest_y}, {room_floor_number})")

    # Соединения через таблицу connections
    for conn in db.query(Connection).all():
        if start_floor_number == end_floor_number and conn.type == "лестница":
            continue

        # Лестницы
        if conn.from_segment_id and conn.to_segment_id and conn.from_segment_id in segments and conn.to_segment_id in segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_floor = floor_numbers[conn.from_segment_id]
            to_floor = floor_numbers[conn.to_segment_id]

            if start_floor_number == end_floor_number and from_floor != to_floor:
                continue

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

            # Выравниваем координаты, чтобы лестницы были "напротив"
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

            # Устанавливаем вес для лестниц, чтобы избежать лишних переходов
            weight = max(conn.weight or 0, 50.0)  # Минимальный вес 50 для лестниц
            graph.add_edge(phantom_from, phantom_to, weight, {"type": "лестница"})
            segment_phantom_points[conn.from_segment_id].append(phantom_from)
            segment_phantom_points[conn.to_segment_id].append(phantom_to)

            # Соединяем фантомные точки на одном сегменте
            for other_phantom in segment_phantom_points[conn.from_segment_id]:
                if other_phantom != phantom_from:
                    coords1 = graph.get_vertex_data(phantom_from)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    # Увеличиваем вес для ненужных лестниц
                    if "stair" in other_phantom and str(conn.to_segment_id) not in other_phantom:
                        weight *= 5  # Штрафуем ненужные лестницы
                    graph.add_edge(phantom_from, other_phantom, weight, {"type": "segment"})
            for other_phantom in segment_phantom_points[conn.to_segment_id]:
                if other_phantom != phantom_to:
                    coords1 = graph.get_vertex_data(phantom_to)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    if "stair" in other_phantom and str(conn.from_segment_id) not in other_phantom:
                        weight *= 5
                    graph.add_edge(phantom_to, other_phantom, weight, {"type": "segment"})

            logger.info(f"Added stair connection: {phantom_from} -> {phantom_to}, weight={weight}")

        # Дверь-улица
        elif conn.from_segment_id and conn.to_outdoor_id and conn.from_segment_id in segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = segments[conn.from_segment_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            door_x = to_start_coords[0]
            door_y = to_start_coords[1]
            from_closest_x, from_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                from_start_coords[0], from_start_coords[1],
                from_end_coords[0], from_end_coords[1]
            )

            # Выравниваем координаты для перехода
            (from_closest_x, from_closest_y, from_floor), (to_start_x, to_start_y, to_floor) = align_coordinates(
                (from_closest_x, from_closest_y, from_start_coords[2]),
                (to_start_coords[0], to_start_coords[1], 1),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_from = f"phantom_segment_{conn.from_segment_id}_to_outdoor_{conn.to_outdoor_id}"
            phantom_to_start = f"phantom_outdoor_{conn.to_outdoor_id}_start"
            phantom_to_end = f"phantom_outdoor_{conn.to_outdoor_id}_end"

            graph.add_vertex(phantom_from, {"coords": (from_closest_x, from_closest_y, from_start_coords[2]), "building_id": None})
            graph.add_vertex(phantom_to_start, {"coords": (to_start_x, to_start_y, 1), "building_id": None})
            graph.add_vertex(phantom_to_end, {"coords": to_end_coords, "building_id": None})

            weight_transition = max(conn.weight or 0, 10.0)
            weight_outdoor = math.sqrt((to_end_coords[0] - to_start_x) ** 2 + (to_end_coords[1] - to_start_y) ** 2)
            graph.add_edge(phantom_from, phantom_to_start, weight_transition, {"type": "переход"})
            graph.add_edge(phantom_to_start, phantom_to_end, weight_outdoor, {"type": "outdoor"})
            segment_phantom_points[conn.from_segment_id].append(phantom_from)
            for other_phantom in segment_phantom_points[conn.from_segment_id]:
                if other_phantom != phantom_from:
                    coords1 = graph.get_vertex_data(phantom_from)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    graph.add_edge(phantom_from, other_phantom, weight, {"type": "segment"})
            logger.info(f"Added transition (дверь-улица): {phantom_from} -> {phantom_to_end}")

        # Улица-дверь
        elif conn.from_outdoor_id and conn.to_segment_id and conn.from_outdoor_id in outdoor_segments and conn.to_segment_id in segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = segments[conn.to_segment_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            door_x = from_end_coords[0]
            door_y = from_end_coords[1]
            to_closest_x, to_closest_y = find_closest_point_on_segment(
                door_x, door_y,
                to_start_coords[0], to_start_coords[1],
                to_end_coords[0], to_end_coords[1]
            )

            # Выравниваем координаты
            (from_end_x, from_end_y, from_floor), (to_closest_x, to_closest_y, to_floor) = align_coordinates(
                (from_end_coords[0], from_end_coords[1], 1),
                (to_closest_x, to_closest_y, to_start_coords[2]),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_from_start = f"phantom_outdoor_{conn.from_outdoor_id}_start"
            phantom_from_end = f"phantom_outdoor_{conn.from_outdoor_id}_end"
            phantom_to = f"phantom_outdoor_{conn.from_outdoor_id}_to_segment_{conn.to_segment_id}"

            graph.add_vertex(phantom_from_start, {"coords": from_start_coords, "building_id": None})
            graph.add_vertex(phantom_from_end, {"coords": (from_end_x, from_end_y, 1), "building_id": None})
            graph.add_vertex(phantom_to, {"coords": (to_closest_x, to_closest_y, to_start_coords[2]), "building_id": None})

            weight_outdoor = math.sqrt((from_end_x - from_start_coords[0]) ** 2 + (from_end_y - from_start_coords[1]) ** 2)
            weight_transition = max(conn.weight or 0, 10.0)
            graph.add_edge(phantom_from_start, phantom_from_end, weight_outdoor, {"type": "outdoor"})
            graph.add_edge(phantom_from_end, phantom_to, weight_transition, {"type": "переход"})
            segment_phantom_points[conn.to_segment_id].append(phantom_to)
            for other_phantom in segment_phantom_points[conn.to_segment_id]:
                if other_phantom != phantom_to:
                    coords1 = graph.get_vertex_data(phantom_to)["coords"]
                    coords2 = graph.get_vertex_data(other_phantom)["coords"]
                    weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                    graph.add_edge(phantom_to, other_phantom, weight, {"type": "segment"})
            logger.info(f"Added transition (улица-дверь): {phantom_from_start} -> {phantom_to}")

        # Улица-улица
        elif conn.from_outdoor_id and conn.to_outdoor_id and conn.from_outdoor_id in outdoor_segments and conn.to_outdoor_id in outdoor_segments:
            from_start, from_end = outdoor_segments[conn.from_outdoor_id]
            to_start, to_end = outdoor_segments[conn.to_outdoor_id]
            from_start_coords = graph.get_vertex_data(from_start)["coords"]
            from_end_coords = graph.get_vertex_data(from_end)["coords"]
            to_start_coords = graph.get_vertex_data(to_start)["coords"]
            to_end_coords = graph.get_vertex_data(to_end)["coords"]

            # Выравниваем координаты
            (from_end_x, from_end_y, from_floor), (to_start_x, to_start_y, to_floor) = align_coordinates(
                (from_end_coords[0], from_end_coords[1], 1),
                (to_start_coords[0], to_start_coords[1], 1),
                (from_start_coords[0], from_start_coords[1]),
                (from_end_coords[0], from_end_coords[1]),
                (to_start_coords[0], to_start_coords[1]),
                (to_end_coords[0], to_end_coords[1])
            )

            phantom_from_start = f"phantom_outdoor_{conn.from_outdoor_id}_start"
            phantom_from_end = f"phantom_outdoor_{conn.from_outdoor_id}_end"
            phantom_to_start = f"phantom_outdoor_{conn.to_outdoor_id}_start"
            phantom_to_end = f"phantom_outdoor_{conn.to_outdoor_id}_end"

            graph.add_vertex(phantom_from_start, {"coords": from_start_coords, "building_id": None})
            graph.add_vertex(phantom_from_end, {"coords": (from_end_x, from_end_y, 1), "building_id": None})
            graph.add_vertex(phantom_to_start, {"coords": (to_start_x, to_start_y, 1), "building_id": None})
            graph.add_vertex(phantom_to_end, {"coords": to_end_coords, "building_id": None})

            weight_outdoor_from = math.sqrt((from_end_x - from_start_coords[0]) ** 2 + (from_end_y - from_start_coords[1]) ** 2)
            weight_outdoor_to = math.sqrt((to_end_coords[0] - to_start_x) ** 2 + (to_end_coords[1] - to_start_y) ** 2)
            weight_transition = max(conn.weight or 0, 10.0)
            graph.add_edge(phantom_from_start, phantom_from_end, weight_outdoor_from, {"type": "outdoor"})
            graph.add_edge(phantom_from_end, phantom_to_start, weight_transition, {"type": "outdoor"})
            graph.add_edge(phantom_to_start, phantom_to_end, weight_outdoor_to, {"type": "outdoor"})
            logger.info(f"Added transition (улица-улица): {phantom_from_start} -> {phantom_to_end}")

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph