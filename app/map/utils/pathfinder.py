# backend/app/map/utils/pathfinder.py
from .graph import Graph
import heapq
import math
import logging

logger = logging.getLogger(__name__)

def heuristic(vertex1: str, vertex2: str, graph: Graph) -> float:
    coords1 = graph.get_vertex_data(vertex1)["coords"]
    coords2 = graph.get_vertex_data(vertex2)["coords"]
    return math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)

def find_path(graph: Graph, start: str, end: str) -> tuple:
    logger.info(f"Starting pathfinding from {start} to {end}")

    open_set = [(0, start, [start])]
    heapq.heapify(open_set)
    g_scores = {start: 0}
    f_scores = {start: heuristic(start, end, graph)}
    came_from = {}
    visited = set()
    iteration = 0
    max_iterations = 10000

    while open_set and iteration < max_iterations:
        f_score, current, path = heapq.heappop(open_set)
        logger.info(f"Iteration {iteration}: Processing vertex: {current}, f_score={f_score}, g_score={g_scores[current]}")

        if current == end:
            logger.info(f"Path found: {path}, weight={g_scores[current]}")
            return path, g_scores[current]

        visited.add(current)
        neighbors = graph.get_neighbors(current)
        logger.info(f"Neighbors of {current}: {[(n, w) for n, w, _ in neighbors]}")

        for neighbor, weight, edge_data in neighbors:
            if neighbor in visited:
                continue

            logger.info(f"Considering neighbor: {neighbor}, weight={weight}")
            tentative_g_score = g_scores[current] + weight

            if neighbor not in g_scores or tentative_g_score < g_scores[neighbor]:
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g_score
                f_scores[neighbor] = tentative_g_score + heuristic(neighbor, end, graph)
                new_path = path + [neighbor]
                logger.info(f"Updated neighbor: {neighbor}, new g_score={tentative_g_score}, new f_score={f_scores[neighbor]}")
                heapq.heappush(open_set, (f_scores[neighbor], neighbor, new_path))

        iteration += 1

    logger.warning(f"No path found from {start} to {end} within {max_iterations} iterations. Processed vertices: {visited}")
    return [], float("inf")