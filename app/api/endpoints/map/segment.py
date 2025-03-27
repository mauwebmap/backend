from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.segment import (
    get_segment,
    get_segments,
    create_segment_with_connections,
    update_segment,
    delete_segment,
    get_segments_by_floor_and_campus
)
from app.map.schemas.segment import SegmentCreate, SegmentResponse
from app.database.database import get_db
from app.users.dependencies.auth import admin_required
import json
from app.map.schemas.connection import ConnectionCreate

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


@router.get("/campus/{campus_id}/floors/{floor_id}/segments", response_model=list[SegmentResponse])
def read_segments_by_floor_and_campus(campus_id: int, floor_id: int, db: Session = Depends(get_db)):
    """
    Получить все сегменты на указанном этаже в кампусе.
    """
    segments = get_segments_by_floor_and_campus(db, floor_id, campus_id)
    if not segments:
        raise HTTPException(status_code=404, detail="No segments found for the given floor and campus")
    return segments


@router.post("/", response_model=SegmentResponse, dependencies=[Depends(admin_required)])
def create_segment_endpoint(
        request: Request,
        response: Response,
        start_x: float = Form(..., description="Координата X начала сегмента"),
        start_y: float = Form(..., description="Координата Y начала сегмента"),
        end_x: float = Form(..., description="Координата X конца сегмента"),
        end_y: float = Form(..., description="Координата Y конца сегмента"),
        floor_id: int = Form(..., description="ID этажа, к которому относится сегмент"),
        building_id: int = Form(..., description="ID здания, к которому относится сегмент"),
        connections: str = Form('[]',
                                description="Список соединений (JSON-строка, [{'type': str, 'weight': float, 'to_segment_id': int, 'from_floor_id': int, 'to_floor_id': int}]"),
        db: Session = Depends(get_db)
):
    """
    Создать новый сегмент с возможными соединениями (multipart/form-data).
    Требуются права администратора.
    """
    try:
        # Парсим connections из JSON-строки
        connections_list = [ConnectionCreate(**conn) for conn in json.loads(connections)] if connections else []

        # Формируем объект SegmentCreate
        segment_data = SegmentCreate(
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            floor_id=floor_id,
            building_id=building_id,
            connections=connections_list
        )
        return create_segment_with_connections(db, segment_data)
    except ValueError as e:  # Ошибка валидации JSON
        raise HTTPException(status_code=400, detail=f"Неверный формат данных: {str(e)}")
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при создании сегмента: {str(e)}"
        )


@router.put("/{segment_id}", response_model=SegmentResponse, dependencies=[Depends(admin_required)])
def update_segment_endpoint(
        segment_id: int,
        request: Request,
        response: Response,
        start_x: float = Form(None, description="Координата X начала сегмента"),
        start_y: float = Form(None, description="Координата Y начала сегмента"),
        end_x: float = Form(None, description="Координата X конца сегмента"),
        end_y: float = Form(None, description="Координата Y конца сегмента"),
        floor_id: int = Form(None, description="ID этажа, к которому относится сегмент"),
        building_id: int = Form(None, description="ID здания, к которому относится сегмент"),
        connections: str = Form(None,
                                description="Список соединений (JSON-строка, [{'type': str, 'weight': float, 'to_segment_id': int, 'from_floor_id': int, 'to_floor_id': int}]"),
        db: Session = Depends(get_db)
):
    """
    Обновить информацию о сегменте (multipart/form-data).
    Требуются права администратора.
    """
    try:
        # Парсим connections из JSON-строки, если переданы
        connections_list = [ConnectionCreate(**conn) for conn in json.loads(connections)] if connections else None

        # Формируем объект SegmentCreate
        segment_data = SegmentCreate(
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            floor_id=floor_id,
            building_id=building_id,
            connections=connections_list if connections_list is not None else []
        )
        return update_segment(db, segment_id, segment_data)
    except ValueError as e:  # Ошибка валидации JSON
        raise HTTPException(status_code=400, detail=f"Неверный формат данных: {str(e)}")
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