# app/map/pathfinder/pathfinder.py
import heapq
from math import sqrt
import logging
from sqlalchemy.orm import Session
from app.map.utils.builder import build_graph, Graph

logger = logging.getLogger(__name__)

def a_star(graph: Graph, start: str, goals: list) -> tuple:
    """Находит кратчайший путь, используя A* + ALT"""
    def heuristic(a, b):
        """Эвристика: евклидово расстояние (если нет ориентиров)"""
        if graph.landmarks:
            return max(graph.landmark_heuristic(a, b) for _ in graph.landmarks)
        xa, ya, _ = graph.vertices[a]
        xb, yb, _ = graph.vertices[b]
        return sqrt((xa - xb) ** 2 + (ya - yb) ** 2)

    if start not in graph.vertices:
        logger.error(f"[a_star] Start vertex {start} not in graph.vertices")
        return None, None
    if not all(goal in graph.vertices for goal in goals):
        logger.error(f"[a_star] One of the goals {goals} not in graph.vertices")
        return None, None

    open_set = [(0, start)]  # (f_score, vertex)
    came_from = {}
    g_score = {start: 0}
    f_score = {start: min(heuristic(start, goal) for goal in goals)}
    open_set_dict = {start: f_score[start]}  # Для быстрого поиска вершин в open_set

    logger.debug(f"[a_star] Starting A* from {start} to {goals}")
    logger.debug(f"[a_star] Initial f_score[{start}] = {f_score[start]}")
    logger.debug(f"[a_star] Graph vertices: {graph.vertices}")
    logger.debug(f"[a_star] Graph edges: {dict(graph.edges)}")

    while open_set:
        f, current = heapq.heappop(open_set)
        if current not in open_set_dict:
            logger.debug(f"[a_star] Skipping vertex {current} (already processed)")
            continue
        del open_set_dict[current]

        logger.debug(f"[a_star] Processing vertex: {current}, f_score = {f_score[current]}")

        if current in goals:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            logger.debug(f"[a_star] Path found: {path}")
            return path, g_score[path[-1]]

        neighbors = graph.edges.get(current, [])
        if not neighbors:
            logger.debug(f"[a_star] No neighbors for vertex {current}")
        for neighbor, weight, neighbor_coords in neighbors:
            tentative_g_score = g_score[current] + weight

            logger.debug(f"[a_star] Considering neighbor {neighbor} of {current}, weight = {weight}, tentative_g_score = {tentative_g_score}")

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + min(heuristic(neighbor, goal) for goal in goals)

                if neighbor in open_set_dict:
                    open_set = [(f, v) for f, v in open_set if v != neighbor]
                    heapq.heapify(open_set)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
                open_set_dict[neighbor] = f_score[neighbor]
                logger.debug(f"[a_star] Added/Updated neighbor: {neighbor}, g_score = {g_score[neighbor]}, f_score = {f_score[neighbor]}")
            else:
                logger.debug(f"[a_star] Skipped neighbor {neighbor}: g_score {g_score.get(neighbor)} <= tentative_g_score {tentative_g_score}")

    logger.warning(f"[a_star] Path from {start} to {goals} not found")
    return None, None

def find_path(db: Session, start: str, end: str, return_graph: bool = False) -> tuple:
    """
    Находит кратчайший путь между start и end.
    Args:
        db: Сессия базы данных
        start: Начальная вершина (например, "room_1")
        end: Конечная вершина (например, "room_2")
        return_graph: Если True, возвращает также граф
    Returns:
        (path, weight, graph) если return_graph=True, иначе (path, weight)
    """
    logger.debug(f"Start vertex: {start}")
    logger.debug(f"End vertex: {end}")

    # Построение графа
    graph = build_graph(db, start, end)
    logger.info("Graph built successfully")

    # Поиск пути с помощью A*
    goals = [end] if isinstance(end, str) else end
    path, weight = a_star(graph, start, goals)

    if path is None:
        logger.warning(f"No path found from {start} to {end}")
        return (None, None, graph) if return_graph else (None, None)

    logger.info(f"A* result: path={path}, weight={weight}")
    return (path, weight, graph) if return_graph else (path, weight)