from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    floor_cost = abs(floor1 - floor2) * 50  # Уменьшенный штраф за этаж
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    deviation_cost = 0
    if prev and graph:
        px, py, _ = prev
        dx1, dy1 = x1 - px, y1 - py  # Вектор от предыдущей точки к текущей
        dx2, dy2 = x2 - x1, y2 - y1  # Вектор от текущей к цели
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            # Штрафуем, если угол поворота больше 90 градусов (разворот назад)
            if angle > 90:
                deviation_cost = (angle - 90) * 5  # Высокий штраф за разворот
            elif angle < 70 or angle > 110:
                deviation_cost = (abs(angle - 90)) * 1  # Минимальный штраф за отклонение

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

            # Упрощенное добавление противоположных точек с приоритетом ближайших
            final_path = []
            goal_coords = graph.vertices[end]
            for i, vertex in enumerate(path):
                final_path.append(vertex)
                if i < len(path) - 1 and ("segment_" in vertex or "outdoor_" in vertex):
                    if vertex.endswith("_start"):
                        opposite = vertex.replace("_start", "_end")
                    elif vertex.endswith("_end"):
                        opposite = vertex.replace("_end", "_start")
                    else:
                        continue
                    if opposite in graph.vertices and opposite not in final_path:
                        curr_coords = graph.vertices[vertex]
                        opp_coords = graph.vertices[opposite]
                        next_coords = graph.vertices[path[i + 1]]
                        # Проверяем, является ли противоположная точка ближе к следующей в направлении к цели
                        curr_dist = sqrt((next_coords[0] - curr_coords[0]) ** 2 + (next_coords[1] - curr_coords[1]) ** 2)
                        opp_dist = sqrt((next_coords[0] - opp_coords[0]) ** 2 + (next_coords[1] - opp_coords[1]) ** 2)
                        goal_angle = degrees(atan2(next_coords[1] - opp_coords[1], next_coords[0] - opp_coords[0]))
                        curr_angle = degrees(atan2(goal_coords[1] - curr_coords[1], goal_coords[0] - curr_coords[0]))
                        angle_diff = abs(((goal_angle - curr_angle + 180) % 360) - 180)
                        if opp_dist < curr_dist and angle_diff < 90:  # Приоритет ближе и в направлении цели
                            final_path.append(opposite)

            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None
        goal_coords = graph.vertices[end]

        for neighbor, weight, _ in graph.edges.get(current, []):
            if neighbor in processed_vertices:
                continue
            curr_coords = graph.vertices[current]
            neighbor_coords = graph.vertices[neighbor]
            # Проверяем направление к цели
            dx1, dy1 = neighbor_coords[0] - curr_coords[0], neighbor_coords[1] - curr_coords[1]
            dx2, dy2 = goal_coords[0] - curr_coords[0], goal_coords[1] - curr_coords[1]
            if dx1 != 0 or dy1 != 0:
                angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
                angle = abs(((angle + 180) % 360) - 180)
                if angle > 90:  # Исключаем развороты назад
                    continue

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    neighbor_coords, goal_coords, curr_coords, graph
                )
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []