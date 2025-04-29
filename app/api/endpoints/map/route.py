# app/api/endpoints/map/route.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.database import get_db
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.floor import Floor  # Добавляем импорт модели Floor
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")

    # Находим путь и граф
    path, weight, graph = find_path(db, start, end, return_graph=True)
    if not path:
        logger.warning("No path found")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"A* result: path={path}, weight={weight}")

    # Преобразуем путь в формат для фронта
    route = []
    current_floor_number = None
    floor_points = []
    last_point = None
    prev_vertex = None  # Для отслеживания предыдущей вершины
    transition_points = []  # Для хранения точек перехода между этажами

    for i, vertex in enumerate(path):
        try:
            # Разбираем вершину
            if vertex.startswith("phantom_"):
                parts = vertex.split("_")
                if len(parts) != 5 or parts[0] != "phantom" or parts[1] != "room" or parts[3] != "segment":
                    raise ValueError(f"Неверный формат фантомной вершины: {vertex}")

                coords = graph.vertices[vertex]
                floor_id = coords[2]
                if floor_id != 0:
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                else:
                    floor_number = 0
                logger.debug(
                    f"Processing phantom vertex {vertex}: floor_id={floor_id}, floor_number={floor_number}, coords={coords}")
            else:
                vertex_type, vertex_id_part = vertex.split("_", 1)

                coords = None
                floor_id = None
                floor_number = None
                if vertex_type == "room":
                    vertex_id = int(vertex_id_part)
                    room = db.query(Room).filter(Room.id == vertex_id).first()
                    if not room:
                        raise ValueError(f"Комната {vertex} не найдена")
                    coords = (room.cab_x, room.cab_y)
                    floor_id = room.floor_id
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                elif vertex_type == "segment":
                    segment_id_part, position = vertex_id_part.rsplit("_", 1)
                    segment_id = int(segment_id_part)
                    segment = db.query(Segment).filter(Segment.id == segment_id).first()
                    if not segment:
                        raise ValueError(f"Сегмент {vertex} не найден")
                    coords = (segment.start_x, segment.start_y) if position == "start" else (
                    segment.end_x, segment.end_y)
                    floor_id = segment.floor_id
                    floor = db.query(Floor).filter(Floor.id == floor_id).first()
                    if not floor:
                        raise ValueError(f"Этаж с id {floor_id} не найден")
                    floor_number = floor.floor_number
                elif vertex_type == "outdoor":
                    outdoor_id_part, position = vertex_id_part.rsplit("_", 1)
                    outdoor_id = int(outdoor_id_part)
                    outdoor = db.query(OutdoorSegment).filter(OutdoorSegment.id == outdoor_id).first()
                    if not outdoor:
                        raise ValueError(f"Уличный сегмент {vertex} не найден")
                    coords = (outdoor.start_x, outdoor.start_y) if position == "start" else (
                    outdoor.end_x, outdoor.end_y)
                    floor_id = 0
                    floor_number = 0
                else:
                    raise ValueError(f"Неизвестный тип вершины: {vertex_type}")

                logger.debug(
                    f"Processing vertex {vertex}: {vertex_type}, floor_id={floor_id}, floor_number={floor_number}")

            # Проверяем, нужно ли пропустить вершину (для соседних комнат)
            skip_vertex = False
            if prev_vertex and vertex.startswith("segment_"):
                # Проверяем, идём ли мы от одной фантомной точки к другой через сегмент
                if prev_vertex.startswith("phantom_") and i + 1 < len(path):
                    next_vertex = path[i + 1]
                    if next_vertex.startswith("phantom_"):
                        # Пропускаем промежуточные точки сегмента
                        skip_vertex = True
                        logger.debug(f"Skipping segment vertex {vertex} between phantom points")

            # Формируем точку
            point = {"x": coords[0], "y": coords[1]}

            # Проверяем, является ли текущая вершина частью перехода между этажами
            if prev_vertex and vertex.startswith("segment_") and prev_vertex.startswith("segment_"):
                prev_segment_id = int(prev_vertex.split("_")[1])
                curr_segment_id = int(vertex.split("_")[1])
                # Проверяем, есть ли соединение типа "лестница" между этими сегментами
                from app.map.models.connection import Connection
                connection = db.query(Connection).filter(
                    Connection.type == "лестница",
                    ((Connection.from_segment_id == prev_segment_id) & (Connection.to_segment_id == curr_segment_id)) |
                    ((Connection.from_segment_id == curr_segment_id) & (Connection.to_segment_id == prev_segment_id))
                ).first()
                if connection:
                    # Добавляем обе точки текущего и предыдущего сегмента
                    prev_segment = db.query(Segment).filter(Segment.id == prev_segment_id).first()
                    curr_segment = db.query(Segment).filter(Segment.id == curr_segment_id).first()
                    transition_points = [
                        {"x": prev_segment.start_x, "y": prev_segment.start_y},
                        {"x": prev_segment.end_x, "y": prev_segment.end_y},
                        {"x": curr_segment.end_x, "y": curr_segment.end_y},
                        {"x": curr_segment.start_x, "y": curr_segment.start_y}
                    ]
                    logger.debug(
                        f"Transition between segments {prev_segment_id} and {curr_segment_id}: {transition_points}")

            # Добавляем точку в маршрут
            if current_floor_number is None:  # Первый этаж
                current_floor_number = floor_number
                floor_points.append(point)
            elif floor_number != current_floor_number:  # Смена этажа
                if floor_points:
                    # Добавляем точки перехода на предыдущем этаже
                    if transition_points:
                        floor_points.extend(transition_points[:2])  # Первые две точки (предыдущий сегмент)
                        transition_points = transition_points[2:]  # Оставляем точки для следующего этажа
                    route.append({"floor": current_floor_number, "points": floor_points})
                # Создаём новый список точек
                floor_points = transition_points if transition_points else [last_point] if last_point else []
                floor_points.append(point)
                current_floor_number = floor_number
            elif not skip_vertex:  # Добавляем точку, если не пропускаем
                floor_points.append(point)

            last_point = point
            prev_vertex = vertex
            logger.debug(f"Added point for vertex {vertex}: x={coords[0]}, y={coords[1]}")

        except Exception as e:
            logger.error(f"Error processing vertex {vertex}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при обработке вершины {vertex}: {str(e)}")

    if floor_points:
        route.append({"floor": current_floor_number, "points": floor_points})

    return {"path": route, "weight": weight}