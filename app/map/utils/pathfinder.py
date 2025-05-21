from heapq import heappush, heappop
from math import sqrt
from .graph import Graph

def heuristic(a: tuple, b: tuple) -> float:
    # Эвклидово расстояние между точками с учетом этажей
    x1, y1, floor1 = a
    x2, y2, floor2 = b
    floor_cost = abs(floor1 - floor2) * 100  # Штраф за смену этажа
    return sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) + floor_cost

def find_path(db, start: str, end: str, return_graph=False):
    graph = build_graph(db, start, end)
    if start not in graph.vertices or end not in graph.vertices:
        return [], float('inf'), graph if return_graph else []

    open_set = [(0, start)]  # (f_score, vertex)
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}

    while open_set:
        current_f, current = heappop(open_set)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            weight = g_score[end]
            return path, weight, graph if return_graph else path

        for neighbor, weight in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight

            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(graph.vertices[neighbor], graph.vertices[end])
                heappush(open_set, (f_score[neighbor], neighbor))

    return [], float('inf'), graph if return_graph else []