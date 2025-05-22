from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    floor_cost = abs(floor1 - floor2) * 50
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
                deviation_cost = (abs(angle - 90)) * 10  # Увеличенный штраф
    # Бонус за движение вдоль прямой линии
    straight_bonus = 0
    if prev and abs(x1 - px) / (abs(y1 - py) + 1e-6) < 0.1 and abs(x2 - x1) / (abs(y2 - y1) + 1e-6) < 0.1:
        straight_bonus = -5
    return distance + floor_cost + deviation_cost + straight_bonus

def optimize_path(path: list, graph: Graph) -> list:
    if len(path) <= 2:
        return path

    optimized_path = [path[0]]
    for i in range(1, len(path) - 1):
        current = path[i]
        prev = optimized_path[-1]
        next_vertex = path[i + 1]

        # Пропускаем только избыточные mid_ или phantom_ вершины
        if ("mid_" in current or "phantom_" in current) and graph.vertices[current] == graph.vertices[next_vertex]:
            continue

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

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end], None, graph)}
    processed_vertices = set()

    logger.info(f"Starting A* search with initial open_set: {(0, start)}")
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

            # Проверяем короткий путь через phantom вершины
            start_coords = graph.vertices[start]
            end_coords = graph.vertices[end]
            if sqrt((end_coords[0] - start_coords[0]) ** 2 + (end_coords[1] - start_coords[1]) ** 2) < 100:
                phantom_start = [v for v in graph.vertices if v.startswith(f"phantom_{start.split('_')[1]}_") and v in path]
                phantom_end = [v for v in graph.vertices if v.startswith(f"phantom_{end.split('_')[1]}_") and v in path]
                if phantom_start and phantom_end:
                    short_path = [start] + phantom_start + phantom_end + [end]
                    short_weight = sum(graph.get_edge_weight(short_path[i], short_path[i+1]) for i in range(len(short_path)-1))
                    if short_weight < g_score[end]:
                        path = short_path

            final_path = optimize_path(path, graph)
            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None

        for neighbor, weight, _ in graph.edges.get(current, []):
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