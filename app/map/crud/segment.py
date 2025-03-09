from sqlalchemy.orm import Session
from app.map.models.segment import Segment
from app.map.schemas.segment import SegmentCreate, SegmentUpdate

def get_segment(db: Session, segment_id: int):
    return db.query(Segment).filter(Segment.id == segment_id).first()

def get_segments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Segment).offset(skip).limit(limit).all()

def create_segment(db: Session, segment: SegmentCreate):
    db_segment = Segment(**segment.dict())
    db.add(db_segment)
    db.commit()
    db.refresh(db_segment)
    return db_segment

def update_segment(db: Session, segment_id: int, segment: SegmentUpdate):
    db_segment = get_segment(db, segment_id)
    if not db_segment:
        return None
    update_data = segment.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_segment, key, value)
    db.commit()
    db.refresh(db_segment)
    return db_segment

def delete_segment(db: Session, segment_id: int):
    db_segment = get_segment(db, segment_id)
    if not db_segment:
        return None
    db.delete(db_segment)
    db.commit()
    return db_segment