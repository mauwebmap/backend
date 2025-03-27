import logging

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,  # Уровень логирования (DEBUG включает все сообщения)
    filename="app.log",   # Имя файла для записи логов
    filemode="a",         # Режим "a" — добавлять в конец файла (не перезаписывать)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"  # Формат записи
)
logger = logging.getLogger(__name__)  # Логгер для текущего модуля


from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, Form, File, Request, Response
from sqlalchemy.orm import Session
from app.map.crud.floor import (
    get_floor,
    get_all_floors,
    create_floor_with_connections,
    update_floor,
    delete_floor,
    get_unique_floor_numbers_by_campus,
    get_floors_by_campus_and_number
)
from app.map.schemas.floor import FloorResponse, FloorNumbersResponse, FloorCreate, FloorUpdate
from app.database.database import get_db
from app.users.dependencies.auth import admin_required

router = APIRouter(prefix="/floors", tags=["Floors"])


@router.get("/", response_model=List[FloorResponse])
def read_floors(
    building_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Получить список всех этажей, опционально отфильтрованных по building_id. Без авторизации."""
    return get_all_floors(db, building_id=building_id, skip=skip, limit=limit)


@router.get("/{floor_id}", response_model=FloorResponse)
def read_floor(
    floor_id: int,
    db: Session = Depends(get_db)
):
    """Получить информацию об этаже по ID. Без авторизации."""
    floor = get_floor(db, floor_id)
    if not floor:
        raise HTTPException(status_code=404, detail="Floor not found")
    return floor


@router.get("/campus/{campus_id}/floor-numbers", response_model=FloorNumbersResponse)
def read_unique_floor_numbers_by_campus(
    campus_id: int,
    db: Session = Depends(get_db)
):
    """Получить уникальные номера этажей в кампусе. Без авторизации."""
    floor_numbers = get_unique_floor_numbers_by_campus(db, campus_id)
    if not floor_numbers:
        raise HTTPException(status_code=404, detail="No floors found for this campus")
    return {"floor_numbers": floor_numbers}


@router.get("/campus/{campus_id}/floors/{floor_number}", response_model=List[FloorResponse])
def read_floors_by_campus_and_number(
    campus_id: int,
    floor_number: int,
    db: Session = Depends(get_db)
):
    """Получить этажи по кампусу и номеру. Без авторизации."""
    floors = get_floors_by_campus_and_number(db, campus_id, floor_number)
    if not floors:
        raise HTTPException(status_code=404, detail="No floors found for the given campus and number")
    return floors


@router.post("/", response_model=FloorResponse, dependencies=[Depends(admin_required)])
async def create_floor_endpoint(
    request: Request,
    response: Response,
    building_id: int = Form(...),
    floor_number: int = Form(...),
    description: Optional[str] = Form(None),
    svg_file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    logger.debug(f"Received: building_id={building_id}, floor_number={floor_number}, description={description}, svg_file={svg_file.filename if svg_file else None}")
    try:
        floor_data = FloorCreate(
            building_id=building_id,
            floor_number=floor_number,
            description=description,
            connections=[]
        )
        logger.debug(f"Floor data: {floor_data.dict()}")
        result = await create_floor_with_connections(db=db, floor_data=floor_data, svg_file=svg_file)
        logger.debug(f"Created floor: {result.id}")
        return result
    except HTTPException as e:
        logger.error(f"HTTP Exception: {str(e)}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при создании этажа: {str(e)}")

# Остальные эндпоинты остаются без изменений, если не нужно логирование в них

@router.put("/{floor_id}", response_model=FloorResponse, dependencies=[Depends(admin_required)])
async def update_floor_endpoint(
    floor_id: int,
    request: Request,
    response: Response,
    building_id: Optional[int] = Form(None, description="Новый ID здания"),
    floor_number: Optional[int] = Form(None, description="Новый номер этажа"),
    description: Optional[str] = Form(None, description="Новое описание этажа"),
    svg_file: Optional[UploadFile] = File(None, description="Новый SVG-файл этажа"),
    db: Session = Depends(get_db)
):
    """Обновить информацию об этаже. Требуются права администратора."""
    try:
        # Создаём объект FloorUpdate с переданными данными
        update_data = FloorUpdate(
            building_id=building_id,
            floor_number=floor_number,
            description=description,
            # connections не передаём через Form, оставляем None
        )
        updated_floor = update_floor(db=db, floor_id=floor_id, floor_data=update_data, svg_file=svg_file)
        if not updated_floor:
            raise HTTPException(status_code=404, detail="Floor not found")
        return updated_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении этажа: {str(e)}")

@router.delete("/{floor_id}", response_model=FloorResponse, dependencies=[Depends(admin_required)])
def delete_floor_endpoint(
    floor_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db)
):
    """Удалить этаж по ID. Требуются права администратора."""
    try:
        deleted_floor = delete_floor(db, floor_id)
        if not deleted_floor:
            raise HTTPException(status_code=404, detail="Floor not found")
        return deleted_floor
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении этажа: {str(e)}")