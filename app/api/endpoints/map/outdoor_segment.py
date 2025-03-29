from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.outdoor_segment import (
    get_outdoor_segment,
    get_outdoor_segments,
    get_outdoor_segments_by_campus,
    create_outdoor_segment,
    update_outdoor_segment,
    delete_outdoor_segment
)
from app.map.schemas.outdoor_segment import OutdoorSegmentCreate, OutdoorSegmentUpdate, OutdoorSegment as OutdoorSegmentResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/outdoor_segments", tags=["Outdoor Segments"])

@router.get("/", response_model=list[OutdoorSegmentResponse])
def read_outdoor_segments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получить список всех уличных сегментов. Без авторизации."""
    return get_outdoor_segments(db, skip=skip, limit=limit)

@router.get("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse)
def read_outdoor_segment(outdoor_segment_id: int, db: Session = Depends(get_db)):
    """Получить информацию об уличном сегменте по ID. Без авторизации."""
    outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    return outdoor_segment

@router.get("/campus/{campus_id}", response_model=list[OutdoorSegmentResponse])
def read_outdoor_segments_by_campus(campus_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Получить все уличные сегменты в указанном кампусе. Без авторизации."""
    return get_outdoor_segments_by_campus(db, campus_id, skip=skip, limit=limit)

@router.post("/", response_model=OutdoorSegmentResponse)
def create_outdoor_segment_endpoint(
    segment_data: OutdoorSegmentCreate,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Создать новый уличный сегмент (application/json). Требуются права администратора."""
    try:
        result = create_outdoor_segment(db, segment_data)
        if new_access_token:
            response.headers["X-New-Access-Token"] = new_access_token
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании уличного сегмента: {str(e)}"
        )

@router.put("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse)
def update_outdoor_segment_endpoint(
    outdoor_segment_id: int,
    segment_data: OutdoorSegmentUpdate,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Обновить информацию об уличном сегменте (application/json). Требуются права администратора."""
    updated_segment = update_outdoor_segment(db, outdoor_segment_id, segment_data)
    if not updated_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    if new_access_token:
        response.headers["X-New-Access-Token"] = new_access_token
    return updated_segment

@router.delete("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse)
def delete_outdoor_segment_endpoint(
    outdoor_segment_id: int,
    db: Session = Depends(get_db),
    request: Request = None,
    response: Response = None,
    new_access_token: Optional[str] = Depends(admin_required)
):
    """Удалить уличный сегмент. Требуются права администратора."""
    deleted_segment = delete_outdoor_segment(db, outdoor_segment_id)
    if not deleted_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    if new_access_token:
        response.headers["X-New-Access-Token"] = new_access_token
    return deleted_segment