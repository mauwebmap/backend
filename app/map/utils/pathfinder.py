import heapq
import logging
import math
from typing import Dict, List, Tuple

from app.map.utils.builder import Graph

logger = logging.getLogger(__name__)

def heuristic(coords1: tuple, coords2: tuple) -> float:
    return math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)

def find_path(graph: Graph, start: str, end: str) -> Tuple[List[str], float]:
    logger.info(f"Starting pathfinding from {start} to {end}")

    try:
        if start not in graph.vertices or end not in graph.vertices:
            logger.error(f"Start {start} or end {end} vertex not found in graph")
            return [], float('inf')

        open_set = [(0, start, 0)]
        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {start: 0}
        f_score: Dict[str, float] = {start: heuristic(graph.get_vertex_data(start)["coords"], graph.get_vertex_data(end)["coords"])}
        closed_set = set()
        iteration = 0
        max_iterations = 10000  # Ограничение на количество итераций

        while open_set:
            iteration += 1
            if iteration > max_iterations:
                logger.error("Pathfinding exceeded maximum iterations")
                return [], float('inf')

            _, current, _ = heapq.heappop(open_set)

            if current in closed_set:
                continue

            logger.info(f"Iteration {iteration}: Processing vertex: {current}, f_score={f_score[current]}, g_score={g_score[current]}")
            closed_set.add(current)

            if current == end:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()

                # Улучшенная фильтрация
                filtered_path = []
                seen_vertices = set()
                prev_vertex = None
                for vertex in path:
                    if vertex not in seen_vertices:
                        if prev_vertex and "stair" in vertex and "stair" in prev_vertex:
                            prev_seg = prev_vertex.split("_to_")[-1] if "to" in prev_vertex else prev_vertex.split("_from_")[-1]
                            curr_seg = vertex.split("_to_")[-1] if "to" in vertex else vertex.split("_from_")[-1]
                            if prev_seg == curr_seg:
                                logger.debug(f"Skipping redundant stair transition: {prev_vertex} -> {vertex}")
                                continue
                        filtered_path.append(vertex)
                        seen_vertices.add(vertex)
                        prev_vertex = vertex
                    else:
                        logger.debug(f"Removed duplicate vertex: {vertex}")

                total_weight = g_score[end]
                logger.info(f"Path found: {filtered_path}, weight={total_weight}")
                return filtered_path, total_weight

            neighbors = graph.get_neighbors(current)
            logger.info(f"Neighbors of {current}: {neighbors}")

            for neighbor, weight, data in neighbors:
                if neighbor in closed_set:
                    continue

                tentative_g_score = g_score[current] + weight

                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    logger.info(f"Considering neighbor: {neighbor}, weight={weight}")
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + heuristic(graph.get_vertex_data(neighbor)["coords"], graph.get_vertex_data(end)["coords"])
                    logger.info(f"Updated neighbor: {neighbor}, new g_score={g_score[neighbor]}, new f_score={f_score[neighbor]}")
                    heapq.heappush(open_set, (f_score[neighbor], neighbor, iteration))

        logger.warning(f"No path found from {start} to {end}")
        return [], float('inf')

    except Exception as e:
        logger.error(f"Error during pathfinding: {str(e)}")
        return [], float('inf')