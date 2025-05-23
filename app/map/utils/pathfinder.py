# backend/app/map/utils/pathfinder.py
from .builder import build_graph
from heapq import heappush, heappop
from math import sqrt
import logging

logger = logging.getLogger(__name__)

def heuristic(a: tuple, b: tuple) -> float:
    return sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)

def find_path(db, start: str, end: str, return_graph=False, max_iterations=10000):
    logger.info(f"Starting pathfinding from {start} to {end}")
    graph = build_graph(db, start, end)
    logger.info(f"Graph built with {len(graph.vertices)} vertices")

    start_data = graph.get_vertex_data(start)
    end_data = graph.get_vertex_data(end)
    if not start_data or not end_data:
        logger.warning(f"Start or end vertex not found in graph")
        return [], float('inf'), graph if return_graph else []

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start_data["coords"][:2], end_data["coords"][:2])}
    closed_set = set()
    iterations = 0

    while open_set and iterations < max_iterations:
        current_f, current = heappop(open_set)
        if current in closed_set:
            continue

        logger.info(f"Iteration {iterations}: Processing vertex: {current}, f_score={current_f}, g_score={g_score.get(current, float('inf'))}")
        closed_set.add(current)

        if current == end:
            logger.info(f"Path found: {reconstruct_path(came_from, current)}, weight={g_score[current]}")
            path = reconstruct_path(came_from, current)
            return path, g_score[current], graph if return_graph else path

        neighbors = graph.get_neighbors(current)
        logger.info(f"Neighbors of {current}: {[(neighbor, weight) for neighbor, weight, _ in neighbors]}")
        for neighbor, weight, _ in neighbors:
            if neighbor in closed_set:
                continue

            tentative_g_score = g_score.get(current, float('inf')) + weight
            logger.info(f"Considering neighbor: {neighbor}, weight={weight}")

            if tentative_g_score < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.get_vertex_data(neighbor)["coords"][:2], end_data["coords"][:2])
                logger.info(f"Updated neighbor: {neighbor}, new g_score={tentative_g_score}, new f_score={f_score[neighbor]}")
                heappush(open_set, (f_score[neighbor], neighbor))

        iterations += 1

    logger.warning(f"No path found from {start} to {end} within {max_iterations} iterations. Processed vertices: {closed_set}")
    return [], float('inf'), graph if return_graph else []

def reconstruct_path(came_from: dict, current: str) -> list:
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    return path[::-1]