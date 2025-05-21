from math import sqrt
import logging
from sqlalchemy.orm import Session
from app.map.utils.builder import build_graph, Graph
import heapq

logger = logging.getLogger(__name__)

def a_star(graph: Graph, start: str, goals: list) -> tuple:
    def heuristic(a, b):
        xa, ya, _ = graph.vertices[a]
        xb, yb, _ = graph.vertices[b]
        return sqrt((xa - xb) ** 2 + (ya - yb) ** 2)

    if start not in graph.vertices:
        logger.error(f"Start vertex {start} not in graph")
        return None, None
    if not all(goal in graph.vertices for goal in goals):
        logger.error(f"One of the goals {goals} not in graph")
        return None, None

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start, min(goals, key=lambda g: heuristic(start, g)))}

    while open_set:
        f, current = heapq.heappop(open_set)
        if current in goals:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()
            logger.debug(f"Path found: {path}, weight={g_score[path[-1]]}")
            return path, g_score[path[-1]]

        for neighbor, weight, _ in graph.edges.get(current, []):
            tentative_g_score = g_score[current] + weight
            if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g_score
                f_score[neighbor] = tentative_g_score + heuristic(neighbor, min(goals, key=lambda g: heuristic(neighbor, g)))
                heapq.heappush(open_set, (f_score[neighbor], neighbor))
            logger.debug(f"Checked neighbor {neighbor}, tentative_g_score={tentative_g_score}, g_score={g_score.get(neighbor)}")

    logger.warning(f"Path from {start} to {goals} not found")
    return None, None

def find_path(db: Session, start: str, end: str, return_graph: bool = False) -> tuple:
    graph = build_graph(db, start, end)
    goals = [end] if isinstance(end, str) else end
    path, weight = a_star(graph, start, goals)
    if path is None:
        logger.warning(f"No path found from {start} to {end}")
    else:
        logger.info(f"Path found from {start} to {end}, weight={weight}")
    return (path, weight, graph) if return_graph else (path, weight)