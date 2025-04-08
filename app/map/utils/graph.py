# app/map/utils/graph.py
from typing import Dict, List, Tuple
from math import sqrt

class Graph:
    def __init__(self):
        # Словарь вершин: vertex -> (x, y, floor)
        self.vertices: Dict[str, Tuple[float, float, int]] = {}
        # Словарь рёбер: vertex -> [(neighbor, weight, (x, y, floor))]
        self.edges: Dict[str, List[Tuple[str, float, Tuple[float, float, int]]]] = {}
        # Список ориентиров для ALT (A* с ориентирами), пока не используем
        self.landmarks: List[str] = []

    def add_vertex(self, vertex: str, coords: Tuple[float, float, int]) -> None:
        """Добавление вершины в граф"""
        if vertex not in self.vertices:
            self.vertices[vertex] = coords
            self.edges[vertex] = []

    def add_edge(self, from_vertex: str, to_vertex: str, weight: float) -> None:
        """Добавление ребра в граф (двунаправленное)"""
        if from_vertex not in self.vertices:
            raise ValueError(f"Вершина {from_vertex} не найдена в графе")
        if to_vertex not in self.vertices:
            raise ValueError(f"Вершина {to_vertex} не найдена в графе")
        # Добавляем ребро from_vertex -> to_vertex
        self.edges[from_vertex].append((to_vertex, weight, self.vertices[to_vertex]))
        # Добавляем обратное ребро to_vertex -> from_vertex
        self.edges[to_vertex].append((from_vertex, weight, self.vertices[from_vertex]))

    def landmark_heuristic(self, a: str, b: str) -> float:
        """Эвристика на основе ориентиров (landmarks) для ALT"""
        if not self.landmarks:
            return 0.0
        # Для простоты возвращаем 0, так как ориентиры пока не используются
        # В будущем можно реализовать полноценную эвристику на основе ориентиров
        return 0.0