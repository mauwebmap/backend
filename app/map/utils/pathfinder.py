from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    floor_cost = abs(floor1 - floor2) * 100
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    # Штраф за отклонение от прямой линии
    deviation_cost = 0
    if prev and graph:
        px, py, _ = prev
        # Вектор от предыдущей точки к текущей
        dx1, dy1 = x1 - px, y1 - py
        # Вектор от текущей точки к цели
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle < 70 or angle > 110:  # Штраф за углы вне 70-110 градусов
                deviation_cost = (abs(angle - 90)) * 5

    return distance + floor_cost + deviation_cost

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

    logger.info(f"Starting A* search with initial open_set: {open_set}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.debug(f"Processing vertex: {current}, f_score={current_f}")

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

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None

        for neighbor, weight, _ in graph.edges.get(current, []):
            # Проверяем, является ли соседний сегмент/аутдор ближе к концу текущего
            current_coords = graph.vertices[current]
            neighbor_coords = graph.vertices[neighbor]
            is_segment_or_outdoor = current.startswith("segment_") or current.startswith("outdoor_")
            if is_segment_or_outdoor and prev_coords:
                curr_start = graph.vertices[current.replace("_end", "_start")] if current.endswith("_end") else current_coords
                curr_end = graph.vertices[current.replace("_start", "_end")] if current.endswith("_start") else current_coords
                dist_to_curr_start = sqrt((current_coords[0] - curr_start[0]) ** 2 + (current_coords[1] - curr_start[1]) ** 2)
                dist_to_curr_end = sqrt((current_coords[0] - curr_end[0]) ** 2 + (current_coords[1] - curr_end[1]) ** 2)
                dist_to_neighbor = sqrt((current_coords[0] - neighbor_coords[0]) ** 2 + (current_coords[1] - neighbor_coords[1]) ** 2)
                if dist_to_neighbor < min(dist_to_curr_start, dist_to_curr_end):
                    continue  # Пропускаем, если сосед ближе, чем конец сегмента

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor], graph.vertices[end], current_coords, graph
                )
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []