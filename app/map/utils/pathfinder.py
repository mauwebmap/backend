from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(a: tuple, b: tuple) -> float:
    x1, y1, floor1 = a
    x2, y2, floor2 = b
    floor_cost = abs(floor1 - floor2) * 100
    # Штраф за резкие повороты (угол между векторами)
    dx1, dy1 = x2 - x1, y2 - y1
    angle_cost = 0
    if dx1 != 0 or dy1 != 0:
        angle = abs(degrees(atan2(dy1, dx1)))
        angle_cost = min(45 - abs(angle % 90 - 45), 0) * 10  # Штраф до 450, если угол далеко от 0 или 90
    return sqrt(dx1 * dx1 + dy1 * dy1) + floor_cost + angle_cost

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

    open_set = [(0, start)]  # (f_score, vertex)
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}

    logger.info(f"Starting A* search with initial open_set: {open_set}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.debug(f"Processing vertex: {current}, f_score={current_f}")

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            weight = g_score[end]
            logger.info(f"Path found: {path}, weight={weight}")
            return path, weight, graph if return_graph else path

        for neighbor, weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.vertices[neighbor], graph.vertices[end])
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []