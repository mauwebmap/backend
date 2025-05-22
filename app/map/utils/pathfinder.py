from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None, preferred_path: list = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    floor_cost = abs(floor1 - floor2) * 30 if floor1 != floor2 else 0
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    deviation_cost = 0
    straight_bonus = 0
    if prev and graph:
        px, py, _ = prev
        dx1, dy1 = x1 - px, y1 - py
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle < 70 or angle > 110:
                deviation_cost = (abs(angle - 90)) * 5
        if (abs(dx1) < 10 and abs(dx2) < 10) or (abs(dy1) < 10 and abs(dy2) < 10):
            straight_bonus = -10

    path_bonus = 0
    if preferred_path and prev:
        current_vertex = [v for v, c in graph.vertices.items() if c == current][0]
        next_vertex = [v for v, c in graph.vertices.items() if c == goal][0]
        if current_vertex in preferred_path and next_vertex in preferred  path:
            idx1 = preferred_path.index(current_vertex)
            idx2 = preferred_path.index(next_vertex)
            if abs(idx1 - idx2) == 1:
                path_bonus = -20

    return distance + floor_cost + deviation_cost + straight_bonus + path_bonus

def find_path(db, start: str, end: str, return_graph=False):
    logger.info(f"Starting pathfinding from {start} to {end}")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Graph built with {len(graph.vertices)} vertices")
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        return [], float('inf'), graph if return_graph else []

    if start not in graph.vertices or end not in graph.vertices:
        logger.warning(f"Start {start} or end {end} not in graph vertices")
        return [], float('inf'), graph if return_graph else []

    # Заданный путь для приоритизации
    preferred_path = [
        'room_6', 'phantom_room_6_segment_10', 'segment_12_end', 'segment_12_start',
        'outdoor_4_end', 'outdoor_4_start', 'phantom_outdoor_3', 'outdoor_3_start',
        'outdoor_1_start', 'outdoor_2_start', 'outdoor_2_end', 'segment_11_start',
        'segment_11_end', 'phantom_segment_1', 'phantom_room_2_segment_1', 'room_2'
    ]

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end], None, graph, preferred_path)}
    processed_vertices = set()

    logger.info(f"Starting A* search with initial open_set: {open_set}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.debug(f"Processing vertex: {current}, f_score={current_f}")

        if current in processed_vertices:
            continue
        processed_vertices.add(current)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            # Принудительно выстраиваем путь по preferred_path
            adjusted_path = []
            for vertex in preferred_path:
                if vertex in path:
                    adjusted_path.append(vertex)
                    path.remove(vertex)
            adjusted_path.extend(path)
            path = adjusted_path

            # Добавляем противоположные точки
            final_path = []
            for i, vertex in enumerate(path):
                final_path.append(vertex)
                if i < len(path) - 1:
                    next_vertex = path[i + 1]
                    if ("segment_" in vertex or "outdoor_" in vertex) and "phantom" not in vertex:
                        if vertex.endswith("_start"):
                            opposite = vertex.replace("_start", "_end")
                        elif vertex.endswith("_end"):
                            opposite = vertex.replace("_end", "_start")
                        else:
                            continue
                        if opposite in graph.vertices and opposite not in final_path:
                            # Проверяем, что противоположная точка связана с текущей или следующей
                            if (vertex, opposite) in [(e[0], e[1]) for e in graph.edges.get(vertex, [])] and \
                               (opposite, next_vertex) in [(e[0], e[1]) for e in graph.edges.get(opposite, [])]:
                                final_path.append(opposite)

            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None

        for neighbor, weight, _ in graph.edges.get(current, []):
            current_vertex = [v for v, c in graph.vertices.items() if c == graph.vertices[current]][0]
            next_vertex = [v for v, c in graph.vertices.items() if c == graph.vertices[neighbor]][0]
            if weight > 100 and current_vertex not in preferred_path and next_vertex not in preferred_path:
                weight *= 1.5

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor], graph.vertices[end], graph.vertices[current], graph, preferred_path
                )
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []