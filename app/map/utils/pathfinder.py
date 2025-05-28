import heapq
import logging
from app.map.graph import Graph

logger = logging.getLogger(__name__)


def heuristic(a, b, graph):
    """Оценочная функция для A* (евклидово расстояние)."""
    coords_a = graph.get_vertex_data(a)["coords"]
    coords_b = graph.get_vertex_data(b)["coords"]
    x1, y1, _ = coords_a
    x2, y2, _ = coords_b
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def find_path(graph, start, end):
    logger.info(f"Начало поиска пути от {start} до {end}")

    if start not in graph.vertices or end not in graph.vertices:
        logger.error(f"Вершина {start} или {end} не найдена в графе")
        return None, float('inf')

    # Инициализация
    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, end, graph)}
    closed_set = set()

    while open_set:
        current_f, current = heapq.heappop(open_set)

        if current == end:
            logger.info(f"Путь найден от {start} до {end}")
            return reconstruct_path(came_from, current), g_score[current]

        if current in closed_set:
            continue

        closed_set.add(current)

        for neighbor, weight, _ in graph.get_neighbors(current):
            if neighbor in closed_set:
                continue

            tentative_g_score = g_score[current] + weight

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, end, graph)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    logger.warning(f"Путь от {start} до {end} не найден")
    return None, float('inf')


def reconstruct_path(came_from, current):
    """Восстановление пути и фильтрация лишних вершин."""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()

    # Фильтрация пути: удаляем лишние end вершины, если они не связаны с переходами
    filtered_path = []
    for i, vertex in enumerate(path):
        if not vertex.endswith("_end") or i == len(path) - 1:
            filtered_path.append(vertex)
            continue

        # Проверяем, является ли предыдущая или следующая вершина частью перехода
        prev_vertex = path[i - 1] if i > 0 else None
        next_vertex = path[i + 1] if i < len(path) - 1 else None
        is_transition = (prev_vertex and prev_vertex.startswith("phantom_segment")) or \
                        (next_vertex and next_vertex.startswith("phantom_segment")) or \
                        (prev_vertex and prev_vertex.startswith("phantom_stair")) or \
                        (next_vertex and next_vertex.startswith("phantom_stair"))

        if is_transition:
            filtered_path.append(vertex)

    return filtered_path