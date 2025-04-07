# app/map/utils/pathfinder.py
import heapq
from math import sqrt


def a_star(graph, start, goals):
    """Находит кратчайший путь, используя A* + ALT"""
    def heuristic(a, b):
        """Эвристика: евклидово расстояние (если нет ориентиров)"""
        if graph.landmarks:
            return max(graph.landmark_heuristic(a, b) for _ in graph.landmarks)
        xa, ya, _ = graph.vertices[a]
        xb, yb, _ = graph.vertices[b]
        return sqrt((xa - xb) ** 2 + (ya - yb) ** 2)

    open_set = []
    heapq.heappush(open_set, (0, start))

    came_from = {}
    g_score = {start: 0}
    f_score = {start: min(heuristic(start, goal) for goal in goals)}
    closed_set = set()

    while open_set:
        f, current = heapq.heappop(open_set)

        if current in closed_set:
            continue

        if current in goals:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            # Группировка пути по этажам
            grouped_path = []
            current_floor = graph.vertices[path[0]][2]
            floor_points = []

            for node in path:
                x, y, floor = graph.vertices[node]
                if floor != current_floor:
                    grouped_path.append({"floor": current_floor, "points": floor_points})
                    floor_points = []
                    current_floor = floor
                floor_points.append({"x": x, "y": y})

            if floor_points:
                grouped_path.append({"floor": current_floor, "points": floor_points})

            return path, g_score[path[-1]]  # Возвращаем простой путь, а не сгруппированный

        closed_set.add(current)

        for neighbor, weight, neighbor_coords in graph.edges.get(current, []):
            if neighbor in closed_set:
                continue

            tentative_g_score = g_score.get(current, float('inf')) + weight

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + min(heuristic(neighbor, goal) for goal in goals)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))

    print(f"[a_star] Путь от {start} до {goals} не найден")
    return None, None