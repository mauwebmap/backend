# backend/app/map/utils/pathfinder.py
from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, current_building: int, goal_building: int) -> float:
    x1, y1, floor_id1 = current
    x2, y2, floor_id2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    # Штраф за разные этажи
    floor_penalty = abs(floor_id1 - floor_id2) * 50.0
    # Штраф за разные здания
    building_penalty = 100.0 if current_building != goal_building and (current_building is not None and goal_building is not None) else 0.0
    return distance + floor_penalty + building_penalty

def find_path(db, start: str, end: str, return_graph=False):
    logger.info(f"Starting pathfinding from {start} to {end}")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Graph built with {len(graph.vertices)} vertices")
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        graph = Graph()
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

            weight = g_score[end]
            logger.info(f"Path found: {path}, weight={weight}")

            return path, weight, graph if return_graph else []

        current_data = graph.get_vertex_data(current)
        current_coords = current_data["coords"]
        current_building = current_data["building_id"]

        for neighbor, weight, _ in graph.get_neighbors(current):
            neighbor_data = graph.get_vertex_data(neighbor)
            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor_data["coords"], end_coords, neighbor_data["building_id"], end_building)
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []