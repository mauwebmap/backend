from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    floor_cost = abs(floor1 - floor2) * 50  # Штраф за этаж
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    deviation_cost = 0
    if prev and graph:
        px, py, _ = prev
        dx1, dy1 = x1 - px, y1 - py
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle < 70 or angle > 110:
                deviation_cost = (abs(angle - 90)) * 5  # Увеличенный штраф за резкие повороты
    return distance + floor_cost + deviation_cost

def optimize_path(path: list, graph: Graph) -> list:
    if len(path) <= 2:
        return path

    optimized_path = [path[0]]
    for i in range(1, len(path) - 1):
        current = path[i]
        prev = optimized_path[-1]
        next_vertex = path[i + 1]

        # Пропускаем, если текущая вершина — это mid_ или phantom_ без изменения направления
        if "mid_" in current or "phantom_" in current:
            continue

        # Добавляем только если это изменение направления или конец сегмента
        curr_coords = graph.vertices[current]
        prev_coords = graph.vertices[prev]
        next_coords = graph.vertices[next_vertex]
        dx1, dy1 = curr_coords[0] - prev_coords[0], curr_coords[1] - prev_coords[1]
        dx2, dy2 = next_coords[0] - curr_coords[0], next_coords[1] - curr_coords[1]
        if dx1 * dx2 + dy1 * dy2 < 0 or "end" in current or "start" in current:
            optimized_path.append(current)

    optimized_path.append(path[-1])
    return optimized_path

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
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end], None, graph)}
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

            # Оптимизируем путь
            final_path = optimize_path(path, graph)
            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None

        for neighbor, weight, _ in graph.edges.get(current, []):
            # Проверяем, что переход между вершинами следует вдоль сегмента
            curr_coords = graph.vertices[current]
            next_coords = graph.vertices[neighbor]
            if prev_coords and abs(curr_coords[0] - next_coords[0]) > 50 and abs(curr_coords[1] - next_coords[1]) > 50:
                continue  # Пропускаем слишком большие "прыжки"

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor], graph.vertices[end], graph.vertices[current], graph
                )
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []