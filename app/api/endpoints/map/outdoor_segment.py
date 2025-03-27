from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Form, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.outdoor_segment import (
    get_outdoor_segment,
    get_outdoor_segments,
    get_outdoor_segments_by_campus,
    create_outdoor_segment,
    update_outdoor_segment,
    delete_outdoor_segment
)
from app.map.crud.connection import create_connection
from app.map.schemas.outdoor_segment import OutdoorSegment as OutdoorSegmentResponse, OutdoorSegmentCreate, OutdoorSegmentUpdate
from app.map.schemas.connection import ConnectionCreate
from app.database.database import get_db
from app.users.dependencies.auth import admin_required
import json

router = APIRouter(prefix="/outdoor_segments", tags=["Outdoor Segments"])


@router.get("/", response_model=List[OutdoorSegmentResponse])
def read_outdoor_segments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех уличных сегментов. Без авторизации."""
    return get_outdoor_segments(db, skip=skip, limit=limit)


@router.get("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse)
def read_outdoor_segment(
    outdoor_segment_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию об уличном сегменте по ID. Без авторизации."""
    outdoor_segment = get_outdoor_segment(db, outdoor_segment_id)
    if not outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    return outdoor_segment


@router.get("/campus/{campus_id}", response_model=List[OutdoorSegmentResponse])
def read_outdoor_segments_by_campus(
    campus_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить все уличные сегменты в указанном кампусе. Без авторизации."""
    return get_outdoor_segments_by_campus(db, campus_id, skip=skip, limit=limit)


@router.post("/", response_model=OutdoorSegmentResponse, dependencies=[Depends(admin_required)])
def create_outdoor_segment_endpoint(
    request: Request,
    response: Response,
    type: str = Form(..., description="Тип уличного сегмента (например, 'path', 'road')"),
    campus_id: int = Form(..., description="ID кампуса, к которому относится сегмент"),
    start_building_id: Optional[int] = Form(None, description="ID начального здания"),
    end_building_id: Optional[int] = Form(None, description="ID конечного здания"),
    start_x: float = Form(..., description="Координата X начальной точки"),
    start_y: float = Form(..., description="Координата Y начальной точки"),
    end_x: float = Form(..., description="Координата X конечной точки"),
    end_y: float = Form(..., description="Координата Y конечной точки"),
    weight: int = Form(..., description="Вес сегмента (например, длина или время прохождения)"),
    connections: Optional[str] = Form(None, description="Список соединений (JSON-строка, [{'type': str, 'weight': float, 'to_outdoor_id': int, ...}])"),
    db: Session = Depends(get_db)
):
    """Создать новый уличный сегмент и опционально связать его с другими объектами. Требуются права администратора."""
    try:
        # Формируем данные уличного сегмента
        outdoor_segment_data = OutdoorSegmentCreate(
            type=type,
            campus_id=campus_id,
            start_building_id=start_building_id,
            end_building_id=end_building_id,
            start_x=start_x,
            start_y=start_y,
            end_x=end_x,
            end_y=end_y,
            weight=weight
        )

        # Создаем уличный сегмент
        outdoor_segment = create_outdoor_segment(db, outdoor_segment_data)

        # Если переданы соединения, создаем их
        if connections:
            connection_list = json.loads(connections)
            for conn in connection_list:
                conn["from_outdoor_id"] = outdoor_segment.id
                create_connection(db, ConnectionCreate(**conn))
            db.commit()

        db.refresh(outdoor_segment)
        return outdoor_segment
    except HTTPException as e:
        raise e
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании уличного сегмента: {str(e)}")


@router.put("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse, dependencies=[Depends(admin_required)])
def update_outdoor_segment_endpoint(
    outdoor_segment_id: int,
    request: Request,
    response: Response,
    type: Optional[str] = Form(None, description="Новый тип уличного сегмента"),
    campus_id: Optional[int] = Form(None, description="Новый ID кампуса"),
    start_building_id: Optional[int] = Form(None, description="Новый ID начального здания"),
    end_building_id: Optional[int] = Form(None, description="Новый ID конечного здания"),
    start_x: Optional[float] = Form(None, description="Новая координата X начальной точки"),
    start_y: Optional[float] = Form(None, description="Новая координата Y начальной точки"),
    end_x: Optional[float] = Form(None, description="Новая координата X конечной точки"),
    end_y: Optional[float] = Form(None, description="Новая координата Y конечной точки"),
    weight: Optional[int] = Form(None, description="Новый вес сегмента"),
    db: Session = Depends(get_db)
):
    """Обновить информацию об уличном сегменте. Требуются права администратора."""
    update_data = {
        key: value for key, value in {
            "type": type,
            "campus_id": campus_id,
            "start_building_id": start_building_id,
            "end_building_id": end_building_id,
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "weight": weight
        }.items() if value is not None
    }
    updated_outdoor_segment = update_outdoor_segment(db, outdoor_segment_id, OutdoorSegmentUpdate(**update_data))
    if not updated_outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    return updated_outdoor_segment


@router.delete("/{outdoor_segment_id}", response_model=OutdoorSegmentResponse, dependencies=[Depends(admin_required)])
def delete_outdoor_segment_endpoint(
    outdoor_segment_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Удалить уличный сегмент. Требуются права администратора."""
    deleted_outdoor_segment = delete_outdoor_segment(db, outdoor_segment_id)
    if not deleted_outdoor_segment:
        raise HTTPException(status_code=404, detail="Outdoor segment not found")
    return deleted_outdoor_segment