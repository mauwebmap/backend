from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    # Штраф за смену этажа
    floor_cost = abs(floor1 - floor2) * 30 if floor1 != floor2 else 0
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)

    deviation_cost = 0
    straight_bonus = 0
    if prev and graph:
        px, py, _ = prev
        dx1, dy1 = x1 - px, y1 - py
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle < 70 or angle > 110:
                deviation_cost = (abs(angle - 90)) * 5
        if (abs(dx1) < 10 and abs(dx2) < 10) or (abs(dy1) < 10 and abs(dy2) < 10):
            straight_bonus = -10

    # Дополнительный бонус за приближение к конечной точке через _end точки
    current_vertex = [v for v, c in graph.vertices.items() if c == current][0]
    if "_end" in current_vertex and current_vertex.split("_")[0] in ["segment", "outdoor"]:
        distance *= 0.9  # Уменьшаем вес для _end точек, чтобы они были предпочтительнее

    # Бонус за phantom точки
    if "phantom_" in current_vertex:
        distance *= 0.8  # Уменьшаем вес для phantom точек

    return distance + floor_cost + deviation_cost + straight_bonus

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

            # Добавляем все возможные противоположные и phantom точки
            final_path = []
            i = 0
            while i < len(path):
                vertex = path[i]
                final_path.append(vertex)
                if i < len(path) - 1:
                    next_vertex = path[i + 1]
                    # Добавляем противоположные точки для segment и outdoor
                    if ("segment_" in vertex or "outdoor_" in vertex) and "phantom" not in vertex:
                        if vertex.endswith("_start"):
                            opposite = vertex.replace("_start", "_end")
                        elif vertex.endswith("_end"):
                            opposite = vertex.replace("_end", "_start")
                        else:
                            i += 1
                            continue
                        if opposite in graph.vertices and opposite not in final_path:
                            # Проверяем все возможные связи
                            for edge in graph.edges.get(vertex, []):
                                if edge[0] == opposite and (opposite, next_vertex) in [(e[0], e[1]) for e in graph.edges.get(opposite, [])]:
                                    final_path.append(opposite)
                                    break

                    # Добавляем phantom точки между текущей и следующей вершиной
                    for potential_phantom in graph.vertices:
                        if potential_phantom.startswith("phantom_") and potential_phantom not in final_path:
                            if (vertex, potential_phantom) in [(e[0], e[1]) for e in graph.edges.get(vertex, [])] and \
                               (potential_phantom, next_vertex) in [(e[0], e[1]) for e in graph.edges.get(potential_phantom, [])]:
                                final_path.append(potential_phantom)
                i += 1

            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        prev_coords = graph.vertices[prev_vertex] if prev_vertex else None

        for neighbor, weight, _ in graph.edges.get(current, []):
            # Штрафуем длинные сегменты
            if weight > 100:
                weight *= 1.5

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