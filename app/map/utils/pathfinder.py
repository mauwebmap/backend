from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple) -> float:
    """
    Эвристическая функция для A*.
    Возвращает примерное расстояние между точками.
    """
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) + abs(floor1 - floor2) * 50

def smooth_path(path: list, graph: Graph) -> list:
    """
    Сглаживает путь, делая повороты более плавными.
    При этом сохраняет все точки из оригинального пути.
    """
    if len(path) <= 2:
        return path

    def get_angle(p1, p2, p3):
        """Вычисляет угол между тремя точками"""
        x1, y1 = p1[0], p1[1]
        x2, y2 = p2[0], p2[1]
        x3, y3 = p3[0], p3[1]
        
        # Векторы
        dx1, dy1 = x2 - x1, y2 - y1
        dx2, dy2 = x3 - x2, y3 - y2
        
        # Угол между векторами
        angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
        return abs(angle)

    def interpolate_point(p1, p2, p3, ratio=0.25):
        """Создает промежуточную точку для сглаживания поворота"""
        x1, y1, f1 = p1
        x2, y2, f2 = p2
        x3, y3, f3 = p3
        
        # Если точки на разных этажах, не интерполируем
        if f1 != f2 or f2 != f3:
            return None
            
        # Создаем точку ближе к центральной точке
        x_new = x2 + (x1 - x2) * ratio
        y_new = y2 + (y1 - y2) * ratio
        return (x_new, y_new, f2)

    smoothed = [path[0]]
    i = 1
    
    while i < len(path) - 1:
        current_vertex = path[i]
        prev_vertex = path[i-1]
        next_vertex = path[i+1]
        
        current_coords = graph.vertices[current_vertex]
        prev_coords = graph.vertices[prev_vertex]
        next_coords = graph.vertices[next_vertex]
        
        # Проверяем угол поворота
        angle = get_angle(prev_coords, current_coords, next_coords)
        
        # Если угол острый, добавляем промежуточные точки
        if angle > 45:
            # Точка перед поворотом
            before_turn = interpolate_point(prev_coords, current_coords, next_coords)
            if before_turn:
                smoothed.append(f"smooth_{i}_before")
                graph.add_vertex(f"smooth_{i}_before", before_turn)
            
            # Добавляем оригинальную точку поворота
            smoothed.append(current_vertex)
            
            # Точка после поворота
            after_turn = interpolate_point(next_coords, current_coords, prev_coords)
            if after_turn:
                smoothed.append(f"smooth_{i}_after")
                graph.add_vertex(f"smooth_{i}_after", after_turn)
        else:
            smoothed.append(current_vertex)
        
        i += 1
    
    smoothed.append(path[-1])
    return smoothed

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
            # Восстанавливаем путь
            path = []
            current_vertex = current
            while current_vertex in came_from:
                path.append(current_vertex)
                current_vertex = came_from[current_vertex]
            path.append(start)
            path.reverse()
            
            # Сглаживаем путь
            final_path = smooth_path(path, graph)
            
            # Вычисляем итоговый вес пути
            weight = 0
            for i in range(len(final_path) - 1):
                v1, v2 = final_path[i], final_path[i + 1]
                # Для сглаженных точек используем евклидово расстояние
                if "smooth_" in v1 or "smooth_" in v2:
                    p1 = graph.vertices[v1]
                    p2 = graph.vertices[v2]
                    weight += sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)
                else:
                    # Для остальных используем вес ребра из графа
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
                    graph.vertices[end]
                )
                heappush(open_set, (f_score[neighbor], neighbor))

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []