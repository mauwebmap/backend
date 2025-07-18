# app/map/utils/pathfinder.py
from typing import List

from .graph import Graph
import heapq
import math
import logging

logger = logging.getLogger(__name__)

def find_path(graph: Graph, start: str, end: str) -> tuple:
    logger.info(f"Начало поиска пути от {start} до {end}")

    if start not in graph.vertices or end not in graph.vertices:
        logger.error(f"Вершина {start} или {end} не найдена в графе")
        return [], float("inf")

    open_set = [(0, start)]
    came_from = {}
    g_scores = {start: 0}
    f_scores = {start: graph.heuristic(start, end)}
    visited = set()

    while open_set:
        f_score, current = heapq.heappop(open_set)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            logger.info(f"Путь найден: {path}, вес={g_scores[end]}")
            return filter_path(graph, path), g_scores[end]

        if current in visited:
            continue

        visited.add(current)
        for neighbor, weight, edge_data in graph.get_neighbors(current):
            if neighbor in visited:
                continue

            tentative_g_score = g_scores[current] + weight
            if neighbor not in g_scores or tentative_g_score < g_scores[neighbor]:
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g_score
                f_scores[neighbor] = tentative_g_score + graph.heuristic(neighbor, end)
                heapq.heappush(open_set, (f_scores[neighbor], neighbor))

    logger.info(f"Путь от {start} до {end} не найден")
    return [], float("inf")

def filter_path(graph: Graph, path: List[str]) -> List[str]:
    filtered_path = []
    i = 0
    while i < len(path):
        vertex = path[i]
        # Пропускаем segment_X_start и segment_X_end
        if vertex.startswith("segment_") and (vertex.endswith("_start") or vertex.endswith("_end")):
            i += 1
            continue

        if vertex not in filtered_path:
            filtered_path.append(vertex)

        # Полностью отображаем лестницы (включая _far)
        if i + 1 < len(path) and graph.get_edge_data(vertex, path[i + 1]).get("type") == "лестница":
            while i + 1 < len(path) and graph.get_edge_data(path[i], path[i + 1]).get("type") == "лестница":
                i += 1
                if path[i] not in filtered_path:
                    filtered_path.append(path[i])
            # Проверяем наличие _far точек
            if vertex.startswith("phantom_stair_") and not vertex.endswith("_far"):
                far_vertex = vertex + "_far"
                if far_vertex in path[i:]:
                    idx = path[i:].index(far_vertex) + i
                    if far_vertex not in filtered_path:
                        filtered_path.append(far_vertex)
                    # Добавляем соответствующую _far точку для пары
                    next_vertex = path[idx + 1] if idx + 1 < len(path) else None
                    if next_vertex and next_vertex.startswith("phantom_stair_") and not next_vertex.endswith("_far"):
                        far_next = next_vertex + "_far"
                        if far_next in path[idx:]:
                            if far_next not in filtered_path:
                                filtered_path.append(far_next)
                    i = idx

        # Полностью отображаем уличные сегменты для "дверь-улица" или "улица-дверь"
        elif i + 1 < len(path) and graph.get_edge_data(vertex, path[i + 1]).get("type") == "дверь":
            next_vertex = path[i + 1]
            if i + 2 < len(path):
                next_next_vertex = path[i + 2]
                if graph.get_edge_data(vertex, next_vertex).get("type") == "дверь":
                    outdoor_id = None
                    if next_vertex.startswith("outdoor_"):
                        outdoor_id = int(next_vertex.split("_")[1])
                    elif next_next_vertex.startswith("outdoor_"):
                        outdoor_id = int(next_next_vertex.split("_")[1])
                    if outdoor_id is not None:
                        start_vertex = f"outdoor_{outdoor_id}_start"
                        end_vertex = f"outdoor_{outdoor_id}_end"
                        if start_vertex in path[i:i+3] and end_vertex in path[i:i+3]:
                            # Добавляем только начальную и конечную точки уличного сегмента
                            if start_vertex not in filtered_path:
                                filtered_path.append(start_vertex)
                            if end_vertex not in filtered_path:
                                filtered_path.append(end_vertex)
                            i += 2
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1
            else:
                i += 1
        else:
            i += 1

    return filtered_path