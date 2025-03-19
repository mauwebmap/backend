from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.map.crud.segment import (
    get_segment,
    get_segments,
    create_segment_with_connections,
    update_segment,
    delete_segment
)
from app.map.schemas.segment import SegmentCreate, SegmentResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/segments", tags=["Segments"])

@router.get("/", response_model=list[SegmentResponse])
def read_segments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """
    Получить список всех сегментов.
    """
    return get_segments(db, skip=skip, limit=limit)

@router.get("/{segment_id}", response_model=SegmentResponse)
def read_segment(segment_id: int, db: Session = Depends(get_db)):
    """
    Получить информацию о сегменте по его ID.
    """
    segment = get_segment(db, segment_id)
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment

@router.post("/", response_model=SegmentResponse, dependencies=[Depends(admin_required)])
def create_segment_endpoint(segment_data: SegmentCreate, db: Session = Depends(get_db)):
    """
    Создать новый сегмент с возможными соединениями.
    Требуются права администратора.
    """
    try:
        return create_segment_with_connections(db, segment_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании сегмента: {str(e)}"
        )

@router.put("/{segment_id}", response_model=SegmentResponse, dependencies=[Depends(admin_required)])
def update_segment_endpoint(segment_id: int, segment_data: SegmentCreate, db: Session = Depends(get_db)):
    """
    Обновить информацию о сегменте.
    Требуются права администратора.
    """
    try:
        return update_segment(db, segment_id, segment_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обновлении сегмента: {str(e)}"
        )

@router.delete("/{segment_id}", response_model=SegmentResponse, dependencies=[Depends(admin_required)])
def delete_segment_endpoint(segment_id: int, db: Session = Depends(get_db)):
    """
    Удалить сегмент по его ID.
    Требуются права администратора.
    """
    try:
        return delete_segment(db, segment_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при удалении сегмента: {str(e)}"
        )