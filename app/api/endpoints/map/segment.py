from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.map.crud.segment import get_segment, get_segments, create_segment, update_segment, delete_segment
from app.map.schemas.segment import Segment, SegmentCreate, SegmentUpdate
from app.database.database import get_db

router = APIRouter(prefix="/segments", tags=["segments"])

@router.get("/{segment_id}", response_model=Segment)
def read_segment(segment_id: int, db: Session = Depends(get_db)):
    segment = get_segment(db, segment_id)
    if not segment: raise HTTPException(status_code=404, detail="Segment not found")
    return segment

@router.get("/", response_model=list[Segment])
def read_segments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return get_segments(db, skip, limit)

@router.post("/", response_model=Segment)
def create_segment_endpoint(segment: SegmentCreate, db: Session = Depends(get_db)):
    return create_segment(db, segment)

@router.put("/{segment_id}", response_model=Segment)
def update_segment_endpoint(segment_id: int, segment: SegmentUpdate, db: Session = Depends(get_db)):
    updated_segment = update_segment(db, segment_id, segment)
    if not updated_segment: raise HTTPException(status_code=404, detail="Segment not found")
    return updated_segment

@router.delete("/{segment_id}", response_model=Segment)
def delete_segment_endpoint(segment_id: int, db: Session = Depends(get_db)):
    deleted_segment = delete_segment(db, segment_id)
    if not deleted_segment: raise HTTPException(status_code=404, detail="Segment not found")
    return deleted_segment