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
                deviation_cost = (abs(angle - 90)) * 1

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

    open_set = [(0, start)]
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

            # Улучшенное добавление противоположных точек
            final_path = []
            goal_coords = graph.vertices[end]
            i = 0
            while i < len(path):
                vertex = path[i]
                final_path.append(vertex)
                if i < len(path) - 1 and ("segment_" in vertex or "outdoor_" in vertex):
                    if vertex.endswith("_start"):
                        opposite = vertex.replace("_start", "_end")
                    elif vertex.endswith("_end"):
                        opposite = vertex.replace("_end", "_start")
                    else:
                        i += 1
                        continue

                    if opposite in graph.vertices and opposite not in final_path:
                        curr_coords = graph.vertices[vertex]
                        opp_coords = graph.vertices[opposite]
                        next_vertex = path[i + 1]
                        next_coords = graph.vertices[next_vertex]

                        # Проверяем, ближе ли противоположная точка к цели
                        dist_to_goal_from_curr = sqrt((goal_coords[0] - curr_coords[0]) ** 2 + (goal_coords[1] - curr_coords[1]) ** 2)
                        dist_to_goal_from_opp = sqrt((goal_coords[0] - opp_coords[0]) ** 2 + (goal_coords[1] - opp_coords[1]) ** 2)
                        dist_to_next_from_opp = sqrt((next_coords[0] - opp_coords[0]) ** 2 + (next_coords[1] - opp_coords[1]) ** 2)

                        # Проверяем угол направления
                        dx1, dy1 = opp_coords[0] - curr_coords[0], opp_coords[1] - curr_coords[1]
                        dx2, dy2 = goal_coords[0] - curr_coords[0], goal_coords[1] - curr_coords[1]
                        if dx1 != 0 or dy1 != 0:
                            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
                            angle = abs(((angle + 180) % 360) - 180)
                            if dist_to_goal_from_opp < dist_to_goal_from_curr and angle < 90 and dist_to_next_from_opp < 100:  # Ограничение на прыжки
                                final_path.append(opposite)
                                i += 1  # Пропускаем добавление следующей точки, так как мы уже учли противоположную
                i += 1

            # Проверяем фантомные точки для сокращения пути
            optimized_path = []
            i = 0
            while i < len(final_path):
                vertex = final_path[i]
                optimized_path.append(vertex)
                if i < len(final_path) - 1 and "phantom_" in vertex:
                    curr_coords = graph.vertices[vertex]
                    next_vertex = final_path[i + 1]
                    next_coords = graph.vertices[next_vertex]
                    goal_coords = graph.vertices[end]

                    # Проверяем, если фантомная точка ближе к следующей точке или цели
                    dist_to_next = sqrt((next_coords[0] - curr_coords[0]) ** 2 + (next_coords[1] - curr_coords[1]) ** 2)
                    dist_to_goal_from_curr = sqrt((goal_coords[0] - curr_coords[0]) ** 2 + (goal_coords[1] - curr_coords[1]) ** 2)
                    dist_to_goal_from_next = sqrt((goal_coords[0] - next_coords[0]) ** 2 + (goal_coords[1] - next_coords[1]) ** 2)

                    if dist_to_next < 50 and dist_to_goal_from_curr < dist_to_goal_from_next:  # Если фантомная точка ближе
                        i += 1  # Пропускаем длинный сегмент
                i += 1

            weight = g_score[end]
            logger.info(f"Path found: {optimized_path}, weight={weight}")
            return optimized_path, weight, graph if return_graph else optimized_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None
        curr_coords = graph.vertices[current]
        goal_coords = graph.vertices[end]

        for neighbor, weight, _ in graph.edges.get(current, []):
            # Проверяем этажность при переходе
            curr_floor = curr_coords[2]
            neighbor_coords = graph.vertices[neighbor]
            neighbor_floor = neighbor_coords[2]
            if curr_floor != neighbor_floor:
                weight += 50  # Дополнительный штраф за переход между этажами

            # Избегаем длинных прыжков
            dist_to_neighbor = sqrt((neighbor_coords[0] - curr_coords[0]) ** 2 + (neighbor_coords[1] - curr_coords[1]) ** 2)
            if dist_to_neighbor > 100:  # Ограничение на длину прыжка
                continue

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