from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.outdoor_segment import get_outdoor_segment, get_outdoor_segments, create_outdoor_segment, update_outdoor_segment, delete_outdoor_segment
from app.map.schemas.outdoor_segment import OutdoorSegment, OutdoorSegmentCreate, OutdoorSegmentUpdate
from app.database.database import get_db

router = APIRouter(prefix="/outdoor_segments", tags=["outdoor_segments"])

@router.get("/{outdoor_segment_id}", response_model=OutdoorSegment)
def read_outdoor_segment(outdoor_segment_id: int, db: Session = Depends(get_db)):
    outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not outdoor_segment: raise HTTPException(status_code=404, detail="OutdoorSegment not found")
    return outdoor_segment

@router.get("/", response_model=list[OutdoorSegment])
def read_outdoor_segments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_outdoor_segments(db, skip, limit)

@router.post("/", response_model=OutdoorSegment)
def create_outdoor_segment_endpoint(outdoor_segment: OutdoorSegmentCreate, db: Session = Depends(get_db)):
    return create_outdoor_segment(db, outdoor_segment)

@router.put("/{outdoor_segment_id}", response_model=OutdoorSegment)
def update_outdoor_segment_endpoint(outdoor_segment_id: int, outdoor_segment: OutdoorSegmentUpdate, db: Session = Depends(get_db)):
    updated_outdoor_segment = update_outdoor_segment(db, outdoor_segment_id, outdoor_segment)
    if not updated_outdoor_segment: raise HTTPException(status_code=404, detail="OutdoorSegment not found")
    return updated_outdoor_segment

@router.delete("/{outdoor_segment_id}", response_model=OutdoorSegment)
def delete_outdoor_segment_endpoint(outdoor_segment_id: int, db: Session = Depends(get_db)):
    deleted_outdoor_segment = delete_outdoor_segment(db, outdoor_segment_id)
    if not deleted_outdoor_segment: raise HTTPException(status_code=404, detail="OutdoorSegment not found")
    return deleted_outdoor_segment