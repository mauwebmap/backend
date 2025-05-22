from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

# Маппинг floor_id -> реальный номер этажа
FLOOR_ID_TO_NUMBER = {
    1: 1,  # Уличный уровень
    8: 1,  # Реальный 1-й этаж в здании
    11: 2,  # Реальный 2-й этаж в здании
}


def heuristic(current: tuple, goal: tuple) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    floor_cost = 0 if floor1 == floor2 else 10
    return distance + floor_cost


def fix_segment_order(path: list, graph: Graph) -> list:
    """Исправляет порядок вершин (start -> end)."""
    corrected_path = []
    i = 0
    while i < len(path):
        vertex = path[i]
        corrected_path.append(vertex)

        # Если текущая вершина — это segment_end, проверяем, есть ли segment_start
        if i + 1 < len(path) and "segment_" in vertex and "_end" in vertex:
            next_vertex = path[i + 1]
            start_vertex = vertex.replace("_end", "_start")
            if next_vertex == start_vertex:
                corrected_path[-1] = start_vertex  # Меняем местами
                corrected_path.append(vertex)
                i += 2
            else:
                i += 1
        else:
            i += 1
    return corrected_path


def optimize_path(path: list, graph: Graph) -> list:
    if len(path) <= 2:
        return path

    optimized_path = [path[0]]
    for i in range(1, len(path) - 1):
        current = path[i]
        prev = optimized_path[-1]
        next_vertex = path[i + 1]

        curr_floor = graph.vertices[current][2]
        prev_floor = graph.vertices[prev][2]
        next_floor = graph.vertices[next_vertex][2]

        # Пропускаем phantom_ точки, если они не нужны
        if "phantom_" in current:
            continue
        # Пропускаем mid_ точки, если они не связаны с переходом этажей
        if "mid_" in current and curr_floor == prev_floor and curr_floor == next_floor:
            continue
        # Объединяем близкие segment_ точки
        if "segment_" in current and "segment_" in prev and graph.get_edge_weight(prev, current) <= 2.0:
            continue

        if current not in optimized_path:
            optimized_path.append(current)

    optimized_path.append(path[-1])
    return optimized_path


def get_real_floor(floor_id: int) -> int:
    return FLOOR_ID_TO_NUMBER.get(floor_id, floor_id)


def find_path(db, start: str, end: str, return_graph=False):
    logger.info(f"Starting pathfinding from {start} to {end} (A*)")
    try:
        graph = build_graph(db, start, end)
        logger.info(f"Graph built with {len(graph.vertices)} vertices")
    except Exception as e:
        logger.error(f"Failed to build graph: {e}")
        return [], float('inf'), graph if return_graph else []

    if start not in graph.vertices or end not in graph.vertices:
        logger.warning(f"Start {start} or end {end} not in graph vertices")
        return [], float('inf'), graph if return_graph else []

    # A* поиск
    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}
    processed_vertices = set()

    logger.info(f"Starting A* search with initial open_set: {(0, start)}")
    while open_set:
        current_f, current = heappop(open_set)
        if current in processed_vertices:
            continue
        processed_vertices.add(current)

        logger.info(
            f"Processing vertex {current}, coords={graph.vertices[current]}, floor={graph.vertices[current][2]}")

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            # Исправляем порядок вершин (start -> end)
            path = fix_segment_order(path, graph)
            # Оптимизируем путь
            optimized_path = optimize_path(path, graph)
            weight = g_score[end]

            # Формируем маршрут с реальными номерами этажей
            route = []
            current_floor = None
            floor_points = []

            for vertex in optimized_path:
                floor_id = graph.vertices[vertex][2]
                real_floor = get_real_floor(floor_id)

                if current_floor is None:
                    current_floor = real_floor
                    floor_points = [{"x": graph.vertices[vertex][0], "y": graph.vertices[vertex][1], "vertex": vertex}]
                elif current_floor != real_floor:
                    route.append({"floor": current_floor, "points": floor_points})
                    current_floor = real_floor
                    floor_points = [{"x": graph.vertices[vertex][0], "y": graph.vertices[vertex][1], "vertex": vertex}]
                else:
                    floor_points.append(
                        {"x": graph.vertices[vertex][0], "y": graph.vertices[vertex][1], "vertex": vertex})

            if floor_points:
                route.append({"floor": current_floor, "points": floor_points})

            logger.info(f"Path found: {optimized_path}, weight={weight}")
            return route, weight, graph if return_graph else route

        for neighbor, weight, _ in graph.edges.get(current, []):
            curr_floor = graph.vertices[current][2]
            next_floor = graph.vertices[neighbor][2]
            if curr_floor != next_floor:
                connection_exists = False
                for conn in db.query(Connection).all():
                    if (conn.from_floor_id == curr_floor and conn.to_floor_id == next_floor) or \
                            (conn.from_floor_id == next_floor and conn.to_floor_id == curr_floor):
                        connection_exists = True
                        break
                if not connection_exists:
                    continue

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.vertices[neighbor], graph.vertices[end])
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []