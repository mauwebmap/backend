from fastapi import Depends, Form, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List
from app.database.database import get_db
from app.map.schemas.room import RoomResponse, RoomCreate, RoomUpdate, Coordinates
from app.map.crud.room import (
    get_rooms,
    get_room,
    create_room,
    update_room,
    delete_room
)
from app.users.dependencies.auth import admin_required
from app.api.endpoints.base import SecureRouter, ProtectedMethodsRoute

router = SecureRouter(
    version=2,
    prefix="/rooms",
    tags=["Rooms"],
    route_class=ProtectedMethodsRoute,
    default_dependencies=[Depends(admin_required)]
)


@router.get("/", response_model=List[RoomResponse])
def read_rooms(
        building_id: Optional[int] = None,
        floor_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
        db: Session = Depends(get_db)
):
    """
    Получить список всех комнат, опционально отфильтрованных по building_id и floor_id.
    """
    return get_rooms(db, skip=skip, limit=limit)  # Фильтрацию можно добавить в CRUD, если нужно


@router.get("/{room_id}", response_model=RoomResponse)
def read_room(
        room_id: int,
        db: Session = Depends(get_db)
):
    """
    Получить информацию о комнате по её ID.
    """
    room = get_room(db, room_id)
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    return room


@router.post("/", response_model=RoomResponse)
async def create_room_endpoint(
        building_id: int = Form(...),
        floor_id: int = Form(...),
        name: str = Form(...),
        cab_id: str = Form(...),
        coordinates: Optional[str] = Form(None),  # Принимаем как строку, парсим в массив
        description: Optional[str] = Form(None),
        svg_file: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):
    """
    Создать новую комнату.
    Требуются права администратора.
    Coordinates принимаются как строка (например, 'x1y1 x2y2 x3y3'), парсятся в массив [[x1, y1], ...].
    """
    try:
        # Парсим coordinates из строки в список координат
        coord_list = []
        if coordinates:
            coords = coordinates.split()
            for coord in coords:
                if len(coord) >= 4 and coord[1].isdigit() and coord[3].isdigit():  # Проверяем минимальный формат x1y1
                    x = float(coord[:2])  # Берем первые два символа как x
                    y = float(coord[2:])  # Остальное как y
                    coord_list.append(Coordinates(x=x, y=y))

        room_data = RoomCreate(
            building_id=building_id,
            floor_id=floor_id,
            name=name,
            cab_id=cab_id,
            coordinates=coord_list if coord_list else None,
            description=description
        )
        return await create_room(db, room_data, svg_file)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{room_id}", response_model=RoomResponse)
async def update_room_endpoint(
        room_id: int,
        building_id: Optional[int] = Form(None),
        floor_id: Optional[int] = Form(None),
        name: Optional[str] = Form(None),
        cab_id: Optional[str] = Form(None),
        coordinates: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        svg_file: Optional[UploadFile] = File(None),
        db: Session = Depends(get_db)
):
    """
    Обновить информацию о комнате.
    Требуются права администратора.
    Coordinates принимаются как строка (например, 'x1y1 x2y2 x3y3'), парсятся в массив [[x1, y1], ...].
    """
    try:
        # Парсим coordinates из строки в список координат
        coord_list = None
        if coordinates:
            coord_list = []
            coords = coordinates.split()
            for coord in coords:
                if len(coord) >= 4 and coord[1].isdigit() and coord[3].isdigit():
                    x = float(coord[:2])
                    y = float(coord[2:])
                    coord_list.append(Coordinates(x=x, y=y))

        room_data = RoomUpdate(
            building_id=building_id,
            floor_id=floor_id,
            name=name,
            cab_id=cab_id,
            coordinates=coord_list if coord_list else None,
            description=description
        )
        updated_room = await update_room(db, room_id, room_data, svg_file)
        if not updated_room:
            raise HTTPException(status_code=404, detail="Room not found")
        return updated_room
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{room_id}", response_model=RoomResponse)
def delete_room_endpoint(
        room_id: int,
        db: Session = Depends(get_db)
):
    """
    Удалить комнату по её ID.
    Требуются права администратора.
    """
    deleted_room = delete_room(db, room_id)
    if not deleted_room:
        raise HTTPException(status_code=404, detail="Room not found")
    return deleted_room