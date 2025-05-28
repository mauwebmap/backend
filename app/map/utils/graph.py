# app/map/utils/graph.py
from typing import Dict, List, Tuple, Union, Any
from math import sqrt

class Graph:
    def __init__(self):
        self.vertices: Dict[str, dict] = {}
        self.edges: Dict[str, List[Tuple[str, float, Dict[str, Any]]]] = {}
        self.landmarks: List[str] = []

    def add_vertex(self, vertex: str, data: dict) -> None:
        if vertex not in self.vertices:
            self.vertices[vertex] = data
            self.edges[vertex] = []

    def add_edge(self, from_vertex: str, to_vertex: str, weight: float, edge_data: Dict[str, Any] = None) -> None:
        if from_vertex not in self.vertices:
            raise ValueError(f"Vertex {from_vertex} not found in graph")
        if to_vertex not in self.vertices:
            raise ValueError(f"Vertex {to_vertex} not found in graph")

        edge_data = edge_data or {}
        self.edges[from_vertex].append((to_vertex, weight, edge_data))
        self.edges[to_vertex].append((from_vertex, weight, edge_data))

    def get_edge_data(self, from_vertex: str, to_vertex: str) -> Dict[str, Any]:
        if from_vertex not in self.edges:
            return {}
        for neighbor, _, edge_data in self.edges[from_vertex]:
            if neighbor == to_vertex:
                return edge_data
        return {}

    def get_edge_weight(self, from_vertex: str, to_vertex: str) -> float:
        if from_vertex not in self.edges:
            return float('inf')
        for neighbor, weight, _ in self.edges[from_vertex]:
            if neighbor == to_vertex:
                return weight
        return float('inf')

    def get_neighbors(self, vertex: str) -> List[Tuple[str, float, Dict[str, Any]]]:
        return self.edges.get(vertex, [])

    def heuristic(self, vertex1: str, vertex2: str) -> float:
        coords1 = self.get_vertex_data(vertex1)["coords"]
        coords2 = self.get_vertex_data(vertex2)["coords"]
        floor_diff = abs(coords1[2] - coords2[2]) * 10
        distance_2d = sqrt((coords1[0] - coords2[0]) ** 2 + (coords1[1] - coords2[1]) ** 2)
        return distance_2d + floor_diff

    def landmark_heuristic(self, a: str, b: str) -> float:
        if not self.landmarks:
            return 0.0
        return 0.0

    def get_vertex_data(self, vertex: str) -> dict:
        return self.vertices.get(vertex, {"coords": (0, 0, 0), "building_id": None})