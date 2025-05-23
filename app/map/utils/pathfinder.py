# backend/app/map/utils/pathfinder.py
from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, current_building: int, goal_building: int) -> float:
    x1, y1, floor_number1 = current
    x2, y2, floor_number2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    floor_penalty = abs(floor_number1 - floor_number2) * 10.0
    return distance + floor_penalty

def find_path(db, start: str, end: str, return_graph=False, max_iterations=5000):
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

    start_data = graph.get_vertex_data(start)
    end_data = graph.get_vertex_data(end)
    start_coords = start_data["coords"]
    end_coords = end_data["coords"]
    start_building = start_data["building_id"]
    end_building = end_data["building_id"]

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start_coords, end_coords, start_building, end_building)}
    processed_vertices = set()
    iterations = 0

    logger.info(f"Starting A* search with initial open_set: {(0, start)}")
    while open_set and iterations < max_iterations:
        current_f, current = heappop(open_set)
        logger.info(f"Iteration {iterations}: Processing vertex: {current}, f_score={current_f}, g_score={g_score.get(current, float('inf'))}")

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
            weight = g_score[end]
            logger.info(f"Path found: {path}, weight={weight}")
            return path, weight, graph if return_graph else path

        current_data = graph.get_vertex_data(current)
        current_coords = current_data["coords"]
        current_building = current_data["building_id"]

        for neighbor, weight, edge_data in graph.get_neighbors(current):
            logger.info(f"Considering neighbor: {neighbor}, weight={weight}, edge_type={edge_data['type']}")
            tentative_g_score = g_score[current] + weight

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.get_vertex_data(neighbor)["coords"], end_coords, graph.get_vertex_data(neighbor)["building_id"], end_building)
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.info(f"Updated neighbor: {neighbor}, new g_score={g_score[neighbor]}, new f_score={f_score[neighbor]}")
        iterations += 1

    logger.warning(f"No path found from {start} to {end} within {max_iterations} iterations. Processed vertices: {processed_vertices}")
    return [], float('inf'), graph if return_graph else []