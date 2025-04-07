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

    if start not in graph.vertices:
        print(f"[a_star] Start vertex {start} not in graph.vertices")
        return None, None
    if not all(goal in graph.vertices for goal in goals):
        print(f"[a_star] One of the goals {goals} not in graph.vertices")
        return None, None

    open_set = [(0, start)]  # (f_score, vertex)
    came_from = {}
    g_score = {start: 0}
    f_score = {start: min(heuristic(start, goal) for goal in goals)}
    open_set_dict = {start: f_score[start]}  # Для быстрого поиска вершин в open_set

    print(f"[a_star] Starting A* from {start} to {goals}")
    print(f"[a_star] Initial f_score[{start}] = {f_score[start]}")

    while open_set:
        f, current = heapq.heappop(open_set)
        if current not in open_set_dict:
            print(f"[a_star] Skipping vertex {current} (already processed)")
            continue
        del open_set_dict[current]

        print(f"[a_star] Processing vertex: {current}, f_score = {f_score[current]}")

        if current in goals:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            print(f"[a_star] Path found: {path}")
            return path, g_score[path[-1]]

        for neighbor, weight, neighbor_coords in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + min(heuristic(neighbor, goal) for goal in goals)

                if neighbor in open_set_dict:
                    open_set = [(f, v) for f, v in open_set if v != neighbor]
                    heapq.heapify(open_set)
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
                open_set_dict[neighbor] = f_score[neighbor]
                print(f"[a_star] Added/Updated neighbor: {neighbor}, g_score = {g_score[neighbor]}, f_score = {f_score[neighbor]}")

    print(f"[a_star] Путь от {start} до {goals} не найден")
    return None, None