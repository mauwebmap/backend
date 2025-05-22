from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.connection import Connection
from app.map.utils.graph import Graph
from math import sqrt, atan2, degrees
import logging

logger = logging.getLogger(__name__)

VALID_TYPES = {"room", "segment", "outdoor"}

def parse_vertex_id(vertex: str):
    type_, id_ = vertex.split("_", 1)
    if type_ not in VALID_TYPES:
        raise ValueError(f"Invalid vertex type: {type_}")
    return type_, int(id_)

def find_phantom_point(room_coords: tuple, segment_start: tuple, segment_end: tuple, prev_coords: tuple = None) -> tuple:
    rx, ry, rfloor = room_coords
    sx, sy, sfloor = segment_start
    ex, ey, efloor = segment_end

    dx = ex - sx
    dy = ey - sy
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return sx, sy, sfloor

    length = sqrt(length_squared)
    nx, ny = dx / length, dy / length

    dot_product = (rx - sx) * nx + (ry - sy) * ny
    t = max(0, min(1, dot_product / length))

    phantom_x = sx + t * dx
    phantom_y = sy + t * dy
    phantom_floor = rfloor if abs(rfloor - sfloor) <= 1 else sfloor

    if prev_coords:
        px, py, _ = prev_coords
        dx1, dy1 = sx - px, sy - py
        dx2, dy2 = ex - px, ey - py
        dist_to_start = sqrt(dx1 * dx1 + dy1 * dy1)
        dist_to_end = sqrt(dx2 * dx2 + dy2 * dy2)
        if dist_to_start < dist_to_end:
            return sx, sy, sfloor
        return ex, ey, efloor

    return phantom_x, phantom_y, phantom_floor

def add_vertex_to_graph(graph: Graph, db: Session, vertex: str):
    type_, id_ = parse_vertex_id(vertex)
    if type_ == "room":
        room = db.query(Room).filter(Room.id == id_).first()
        if not room:
            logger.error(f"Room {vertex} not found in database")
            raise ValueError(f"Room {vertex} not found")
        graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))
        logger.info(f"Added room vertex: {vertex} -> {(room.cab_x, room.cab_y, room.floor_id)}")
    elif type_ == "segment":
        segment = db.query(Segment).filter(Segment.id == id_).first()
        if not segment:
            logger.error(f"Segment {vertex} not found in database")
            raise ValueError(f"Segment {vertex} not found")
        graph.add_vertex(f"segment_{id_}_start", (segment.start_x, segment.start_y, segment.floor_id))
        graph.add_vertex(f"segment_{id_}_end", (segment.end_x, segment.end_y, segment.floor_id))
        logger.info(f"Added segment vertices: segment_{id_}_start -> {(segment.start_x, segment.start_y, segment.floor_id)}, segment_{id_}_end -> {(segment.end_x, segment.end_y, segment.floor_id)}")
    elif type_ == "outdoor":
        outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == id_).first()
        if not outdoor:
            logger.error(f"Outdoor segment {vertex} not found in database")
            raise ValueError(f"Outdoor segment {vertex} not found")
        graph.add_vertex(f"outdoor_{id_}_start", (outdoor.start_x, outdoor.start_y, 1))
        graph.add_vertex(f"outdoor_{id_}_end", (outdoor.end_x, outdoor.end_y, 1))
        logger.info(f"Added outdoor segment vertices: outdoor_{id_}_start -> {(outdoor.start_x, outdoor.start_y, 1)}, outdoor_{id_}_end -> {(outdoor.end_x, outdoor.end_y, 1)}")

def get_relevant_buildings(db: Session, start: str, end: str) -> set:
    building_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room and room.building_id:
                building_ids.add(room.building_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment and segment.building_id:
                building_ids.add(segment.building_id)
    logger.info(f"Relevant building IDs: {building_ids}")
    return building_ids

def get_relevant_floors(db: Session, start: str, end: str) -> set:
    floor_ids = set()
    for vertex in (start, end):
        type_, id_ = parse_vertex_id(vertex)
        if type_ == "room":
            room = db.query(Room).filter(Room.id == id_).first()
            if room and room.floor_id:
                floor_ids.add(room.floor_id)
        elif type_ == "segment":
            segment = db.query(Segment).filter(Segment.id == id_).first()
            if segment and segment.floor_id:
                floor_ids.add(segment.floor_id)
    floor_ids.add(1)  # Always include ground floor
    logger.info(f"Relevant floor IDs: {floor_ids}")
    return floor_ids

def build_graph(db: Session, start: str, end: str) -> Graph:
    logger.info(f"Starting to build graph for start={start}, end={end}")
    graph = Graph()
    try:
        add_vertex_to_graph(graph, db, start)
        add_vertex_to_graph(graph, db, end)
    except ValueError as e:
        logger.error(f"Failed to add start/end vertices: {e}")
        raise

    building_ids = get_relevant_buildings(db, start, end)
    floor_ids = get_relevant_floors(db, start, end)

    # Add rooms
    rooms = db.query(Room).filter(
        Room.building_id.in_(building_ids),
        Room.floor_id.in_(floor_ids)
    ).all()
    for room in rooms:
        vertex = f"room_{room.id}"
        if vertex not in graph.vertices:
            graph.add_vertex(vertex, (room.cab_x, room.cab_y, room.floor_id))

    # Add segments with their connections
    segments = db.query(Segment).filter(
        Segment.building_id.in_(building_ids),
        Segment.floor_id.in_(floor_ids)
    ).all()
    
    # Create a mapping of segment IDs to their connections
    segment_connections = {}
    connections = db.query(Connection).all()
    for conn in connections:
        if conn.from_segment_id:
            if conn.from_segment_id not in segment_connections:
                segment_connections[conn.from_segment_id] = []
            segment_connections[conn.from_segment_id].append(conn)
        if conn.to_segment_id:
            if conn.to_segment_id not in segment_connections:
                segment_connections[conn.to_segment_id] = []
            segment_connections[conn.to_segment_id].append(conn)

    # Add segments and their edges
    for segment in segments:
        start_vertex = f"segment_{segment.id}_start"
        end_vertex = f"segment_{segment.id}_end"
        
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (segment.start_x, segment.start_y, segment.floor_id))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (segment.end_x, segment.end_y, segment.floor_id))
        
        # Add edge between start and end of segment
        weight = sqrt((segment.end_x - segment.start_x) ** 2 + (segment.end_y - segment.start_y) ** 2)
        edge_data = {"type": "corridor", "segment_id": segment.id}
        graph.add_edge(start_vertex, end_vertex, weight, edge_data)

        # Add connections for this segment
        if segment.id in segment_connections:
            for conn in segment_connections[segment.id]:
                if conn.type == "дверь" and conn.room_id:
                    room_vertex = f"room_{conn.room_id}"
                    if room_vertex in graph.vertices:
                        # Create phantom point for door connection
                        room_coords = graph.vertices[room_vertex]
                        start_coords = graph.vertices[start_vertex]
                        end_coords = graph.vertices[end_vertex]
                        phantom_coords = find_phantom_point(room_coords, start_coords, end_coords)
                        
                        phantom_vertex = f"phantom_room_{conn.room_id}_segment_{segment.id}"
                        graph.add_vertex(phantom_vertex, phantom_coords)
                        
                        # Add edges with door metadata
                        door_data = {"type": "дверь", "connection_id": conn.id}
                        dist_to_phantom = sqrt(
                            (room_coords[0] - phantom_coords[0]) ** 2 + 
                            (room_coords[1] - phantom_coords[1]) ** 2
                        )
                        graph.add_edge(room_vertex, phantom_vertex, dist_to_phantom, door_data)
                        
                        # Connect phantom to segment endpoints
                        for segment_point in [start_vertex, end_vertex]:
                            segment_coords = graph.vertices[segment_point]
                            dist = sqrt(
                                (phantom_coords[0] - segment_coords[0]) ** 2 + 
                                (phantom_coords[1] - segment_coords[1]) ** 2
                            )
                            graph.add_edge(phantom_vertex, segment_point, dist, door_data)

    # Add outdoor segments
    outdoor_segments = db.query(OutdoorSegment).all()
    for outdoor in outdoor_segments:
        start_vertex = f"outdoor_{outdoor.id}_start"
        end_vertex = f"outdoor_{outdoor.id}_end"
        
        if start_vertex not in graph.vertices:
            graph.add_vertex(start_vertex, (outdoor.start_x, outdoor.start_y, 1))
        if end_vertex not in graph.vertices:
            graph.add_vertex(end_vertex, (outdoor.end_x, outdoor.end_y, 1))
        
        weight = outdoor.weight if outdoor.weight else sqrt(
            (outdoor.end_x - outdoor.start_x) ** 2 + 
            (outdoor.end_y - outdoor.start_y) ** 2
        )
        edge_data = {"type": "outdoor", "segment_id": outdoor.id}
        graph.add_edge(start_vertex, end_vertex, weight, edge_data)

    # Process remaining connections (stairs, etc.)
    for conn in connections:
        if conn.type == "лестница" and conn.from_segment_id and conn.to_segment_id:
            from_vertex = f"segment_{conn.from_segment_id}_end"
            to_vertex = f"segment_{conn.to_segment_id}_start"
            
            if from_vertex in graph.vertices and to_vertex in graph.vertices:
                from_coords = graph.vertices[from_vertex]
                to_coords = graph.vertices[to_vertex]
                
                # Calculate 3D distance for stairs
                dx = to_coords[0] - from_coords[0]
                dy = to_coords[1] - from_coords[1]
                dz = abs(to_coords[2] - from_coords[2]) * 50  # Vertical distance penalty
                weight = sqrt(dx * dx + dy * dy + dz * dz)
                
                edge_data = {
                    "type": "лестница",
                    "connection_id": conn.id,
                    "floor_change": to_coords[2] - from_coords[2]
                }
                graph.add_edge(from_vertex, to_vertex, weight, edge_data)

    logger.info(f"Graph built successfully with {len(graph.vertices)} vertices")
    return graph