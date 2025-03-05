from sqlalchemy.orm import Session
from app.map.models.room import Room
from app.map.models.floor import Floor
from app.map.models.building import Building
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from typing import Optional, Any

def get_node_by_id(db: Session, node_id: int, node_type: str) -> Optional[Any]:
    if node_type == "room":
        return db.query(Room).filter(Room.id == node_id).first()
    elif node_type == "segment":
        return db.query(Segment).filter(Segment.id == node_id).first()
    elif node_type == "outdoor":
        return db.query(OutdoorSegment).filter(OutdoorSegment.id == node_id).first()
    elif node_type == "building":
        return db.query(Building).filter(Building.id == node_id).first()
    return None

def get_node_description(db: Session, node_id: int, node_type: str) -> str:
    node = get_node_by_id(db, node_id, node_type)
    if not node:
        return f"Неизвестный узел {node_id}"

    if node_type == "room":
        floor = db.query(Floor).filter(Floor.id == node.floor_id).first()
        building = db.query(Building).filter(Building.id == node.building_id).first()
        return f"Комната {node.name} (Этаж {floor.floor_number}, Здание {building.name})"
    elif node_type == "segment":
        building = db.query(Building).filter(Building.id == node.building_id).first()
        return f"Сегмент {node.type} (Этаж {node.floor}, Здание {building.name})"
    elif node_type == "outdoor":
        start_b = db.query(Building).filter(Building.id == node.start_building_id).first()
        end_b = db.query(Building).filter(Building.id == node.end_building_id).first()
        return f"Улица от {start_b.name} до {end_b.name}"
    elif node_type == "building":
        return f"Вход/выход в здание {node.name}"
    return f"{node_type} {node_id}"