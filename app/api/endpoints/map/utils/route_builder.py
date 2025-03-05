import heapq
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.floor import Floor
from app.map.models.building import Building
from .graph_utils import build_graph
from .node_utils import get_node_description


def build_route(db: Session, start_building: str, start_floor: int, start_room_name: str,
                end_building: str, end_floor: int, end_room_name: str) -> str:
    start_room = db.query(Room).join(Floor).join(Building).filter(
        Building.name == start_building,
        Floor.floor_number == start_floor,
        Room.name == start_room_name
    ).first()

    end_room = db.query(Room).join(Floor).join(Building).filter(
        Building.name == end_building,
        Floor.floor_number == end_floor,
        Room.name == end_room_name
    ).first()

    if not start_room or not end_room:
        return "Одна из комнат не найдена"

    graph, nodes = build_graph(db, start_room, end_room)

    distances = {node: float('infinity') for node in nodes}
    distances[start_room.id] = 0
    previous = {node: (None, None) for node in nodes}
    pq = [(0, start_room.id)]

    while pq:
        current_distance, current_node = heapq.heappop(pq)

        if current_node == end_room.id:
            break

        if current_distance > distances[current_node]:
            continue

        for neighbor, weight, neighbor_type in graph[current_node]:
            distance = current_distance + weight
            if distance < distances[neighbor]:
                distances[neighbor] = distance
                previous[neighbor] = (current_node, neighbor_type)
                heapq.heappush(pq, (distance, neighbor))

    if distances[end_room.id] == float('infinity'):
        return "Маршрут не найден"

    path = []
    current_node = end_room.id
    current_type = "room"
    while current_node is not None:
        path.append((current_node, current_type))
        current_node, current_type = previous[current_node]
    path.reverse()

    route_description = [get_node_description(db, node_id, node_type) for node_id, node_type in path]
    return "\n -> ".join(route_description)