from .graph import Graph
import heapq
import math
import logging

logger = logging.getLogger(__name__)

def heuristic(vertex1: str, vertex2: str, graph: Graph) -> float:
    coords1 = graph.get_vertex_data(vertex1)["coords"]
    coords2 = graph.get_vertex_data(vertex2)["coords"]
    floor_diff = abs(coords1[2] - coords2[2]) * 10
    distance_2d = math.sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
    return distance_2d + floor_diff

def find_path(graph: Graph, start: str, end: str) -> tuple:
    logger.info(f"Начало поиска пути от {start} до {end}")

    if start not in graph.vertices or end not in graph.vertices:
        logger.error(f"Вершина {start} или {end} отсутствует в графе")
        return [], float("inf")

    open_set = [(0, start, [start])]
    heapq.heapify(open_set)
    g_scores = {start: 0}
    f_scores = {start: heuristic(start, end, graph)}
    came_from = {}
    visited = set()
    iteration = 0
    max_iterations = 20000

    while open_set and iteration < max_iterations:
        f_score, current, path = heapq.heappop(open_set)
        logger.debug(f"Итерация {iteration}: {current}, f_score={f_score}")

        if current == end:
            logger.info(f"Путь найден: {path}, вес={g_scores[current]}")
            return path, g_scores[current]

        if current in visited:
            continue

        visited.add(current)
        neighbors = graph.get_neighbors(current)

        for neighbor, weight, _ in neighbors:
            if neighbor in visited:
                continue

            tentative_g_score = g_scores[current] + weight
            if neighbor not in g_scores or tentative_g_score < g_scores[neighbor]:
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g_score
                f_scores[neighbor] = tentative_g_score + heuristic(neighbor, end, graph)
                new_path = path + [neighbor]
                heapq.heappush(open_set, (f_scores[neighbor], neighbor, new_path))

        iteration += 1

    logger.warning(f"Путь не найден за {max_iterations} итераций")
    return [], float("inf")