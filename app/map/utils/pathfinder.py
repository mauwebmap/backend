from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    floor_cost = 0 if floor1 == floor2 else 10  # Минимальный штраф для разных этажей
    return distance + floor_cost

def find_path(db, start: str, end: str, return_graph=False):
    logger.info(f"Starting pathfinding from {start} to {end} (reverse A*)")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Graph built with {len(graph.vertices)} vertices")
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        return [], float('inf'), graph if return_graph else []

    if start not in graph.vertices or end not in graph.vertices:
        logger.warning(f"Start {start} or end {end} not in graph vertices")
        return [], float('inf'), graph if return_graph else []

    # Обратный A*: начинаем от end к start
    open_set = [(0, end)]  # (f_score, vertex)
    came_from = {}
    g_score = {end: 0}
    f_score = {end: heuristic(graph.vertices[end], graph.vertices[start])}
    processed_vertices = set()

    logger.info(f"Starting reverse A* search with initial open_set: {open_set}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.debug(f"Processing vertex: {current}, f_score={current_f}")

        if current in processed_vertices:
            continue
        processed_vertices.add(current)

        if current == start:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(end)
            path.reverse()  # Переворачиваем путь, чтобы он шел от start к end

            # Оптимизация пути: добавляем фантомные точки, если это не start или end
            optimized_path = [path[0]]  # Начинаем с start
            for i in range(1, len(path) - 1):
                vertex = path[i]
                if "mid_" in vertex:  # Используем фантомную точку
                    optimized_path.append(vertex)
                elif "segment_" in vertex or "outdoor_" in vertex:
                    # Проверяем, есть ли фантомная точка для этого сегмента/аутдора
                    if i < len(path) - 2:
                        next_vertex = path[i + 1]
                        mid_vertex = f"mid_{vertex}_{next_vertex}" if vertex.endswith("_start") else f"mid_{next_vertex}_{vertex}"
                        if mid_vertex in graph.vertices:
                            optimized_path.append(mid_vertex)
                    optimized_path.append(vertex)
            optimized_path.append(path[-1])  # Завершаем end

            weight = g_score[start]
            logger.info(f"Path found: {optimized_path}, weight={weight}")
            return optimized_path, weight, graph if return_graph else optimized_path

        for neighbor, weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.vertices[neighbor], graph.vertices[start])
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []