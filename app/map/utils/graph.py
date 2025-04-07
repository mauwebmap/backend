from collections import defaultdict
from math import sqrt

class Graph:
    def __init__(self):
        self.edges = defaultdict(list)  # {вершина: [(сосед, вес, координаты)]}
        self.vertices = {}              # {вершина: (x, y, floor)}
        self.landmarks = []            # Список ориентиров

    def add_edge(self, from_vertex, to_vertex, weight, from_coords, to_coords):
        """Добавляет ребро в граф."""
        try:
            if not isinstance(from_coords, tuple) or not isinstance(to_coords, tuple):
                raise ValueError("Координаты должны быть кортежами")

            self.edges[from_vertex].append((to_vertex, weight, to_coords))
            self.edges[to_vertex].append((from_vertex, weight, from_coords))

            self.vertices[from_vertex] = from_coords
            self.vertices[to_vertex] = to_coords
        except Exception as e:
            print(f"[add_edge] Ошибка при добавлении ребра {from_vertex} -> {to_vertex}: {e}")

    def set_landmarks(self, landmarks):
        """Задает ориентиры (landmarks)"""
        try:
            if not isinstance(landmarks, list):
                raise ValueError("Ориентиры должны быть списком")
            self.landmarks = landmarks
        except Exception as e:
            print(f"[set_landmarks] Ошибка при установке ориентиров: {e}")

    def landmark_heuristic(self, a, b):
        """Эвристика ALT: максимальное расстояние по ориентирам"""
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
