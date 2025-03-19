from collections import defaultdict
from math import sqrt


class Graph:
    def __init__(self):
        self.edges = defaultdict(list)  # {вершина: [(сосед, вес, координаты)]}
        self.vertices = {}  # {вершина: (x, y, floor)}
        self.landmarks = []  # Список ориентиров

    def add_edge(self, from_vertex, to_vertex, weight, from_coords, to_coords):
        """Добавляет ребро в граф."""
        self.edges[from_vertex].append((to_vertex, weight, to_coords))
        self.edges[to_vertex].append((from_vertex, weight, from_coords))  # Двустороннее соединение
        self.vertices[from_vertex] = from_coords
        self.vertices[to_vertex] = to_coords

    def set_landmarks(self, landmarks):
        """Задает ориентиры (landmarks)"""
        self.landmarks = landmarks

    def landmark_heuristic(self, a, b):
        """Эвристика ALT: максимальное расстояние по ориентирам"""
        return max(abs(self.vertices[a][0] - self.vertices[b][0]),
                   abs(self.vertices[a][1] - self.vertices[b][1]))
