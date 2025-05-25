import math
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

class Graph:
    def __init__(self):
        self.vertices = {}
        self.edges = {}

    def add_vertex(self, vertex: str, data: dict):
        self.vertices[vertex] = data
        if vertex not in self.edges:
            self.edges[vertex] = []

    def add_edge(self, from_vertex: str, to_vertex: str, weight: float, data: dict):
        self.edges[from_vertex].append((to_vertex, weight, data))
        self.edges[to_vertex].append((from_vertex, weight, data))

    def get_vertex_data(self, vertex: str) -> dict:
        return self.vertices.get(vertex, {})

    def get_neighbors(self, vertex: str) -> List[Tuple[str, float, dict]]:
        return self.edges.get(vertex, [])

def find_closest_point_on_segment(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> Tuple[float, float]:
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return x1, y1
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    closest_x = x1 + t * dx
    closest_y = y1 + t * dy
    return closest_x, closest_y

def align_coordinates(from_coords: tuple, to_coords: tuple, from_seg_start: tuple, from_seg_end: tuple, to_seg_start: tuple, to_seg_end: tuple) -> tuple:
    from_x, from_y, from_z = from_coords
    to_x, to_y, to_z = to_coords
    dist_x = abs(from_x - to_x)
    dist_y = abs(from_y - to_y)
    if dist_x < dist_y:
        aligned_x = from_seg_end[0]
        return (aligned_x, from_y, from_z), (aligned_x, to_y, to_z)
    else:
        aligned_y = from_seg_end[1]
        return (from_x, aligned_y, from_z), (to_x, aligned_y, to_z)

def build_graph(rooms: dict, segments: dict, outdoor_segments: dict, connections: dict) -> Graph:
    logger.info("Starting graph construction")
    graph = Graph()
    segment_phantom_points: Dict[int, List[str]] = {seg_id: [] for seg_id in segments}

    try:
        if not rooms or not segments or not connections:
            logger.info("Empty input data: rooms, segments, or connections")
            raise ValueError("Input data cannot be empty")

        # Добавляем комнаты
        for room_id, (x, y, floor, building_id) in rooms.items():
            vertex = f"room_{room_id}"
            graph.add_vertex(vertex, {"coords": (x, y, floor), "building_id": building_id})
            logger.debug(f"Added room vertex: {vertex} at {(x, y, floor)}")

        # Добавляем сегменты
        for seg_id, (start_vertex, end_vertex) in segments.items():
            start_data = graph.get_vertex_data(start_vertex)
            end_data = graph.get_vertex_data(end_vertex)
            if not start_data or not end_data:
                logger.warning(f"Segment {seg_id} has missing vertices: {start_vertex}, {end_vertex}")
                continue

            start_coords = start_data["coords"]
            end_coords = end_data["coords"]
            weight = math.sqrt((end_coords[0] - start_coords[0]) ** 2 + (end_coords[1] - start_coords[1]) ** 2)

            if "stair" in start_vertex or "stair" in end_vertex:
                phantom_start = f"phantom_{start_vertex}"
                phantom_end = f"phantom_{end_vertex}"
                graph.add_vertex(phantom_start, {"coords": start_coords, "building_id": start_data["building_id"]})
                graph.add_vertex(phantom_end, {"coords": end_coords, "building_id": end_data["building_id"]})
                graph.add_edge(phantom_start, phantom_end, weight, {"type": "лестница"})  # Используем "лестница"
                segment_phantom_points[seg_id].extend([phantom_start, phantom_end])
                logger.debug(f"Added stair segment: {phantom_start} -> {phantom_end}, weight={weight}")
            else:
                graph.add_edge(start_vertex, end_vertex, weight, {"type": "segment"})
                logger.debug(f"Added segment: {start_vertex} -> {end_vertex}, weight={weight}")

        # Уличные сегменты
        for outdoor_id, (start_vertex, end_vertex) in outdoor_segments.items():
            start_coords = graph.get_vertex_data(start_vertex)["coords"]
            end_coords = graph.get_vertex_data(end_vertex)["coords"]
            weight = math.sqrt((end_coords[0] - start_coords[0]) ** 2 + (end_coords[1] - start_coords[1]) ** 2)
            graph.add_edge(start_vertex, end_vertex, weight, {"type": "outdoor"})
            logger.debug(f"Added outdoor segment: {start_vertex} -> {end_vertex}, weight={weight}")

        # Связи из таблицы connections
        for conn_id, conn in connections.items():
            if conn.from_room_id and conn.to_segment_id:
                room_vertex = f"room_{conn.from_room_id}"
                seg_start, seg_end = segments[conn.to_segment_id]
                room_coords = graph.get_vertex_data(room_vertex)["coords"]
                seg_start_coords = graph.get_vertex_data(seg_start)["coords"]
                seg_end_coords = graph.get_vertex_data(seg_end)["coords"]

                closest_x, closest_y = find_closest_point_on_segment(
                    room_coords[0], room_coords[1],
                    seg_start_coords[0], seg_start_coords[1],
                    seg_end_coords[0], seg_end_coords[1]
                )

                phantom_vertex = f"phantom_room_{conn.from_room_id}_segment_{conn.to_segment_id}"
                graph.add_vertex(phantom_vertex, {"coords": (closest_x, closest_y, room_coords[2]), "building_id": None})
                weight = math.sqrt((room_coords[0] - closest_x) ** 2 + (room_coords[1] - closest_y) ** 2)
                graph.add_edge(room_vertex, phantom_vertex, weight, {"type": "phantom"})
                segment_phantom_points[conn.to_segment_id].append(phantom_vertex)

                for other_phantom in segment_phantom_points[conn.to_segment_id]:
                    if other_phantom != phantom_vertex:
                        coords1 = graph.get_vertex_data(phantom_vertex)["coords"]
                        coords2 = graph.get_vertex_data(other_phantom)["coords"]
                        weight = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
                        graph.add_edge(phantom_vertex, other_phantom, weight, {"type": "segment"})
                logger.debug(f"Added room-segment connection: {room_vertex} -> {phantom_vertex}")

            elif conn.from_outdoor_id and conn.to_segment_id:
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
                phantom_to = f"phantom_segment_{conn.to_segment_id}_to_outdoor_{conn.from_outdoor_id}"

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
                logger.debug(f"Added outdoor-segment connection: {phantom_from_start} -> {phantom_to}")

        logger.info("Graph construction completed successfully")
        return graph

    except Exception as e:
        logger.info(f"Error building graph: {str(e)}")
        raise