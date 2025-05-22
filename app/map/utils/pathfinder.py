# backend/app/map/utils/pathfinder.py
from heapq import heappush, heappop
from math import sqrt
from .graph import Graph
from .builder import build_graph
import logging

logger = logging.getLogger(__name__)

def heuristic(current: tuple, goal: tuple) -> float:
    x1, y1, floor_id1 = current
    x2, y2, floor_id2 = goal
    distance = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
    floor_cost = abs(floor_id1 - floor_id2) * 30 if floor_id1 != floor_id2 else 0
    return distance + floor_cost

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

    # Извлекаем данные о стартовой и конечной точках
    start_data = graph.get_vertex_data(start)
    end_data = graph.get_vertex_data(end)
    start_building = start_data["building_id"]
    end_building = end_data["building_id"]
    start_coords = start_data["coords"]
    end_coords = end_data["coords"]

    open_set = [(0, start)]
    came_from = {}
    g_score = {start: 0}
    f_score = {start: heuristic(start_coords, end_coords)}
    processed_vertices = set()

    logger.info(f"Starting A* search with initial open_set: {open_set}")
    while open_set:
        current_f, current = heappop(open_set)
        logger.debug(f"Processing vertex: {current}, f_score={current_f}")

        if current in processed_vertices:
            continue
        processed_vertices.add(current)

        if current == end:
            path = []
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            path.reverse()

            weight = g_score[end]
            logger.info(f"Path found: {path}, weight={weight}")

            # Формируем маршрут с этажами
            route = []
            current_floor = None
            points = []
            for i, vertex in enumerate(path):
                vertex_data = graph.get_vertex_data(vertex)
                floor_id = vertex_data["coords"][2]
                floor_number = 1 if vertex_data["building_id"] is None else floor_id  # outdoor = 1, else floor_id

                if i == 0:
                    current_floor = floor_number
                    points.append({"x": vertex_data["coords"][0], "y": vertex_data["coords"][1], "vertex": vertex})
                elif floor_number != current_floor or i == len(path) - 1:
                    if points:
                        route.append({"floor": current_floor, "points": points})
                    current_floor = floor_number
                    points = [{"x": vertex_data["coords"][0], "y": vertex_data["coords"][1], "vertex": vertex}]
                else:
                    points.append({"x": vertex_data["coords"][0], "y": vertex_data["coords"][1], "vertex": vertex})

            if points:
                route.append({"floor": current_floor, "points": points})

            # Исключаем outdoor, если здания одинаковые
            if start_building == end_building and start_building is not None:
                route = [segment for segment in route if not any("outdoor" in p["vertex"] for p in segment["points"])]

            logger.info(f"Generated route structure: {route}")  # Добавляем отладочный лог
            logger.info(f"Pathfinding completed: path={path}, weight={weight}")
            return path, weight, graph if return_graph else route

        try:
            for neighbor, weight, _ in graph.get_neighbors(current):
                neighbor_data = graph.get_vertex_data(neighbor)
                # Пропускаем outdoor вершины, если здания одинаковые
                if start_building == end_building and start_building is not None and neighbor_data["building_id"] is None:
                    continue

                tentative_g_score = g_score[current] + weight
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = tentative_g_score + heuristic(neighbor_data["coords"], end_coords)
                    heappush(open_set, (f_score[neighbor], neighbor))
                    logger.debug(f"Added to open_set: {neighbor}, f_score={f_score[neighbor]}")
        except Exception as e:
            logger.error(f"Error processing neighbor for vertex {current}: {e}")
            continue

    logger.warning(f"No path found from {start} to {end}")
    return [], float('inf'), graph if return_graph else []