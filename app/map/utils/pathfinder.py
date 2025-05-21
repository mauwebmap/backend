import heapq
from math import sqrt
import logging
from sqlalchemy.orm import Session
from app.map.utils.builder import build_graph, Graph

logger = logging.getLogger(__name__)

def a_star(graph: Graph, start: str, goals: list) -> tuple:
    """Находит кратчайший путь, используя A* с фильтрацией циклов"""
    def heuristic(a, b):
        if graph.landmarks:
            return max(graph.landmark_heuristic(a, b) for _ in graph.landmarks)
        xa, ya, _ = graph.vertices[a]
        xb, yb, _ = graph.vertices[b]
        return sqrt((xa - xb) ** 2 + (ya - yb) ** 2)

    if start not in graph.vertices:
        logger.error(f"[A*] Стартовая вершина '{start}' отсутствует в графе.")
        return None, None
    if not all(goal in graph.vertices for goal in goals):
        logger.error(f"[A*] Одна или несколько целевых вершин отсутствуют в графе: {goals}")
        return None, None

    logger.info(f"[A*] Поиск пути от '{start}' до {goals}")

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: min(heuristic(start, goal) for goal in goals)}
    open_set_dict = {start: f_score[start]}
    visited = set()  # Для отслеживания посещенных вершин

    while open_set:
        _, current = heapq.heappop(open_set)
        if current not in open_set_dict:
            continue
        del open_set_dict[current]

        if current in goals:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            logger.info(f"[A*] Путь найден. Длина: {g_score[path[-1]]}. Вершин: {len(path)}")
            logger.info(f"[A*] result: path={path}, weight={g_score[path[-1]]}")
            return path, g_score[path[-1]]

        if current in visited:
            continue  # Пропускаем уже посещенные вершины
        visited.add(current)

        for neighbor, weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight

            # Проверяем, улучшает ли путь переход к соседней вершине
            if neighbor not in g_score or tentative_g_score < g_score.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + min(heuristic(neighbor, goal) for goal in goals)

                if neighbor in open_set_dict:
                    open_set = [(f, v) for f, v in open_set if v != neighbor]
                    heapq.heapify(open_set)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
                open_set_dict[neighbor] = f_score[neighbor]

    logger.warning(f"[A*] Путь от '{start}' до {goals} не найден.")
    return None, None

def find_path(db: Session, start: str, end: str, return_graph: bool = False) -> tuple:
    """Находит кратчайший путь между start и end."""
    logger.info(f"[find_path] Запрос пути от '{start}' до '{end}'")

    graph = build_graph(db, start, end)
    logger.info("[find_path] Граф построен")

    goals = [end] if isinstance(end, str) else end
    path, weight = a_star(graph, start, goals)

    if path is None:
        logger.warning(f"[find_path] Путь не найден от '{start}' до '{end}'")
        return (None, None, graph) if return_graph else (None, None)

    logger.info(f"[find_path] Путь успешно найден. Длина: {weight}. Вершин: {len(path)}")
    return (path, weight, graph) if return_graph else (path, weight)