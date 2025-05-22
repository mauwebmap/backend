from heapq import heappush, heappop
from math import sqrt, atan2, degrees
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple, prev: tuple = None, graph: dict = None, connection_type: str = None) -> float:
    x1, y1, floor1 = current
    x2, y2, floor2 = goal
    
    # Base distance using Manhattan distance for better estimates in indoor environments
    dx = abs(x2 - x1)
    dy = abs(y2 - y1)
    base_distance = dx + dy
    
    # Floor difference cost - higher penalty for floor changes
    floor_diff = abs(floor1 - floor2)
    floor_cost = floor_diff * 100  # Increased penalty for floor changes
    
    # Connection type modifiers
    connection_modifier = 0
    if connection_type:
        if connection_type == "лестница":
            connection_modifier = 50 * floor_diff  # Additional cost for stairs
        elif connection_type == "дверь":
            connection_modifier = 10  # Small penalty for doors
    
    # Direction change penalty
    direction_penalty = 0
    if prev and graph:
        px, py, _ = prev
        # Calculate direction changes
        dx1, dy1 = x1 - px, y1 - py
        dx2, dy2 = x2 - x1, y2 - y1
        if dx1 != 0 or dy1 != 0:
            angle = degrees(atan2(dx1 * dy2 - dx2 * dy1, dx1 * dx2 + dy1 * dy2))
            angle = abs(((angle + 180) % 360) - 180)
            if angle > 45:  # Penalize sharp turns
                direction_penalty = angle * 0.5
    
    return base_distance + floor_cost + connection_modifier + direction_penalty

def optimize_path(path: list, graph: Graph) -> list:
    if len(path) <= 2:
        return path

    optimized_path = [path[0]]
    current_floor = graph.vertices[path[0]][2]
    
    for i in range(1, len(path) - 1):
        current = path[i]
        next_vertex = path[i + 1]
        vertex_floor = graph.vertices[current][2]
        
        # Always keep vertices that change floors
        if vertex_floor != current_floor:
            optimized_path.append(current)
            current_floor = vertex_floor
            continue
            
        # Keep connection points and room vertices
        if ("segment_" in current and ("_start" in current or "_end" in current)) or \
           "room_" in current or \
           graph.vertices[current] != graph.vertices[next_vertex]:
            optimized_path.append(current)
    
    optimized_path.append(path[-1])
    return optimized_path

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

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(graph.vertices[start], graph.vertices[end])}
    connection_types = {}  # Track connection types for better heuristics
    processed_vertices = set()

    while open_set:
        current_f, current = heappop(open_set)
        
        if current in processed_vertices:
            continue
        processed_vertices.add(current)

        if current == end:
            path = []
            current_vertex = current
            while current_vertex in came_from:
                path.append(current_vertex)
                current_vertex = came_from[current_vertex]
            path.append(start)
            path.reverse()
            
            # Optimize the final path
            final_path = optimize_path(path, graph)
            weight = g_score[end]
            logger.info(f"Path found: {final_path}, weight={weight}")
            return final_path, weight, graph if return_graph else final_path

        prev_vertex = came_from.get(current, None)
        
        for neighbor, weight, edge_data in graph.edges.get(current, []):
            # Get connection type if available
            connection_type = edge_data.get('type') if isinstance(edge_data, dict) else None
            
            # Calculate tentative g_score
            tentative_g_score = g_score[current] + weight
            
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                connection_types[neighbor] = connection_type
                
                # Calculate f_score with connection type consideration
                f_score[neighbor] = tentative_g_score + heuristic(
                    graph.vertices[neighbor],
                    graph.vertices[end],
                    graph.vertices[current],
                    graph,
                    connection_type
                )
                
                heappush(open_set, (f_score[neighbor], neighbor))
                logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []