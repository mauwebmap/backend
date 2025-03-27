from sqlalchemy.orm import Session
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.schemas.outdoor_segment import OutdoorSegmentCreate, OutdoorSegmentUpdate
from fastapi import HTTPException

def get_outdoor_segment(db: Session, outdoor_segment_id: int):
    return db.query(OutdoorSegment).filter(OutdoorSegment.id == outdoor_segment_id).first()

def get_outdoor_segments(db: Session, skip: int = 0, limit: int = 100):
    return db.query(OutdoorSegment).offset(skip).limit(limit).all()

def get_outdoor_segments_by_campus(db: Session, campus_id: int, skip: int = 0, limit: int = 100):
    outdoor_segments = (
        db.query(OutdoorSegment)
        .filter(OutdoorSegment.campus_id == campus_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    if not outdoor_segments:
        raise HTTPException(status_code=404, detail="No outdoor segments found for the given campus")
    return outdoor_segments

def create_outdoor_segment(db: Session, outdoor_segment: OutdoorSegmentCreate):
    db_outdoor_segment = OutdoorSegment(**outdoor_segment.dict())
    db.add(db_outdoor_segment)
    db.commit()
    db.refresh(db_outdoor_segment)
    return db_outdoor_segment

def update_outdoor_segment(db: Session, outdoor_segment_id: int, outdoor_segment: OutdoorSegmentUpdate):
    db_outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not db_outdoor_segment:
        return None
    update_data = outdoor_segment.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_outdoor_segment, key, value)
    db.commit()
    db.refresh(db_outdoor_segment)
    return db_outdoor_segment

def delete_outdoor_segment(db: Session, outdoor_segment_id: int):
    db_outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not db_outdoor_segment:
        return None
    db.delete(db_outdoor_segment)
    db.commit()
    return db_outdoor_segment