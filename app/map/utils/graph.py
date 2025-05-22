# app/map/utils/graph.py
from typing import Dict, List, Tuple, Union, Any
from math import sqrt

class Graph:
    def __init__(self):
        # Dictionary of vertices: vertex -> (x, y, floor)
        self.vertices: Dict[str, Tuple[float, float, int]] = {}
        # Dictionary of edges: vertex -> [(neighbor, weight, edge_data)]
        # edge_data can contain connection type and other metadata
        self.edges: Dict[str, List[Tuple[str, float, Dict[str, Any]]]] = {}
        # Список ориентиров для ALT (A* с ориентирами), пока не используем
        self.landmarks: List[str] = []

    def add_vertex(self, vertex: str, coords: Tuple[float, float, int]) -> None:
        """Add a vertex to the graph with its coordinates"""
        if vertex not in self.vertices:
            self.vertices[vertex] = coords
            self.edges[vertex] = []

    def add_edge(self, from_vertex: str, to_vertex: str, weight: float, edge_data: Dict[str, Any] = None) -> None:
        """
        Add a bidirectional edge to the graph with optional metadata
        
        Args:
            from_vertex: Source vertex
            to_vertex: Target vertex
            weight: Edge weight (distance/cost)
            edge_data: Optional dictionary containing edge metadata (e.g., connection type)
        """
        if from_vertex not in self.vertices:
            raise ValueError(f"Vertex {from_vertex} not found in graph")
        if to_vertex not in self.vertices:
            raise ValueError(f"Vertex {to_vertex} not found in graph")

        edge_data = edge_data or {}
        
        # Add edge from_vertex -> to_vertex
        self.edges[from_vertex].append((to_vertex, weight, edge_data))
        
        # Add reverse edge to_vertex -> from_vertex with same metadata
        self.edges[to_vertex].append((from_vertex, weight, edge_data))

    def get_edge_data(self, from_vertex: str, to_vertex: str) -> Dict[str, Any]:
        """Get metadata for the edge between two vertices"""
        if from_vertex not in self.edges:
            return {}
            
        for neighbor, _, edge_data in self.edges[from_vertex]:
            if neighbor == to_vertex:
                return edge_data
        return {}

    def get_edge_weight(self, from_vertex: str, to_vertex: str) -> float:
        """Get the weight of the edge between two vertices"""
        if from_vertex not in self.edges:
            return float('inf')
            
        for neighbor, weight, _ in self.edges[from_vertex]:
            if neighbor == to_vertex:
                return weight
        return float('inf')

    def get_neighbors(self, vertex: str) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Get all neighbors of a vertex with their weights and edge data"""
        return self.edges.get(vertex, [])

    def landmark_heuristic(self, a: str, b: str) -> float:
        """Эвристика на основе ориентиров (landmarks) для ALT"""
        if not self.landmarks:
            return 0.0
        # Для простоты возвращаем 0, так как ориентиры пока не используются
        # В будущем можно реализовать полноценную эвристику на основе ориентиров
        return 0.0