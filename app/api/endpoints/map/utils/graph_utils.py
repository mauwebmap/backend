from collections import defaultdict
from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.building import Building
from typing import Dict, List, Tuple, Set

def build_graph(db: Session, start_room: Room, end_room: Room) -> Tuple[Dict[int, List[Tuple[int, int, str]]], Set[int]]:
    graph = defaultdict(list)
    nodes = set()

    def add_edge(from_id: int, to_id: int, weight: int, to_type: str):
        graph[from_id].append((to_id, weight, to_type))
        nodes.add(from_id)
        nodes.add(to_id)

    for room in [start_room, end_room]:
        for conn in room.connections:
            add_edge(room.id, conn.segment_id, conn.weight, "segment")
            add_edge(conn.segment_id, room.id, conn.weight, "room")

    segments = db.query(Segment).join(Building).filter(
        Building.id.in_([start_room.building_id, end_room.building_id])
    ).all()
    for segment in segments:
        for conn in segment.connections:
            if conn.room_id:
                add_edge(segment.id, conn.room_id, conn.weight, "room")

    outdoor_segments = db.query(OutdoorSegment).filter(
        OutdoorSegment.start_building_id.in_([start_room.building_id, end_room.building_id]) |
        OutdoorSegment.end_building_id.in_([start_room.building_id, end_room.building_id])
    ).all()
    for outdoor in outdoor_segments:
        add_edge(outdoor.start_building_id, outdoor.id, outdoor.weight, "outdoor")
        add_edge(outdoor.id, outdoor.end_building_id, outdoor.weight, "building")

    return graph, nodes