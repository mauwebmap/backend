# app/map/utils/graph.py
from collections import defaultdict
from math import sqrt


class Graph:
    def __init__(self):
        self.edges = defaultdict(list)  # {вершина: [(сосед, вес, координаты)]}
        self.vertices = {}              # {вершина: (x, y, floor)}
        self.landmarks = []            # Список ориентиров

    def add_edge(self, from_vertex, to_vertex, weight, from_coords, to_coords, connection_type=None):
        """
        Добавляет ребро в граф.
        Проверяет этажи, но пропускает проверку для соединений типа "stair" и "outdoor".
        """
        try:
            if not isinstance(from_coords, tuple) or not isinstance(to_coords, tuple):
                raise ValueError("Координаты должны быть кортежами")

            # Проверяем этажи, если это не "stair" и не "outdoor"
            if connection_type not in ["stair", "outdoor"] and from_coords[2] != to_coords[2] and from_coords[2] != "outdoor" and to_coords[2] != "outdoor":
                raise ValueError(f"Cannot add edge between vertices on different floors: {from_coords[2]} and {to_coords[2]}")

            # Добавляем ребро в граф
            self.edges[from_vertex].append((to_vertex, weight, to_coords))
            self.edges[to_vertex].append((from_vertex, weight, from_coords))

            # Сохраняем координаты вершин
            self.vertices[from_vertex] = from_coords
            self.vertices[to_vertex] = to_coords

        except Exception as e:
            print(f"[add_edge] Ошибка при добавлении ребра {from_vertex} -> {to_vertex}: {e}")
            raise  # Перебрасываем исключение, чтобы не скрывать ошибки

    def set_landmarks(self, landmarks):
        """Задает ориентиры (landmarks)."""
        try:
            if not isinstance(landmarks, list):
                raise ValueError("Ориентиры должны быть списком")
            self.landmarks = landmarks
        except Exception as e:
            print(f"[set_landmarks] Ошибка при установке ориентиров: {e}")
            raise

    def landmark_heuristic(self, a, b):
        """Эвристика ALT: максимальное расстояние по ориентирам."""
        try:
            a_coords = self.vertices[a]
            b_coords = self.vertices[b]
            return max(abs(a_coords[0] - b_coords[0]), abs(a_coords[1] - b_coords[1]))
        except KeyError as e:
            print(f"[landmark_heuristic] Вершина не найдена: {e}")
            return float('inf')
        except Exception as e:
            print(f"[landmark_heuristic] Ошибка при вычислении эвристики между {a} и {b}: {e}")
            return float('inf')

    def find_path(self, start, end):
        """
        Находит кратчайший путь между start и end с помощью алгоритма Dijkstra.
        """
        if start not in self.vertices or end not in self.vertices:
            print(f"[find_path] Одна из вершин не найдена: start={start}, end={end}")
            return None

        from heapq import heappush, heappop

        # Очередь с приоритетами: (g_score, вершина, путь)
        queue = [(0, start, [start])]
        distances = {start: 0}  # Расстояние от start до текущей вершины
        visited = set()

        while queue:
            dist, current, path = heappop(queue)

            if current in visited:
                continue

            if current == end:
                return path

            visited.add(current)

            for neighbor, weight, _ in self.edges[current]:
                if neighbor in visited:
                    continue

                new_dist = distances[current] + weight

                if neighbor not in distances or new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    new_path = path + [neighbor]
                    heappush(queue, (new_dist, neighbor, new_path))

        print(f"[find_path] Путь от {start} до {end} не найден")
        return None