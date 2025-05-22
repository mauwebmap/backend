from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    
    # Basic Euclidean distance
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    
    # Floor difference penalty
    floor_diff = abs(floor1 - floor2)
    floor_cost = floor_diff * 50  # Penalty for changing floors
    
    # Direction change penalty
    direction_penalty = 0
    if prev:
        px, py, _ = prev
        dx1, dy1 = x1 - px, y1 - py
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle > 90:  # Penalize sharp turns
                direction_penalty = angle * 0.5
    
    return distance + floor_cost + direction_penalty

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

    # Initialize data structures for A* search
    open_set = [(0, start)]  # Priority queue of (f_score, vertex)
    came_from = {}  # Keep track of the path
    g_score = {start: 0}  # Cost from start to vertex
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}  # Estimated total cost
    processed = set()  # Keep track of processed vertices

    while open_set:
        current_f, current = heappop(open_set)
        
        if current in processed:
            continue
        
        processed.add(current)
        
        # Check if we've reached the goal
        if current == end:
            # Reconstruct path
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            
            # Add intermediate points for segments
            final_path = []
            for i, vertex in enumerate(path):
                final_path.append(vertex)
                if i < len(path) - 1:
                    # If current vertex is a segment endpoint, add the other endpoint
                    if "_start" in vertex:
                        opposite = vertex.replace("_start", "_end")
                        if opposite in graph.vertices:
                            final_path.append(opposite)
                    elif "_end" in vertex:
                        opposite = vertex.replace("_end", "_start")
                        if opposite in graph.vertices:
                            final_path.append(opposite)
            
            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        # Process neighbors
        for neighbor, edge_weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + edge_weight
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                # This path is better than any previous one
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor],
                    graph.vertices[end],
                    graph.vertices[current]
                )
                heappush(open_set, (f_score[neighbor], neighbor))

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []