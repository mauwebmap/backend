from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    
    # Евклидово расстояние
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    # Штраф за смену этажа
    floor_diff = abs(floor1 - floor2)
    floor_cost = floor_diff * 50
    
    return distance + floor_cost

def optimize_path_with_phantoms(path: list, graph: Graph) -> list:
    """Оптимизирует путь, добавляя фантомные точки только внутри сегментов"""
    if len(path) <= 2:
        return path

    optimized = []
    i = 0
    while i < len(path):
        current = path[i]
        optimized.append(current)
        
        if i + 1 < len(path):
            next_vertex = path[i + 1]
            
            # Если текущая вершина - комната, а следующая - часть сегмента
            if current.startswith("room_") and ("segment_" in next_vertex or "outdoor_" in next_vertex):
                # Проверяем, есть ли фантомная точка для этой комнаты на этом сегменте
                segment_id = next_vertex.split("_")[1]
                phantom = f"phantom_room_{current.split('_')[1]}_segment_{segment_id}"
                if phantom in graph.vertices:
                    optimized.append(phantom)
            
            # Если текущая вершина - часть сегмента, а следующая - комната
            elif ("segment_" in current or "outdoor_" in current) and next_vertex.startswith("room_"):
                segment_id = current.split("_")[1]
                phantom = f"phantom_room_{next_vertex.split('_')[1]}_segment_{segment_id}"
                if phantom in graph.vertices:
                    optimized.append(phantom)
        
        i += 1

    return optimized

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

    # Инициализация для A*
    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}
    processed = set()

    while open_set:
        current_f, current = heappop(open_set)
        
        if current in processed:
            continue
        
        processed.add(current)
        
        if current == end:
            # Восстанавливаем базовый путь
            path = []
            current_vertex = current
            while current_vertex in came_from:
                path.append(current_vertex)
                current_vertex = came_from[current_vertex]
            path.append(start)
            path.reverse()
            
            # Оптимизируем путь, добавляя фантомные точки
            final_path = optimize_path_with_phantoms(path, graph)
            
            # Вычисляем итоговый вес пути
            weight = 0
            for i in range(len(final_path) - 1):
                v1, v2 = final_path[i], final_path[i + 1]
                for neighbor, w, _ in graph.edges[v1]:
                    if neighbor == v2:
                        weight += w
                        break
            
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        # Обрабатываем соседей
        for neighbor, edge_weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + edge_weight
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor],
                    graph.vertices[end],
                    graph.vertices[current]
                )
                heappush(open_set, (f_score[neighbor], neighbor))

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []