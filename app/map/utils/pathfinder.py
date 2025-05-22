from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging
from app.map.models.connection import Connection

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    floor_cost = 0 if floor1 == floor2 else 10  # Штраф для разных этажей
    return distance + floor_cost

def find_nearest_point(prev_coords: tuple, candidates: list, graph: Graph) -> str:
    if not candidates:
        return None
    min_dist = float('inf')
    nearest = None
    for vertex in candidates:
        curr_coords = graph.vertices[vertex]
        dist = sqrt((curr_coords[0] - prev_coords[0]) ** 2 + (curr_coords[1] - prev_coords[1]) ** 2)
        if dist < min_dist:
            min_dist = dist
            nearest = vertex
    return nearest

def optimize_path(path: list, graph: Graph) -> list:
    if len(path) <= 2:
        return path

    optimized_path = [path[0]]  # Начинаем с start
    for i in range(1, len(path) - 1):
        current = path[i]
        prev = optimized_path[-1]
        next_vertex = path[i + 1]

        # Пропускаем избыточные вершины, если они не меняют этаж или направление
        if "mid_" in current or "phantom_" in current:
            if current not in optimized_path:  # Избегаем дубликатов
                optimized_path.append(current)
        elif "segment_" in current or "outdoor_" in current:
            # Ищем ближайшую фантомную точку или конец/начало
            candidates = []
            curr_floor = graph.vertices[current][2]
            if current.endswith("_start"):
                mid_vertex = f"mid_{current}_{current.replace('_start', '_end')}"
                end_vertex = current.replace("_start", "_end")
                if mid_vertex in graph.vertices and graph.vertices[mid_vertex][2] == curr_floor:
                    candidates.append(mid_vertex)
                if end_vertex in graph.vertices and graph.vertices[end_vertex][2] == curr_floor:
                    candidates.append(end_vertex)
            elif current.endswith("_end"):
                mid_vertex = f"mid_{current.replace('_end', '_start')}_{current}"
                start_vertex = current.replace("_end", "_start")
                if mid_vertex in graph.vertices and graph.vertices[mid_vertex][2] == curr_floor:
                    candidates.append(mid_vertex)
                if start_vertex in graph.vertices and graph.vertices[start_vertex][2] == curr_floor:
                    candidates.append(start_vertex)

            if candidates:
                nearest = find_nearest_point(graph.vertices[prev], candidates, graph)
                if nearest and nearest != optimized_path[-1]:  # Избегаем дубликатов
                    optimized_path.append(nearest)
            if current not in optimized_path:  # Добавляем только если не дубликат
                optimized_path.append(current)

    optimized_path.append(path[-1])  # Завершаем end
    return optimized_path

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

    # Обычный A*: от start к end
    open_set = [(0, start)]  # (f_score, vertex)
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}
    processed_vertices = set()

    logger.info(f"Starting A* search with initial open_set: {(0, start)}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.info(f"Processing vertex {current}, coords={graph.vertices[current]}, floor={graph.vertices[current][2]}")

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
            optimized_path = optimize_path(path, graph)
            weight = g_score[end]
            logger.info(f"Path found: {optimized_path}, weight={weight}")
            return optimized_path, weight, graph if return_graph else optimized_path

        for neighbor, weight, _ in graph.edges.get(current, []):
            # Проверяем, что переход между этажами возможен (через Connection)
            curr_floor = graph.vertices[current][2]
            next_floor = graph.vertices[neighbor][2]
            if curr_floor != next_floor and not any(conn.from_segment_id or conn.from_outdoor_id for conn in db.query(Connection).filter_by(to_segment_id=neighbor.split('_')[1] if 'segment' in neighbor else None).all()):
                continue  # Пропускаем, если нет связи между этажами

            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.vertices[neighbor], graph.vertices[end])
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []