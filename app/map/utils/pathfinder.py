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
    logger.info(f"Начало поиска пути от {start} до {end}")

    open_set = [(0, start, [start])]
    heapq.heapify(open_set)
    g_scores = {start: 0}
    f_scores = {start: heuristic(start, end, graph)}
    came_from = {}
    visited = set()
    iteration = 0
    max_iterations = 20000  # Увеличиваем лимит для больших графов

    while open_set and iteration < max_iterations:
        f_score, current, path = heapq.heappop(open_set)
        logger.info(f"Итерация {iteration}: обработка вершины {current}, f_score={f_score}, g_score={g_scores[current]}")

        if current == end:
            logger.info(f"Путь найден: {path}, вес={g_scores[current]}")
            return path, g_scores[current]

        if current in visited:
            continue

        visited.add(current)
        neighbors = graph.get_neighbors(current)
        logger.info(f"Соседи вершины {current}: {[(n, w) for n, w, _ in neighbors]}")

        for neighbor, weight, edge_data in neighbors:
            if neighbor in visited:
                continue

            logger.info(f"Рассматривается сосед: {neighbor}, вес={weight}")
            tentative_g_score = g_scores[current] + weight

            if neighbor not in g_scores or tentative_g_score < g_scores[neighbor]:
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g_score
                f_scores[neighbor] = tentative_g_score + heuristic(neighbor, end, graph)
                new_path = path + [neighbor]
                logger.info(f"Обновлён сосед: {neighbor}, новый g_score={tentative_g_score}, новый f_score={f_scores[neighbor]}")
                heapq.heappush(open_set, (f_scores[neighbor], neighbor, new_path))

        iteration += 1

    logger.info(f"Путь от {start} до {end} не найден в течение {max_iterations} итераций. Обработано вершин: {len(visited)}")
    return [], float("inf")