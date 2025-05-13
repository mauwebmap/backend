# app/api/endpoints/map/route.py
from app.database.database import get_db
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.map.utils.pathfinder import find_path
from app.map.models.room import Room
from app.map.models.segment import Segment
from app.map.models.outdoor_segment import OutdoorSegment
from app.map.models.floor import Floor
from app.map.models.connection import Connection
import logging
from math import atan2, degrees

logger = logging.getLogger(__name__)

router = APIRouter()

def get_direction(prev_prev_coords: tuple, prev_coords: tuple, curr_coords: tuple, prev_direction: str = None,
                  initial_orientation: str = "вперёд", i: int = 0) -> str:
    """
    Определяет направление движения или поворот на основе смещения между последними двумя сегментами.
    prev_prev_coords: (x, y) - точка до предыдущей
    prev_coords: (x, y) - предыдущая точка
    curr_coords: (x, y) - текущая точка
    prev_direction: Предыдущее направление (для оптимизации поворотов)
    initial_orientation: Начальная ориентация (по умолчанию "вперёд")
    i: Индекс текущей вершины в пути
    Возвращает: "налево", "направо", "вперёд" или "назад" для движения, или поворот при изменении направления
    """
    # Вычисляем векторы для предыдущего и текущего сегментов
    prev_dx = prev_coords[0] - prev_prev_coords[0]
    prev_dy = prev_coords[1] - prev_prev_coords[1]
    curr_dx = curr_coords[0] - prev_coords[0]
    curr_dy = curr_coords[1] - prev_coords[1]

    # Если нет смещения в текущем сегменте, считаем, что идём "вперёд"
    if curr_dx == 0 and curr_dy == 0:
        return "вперёд"

    # Вычисляем углы для предыдущего и текущего сегментов (в градусах)
    prev_angle = degrees(atan2(prev_dy, prev_dx)) if (prev_dx != 0 or prev_dy != 0) else 0
    curr_angle = degrees(atan2(curr_dy, curr_dx))

    # Нормализуем углы в диапазон [-180, 180]
    prev_angle = ((prev_angle + 180) % 360) - 180
    curr_angle = ((curr_angle + 180) % 360) - 180

    # Определяем базовое направление текущего сегмента
    base_direction = None
    if -45 <= curr_angle <= 45:
        base_direction = "направо"  # Движение вправо (x увеличивается)
    elif 45 < curr_angle <= 135:
        base_direction = "вперёд"   # Движение вверх (y увеличивается)
    elif 135 < curr_angle <= 180 or -180 <= curr_angle < -135:
        base_direction = "налево"   # Движение влево (x уменьшается)
    else:
        base_direction = "назад"    # Движение вниз (y уменьшается)

    # Корректировка для начальной ориентации (только для первого поворота)
    if i == 1 and initial_orientation == "налево" and base_direction == "направо":
        base_direction = "налево"
    elif i == 1 and initial_orientation == "налево" and base_direction == "назад":
        base_direction = "направо"

    # Если это первый сегмент (нет предыдущего), возвращаем базовое направление
    if prev_prev_coords is None or (prev_dx == 0 and prev_dy == 0):
        return base_direction

    # Вычисляем разницу углов для определения поворота
    angle_diff = curr_angle - prev_angle
    angle_diff = ((angle_diff + 180) % 360) - 180  # Нормализация разницы углов

    # Определяем поворот
    if abs(angle_diff) > 10:  # Порог для игнорирования мелких изменений (в градусах)
        if -180 < angle_diff <= -10:
            return "поверните налево"  # Против часовой стрелки
        elif 10 <= angle_diff < 180:
            return "поверните направо"  # По часовой стрелке

    # Если нет значительного поворота, возвращаем базовое направление
    return base_direction

def get_vertex_details(vertex: str, db: Session) -> tuple:
    """
    Возвращает читаемое имя вершины и её номер (если есть).
    Возвращает: (имя, номер)
    """
    vertex_type, vertex_id = vertex.split("_", 1)
    if vertex_type == "room":
        room = db.query(Room).filter(Room.id == int(vertex_id)).first()
        if room:
            return room.name, room.cab_id
        return vertex, None
    elif vertex_type == "segment":
        return "лестницы", None if "_end" in vertex or "_start" in vertex else vertex
    elif vertex_type == "outdoor":
        return f"Уличный сегмент {vertex_id}", None
    return vertex, None

def generate_text_instructions(path: list, graph: dict, db: Session) -> list:
    """
    Генерирует текстовое описание пути в виде массива строк.
    path: Список вершин маршрута
    graph: Граф с координатами вершин
    db: Сессия базы данных
    Возвращает: Список инструкций (каждая строка — отдельный шаг)
    """
    instructions = []
    prev_prev_coords = None
    prev_coords = None
    prev_vertex = None
    prev_direction = None
    current_instruction = []

    for i, vertex in enumerate(path):
        # Получаем координаты текущей вершины
        coords = graph.vertices[vertex]
        floor_id = coords[2]

        # Определяем этаж
        if floor_id != 0:
            floor = db.query(Floor).filter(Floor.id == floor_id).first()
            floor_number = floor.floor_number if floor else floor_id
        else:
            floor_number = 0

        # Получаем читаемое имя вершины и её номер
        vertex_name, vertex_number = get_vertex_details(vertex, db)

        # Начало маршрута
        if i == 0:
            current_instruction.append(f"При выходе из {vertex_name}")
            initial_orientation = "налево"  # Предполагаем начальную ориентацию
            prev_coords = (coords[0], coords[1])
            prev_vertex = vertex
            continue

        # Проверяем переход между этажами
        if prev_floor != floor_number and i > 1:
            # Завершаем текущую инструкцию, если она есть
            if current_instruction:
                instructions.append(" ".join(current_instruction))
                current_instruction = []

            # Ищем соединение типа "лестница"
            prev_segment_id = int(prev_vertex.split("_")[1]) if prev_vertex.startswith("segment_") else None
            curr_segment_id = int(vertex.split("_")[1]) if vertex.startswith("segment_") else None
            if prev_segment_id and curr_segment_id:
                connection = db.query(Connection).filter(
                    Connection.type == "лестница",
                    ((Connection.from_segment_id == prev_segment_id) & (Connection.to_segment_id == curr_segment_id)) |
                    ((Connection.from_segment_id == curr_segment_id) & (Connection.to_segment_id == prev_segment_id))
                ).first()
                if connection:
                    if prev_floor < floor_number:
                        instructions.append(f"Дойдите до лестницы и поднимитесь на {floor_number}-й этаж")
                    else:
                        instructions.append(f"Дойдите до лестницы и спуститесь на {floor_number}-й этаж")
            prev_direction = None  # Сбрасываем направление после перехода
            prev_prev_coords = None  # Сбрасываем предыдущую точку после перехода

        # Определяем направление или поворот
        if prev_coords:
            direction = get_direction(prev_prev_coords, prev_coords, (coords[0], coords[1]), prev_direction,
                                     initial_orientation if i == 1 else None, i)
            if direction.startswith("поверните"):
                if current_instruction and "поверните" in current_instruction[-1].lower():
                    instructions.append(" ".join(current_instruction))
                    current_instruction = [direction]
                else:
                    current_instruction.append(direction)
            elif direction != "вперёд" or not current_instruction:
                current_instruction.append(direction)
            prev_direction = direction if not direction.startswith("поверните") else prev_direction

        # Если это последняя точка, указываем пункт назначения
        if i == len(path) - 1:
            destination = f"{vertex_name} номер {vertex_number}" if vertex_number else vertex_name
            current_instruction.append(f"пройдите вперёд до {destination}")
            instructions.append(" ".join(current_instruction))

        prev_prev_coords = prev_coords
        prev_coords = (coords[0], coords[1])
        prev_floor = floor_number
        prev_vertex = vertex

    return instructions

@router.get("/route", response_model=dict)
async def get_route(start: str, end: str, db: Session = Depends(get_db)):
    logger.info(f"Received request to find route from {start} to {end}")

    # Находим путь и граф
    path, weight, graph = find_path(db, start, end, return_graph=True)
    if not path:
        logger.warning("No path found")
        raise HTTPException(status_code=404, detail="Маршрут не найден")

    logger.info(f"A* result: path={path}, weight={weight}")

    # Генерируем текстовые инструкции
    instructions = generate_text_instructions(path, graph, db)

    # Преобразуем путь в формат для фронта
    route = []
    current_floor_number = None
    floor_points = []
    last_point = None
    prev_vertex = None
    transition_points = []

    # Для отслеживания добавленных точек и избежания дубликатов
    added_points = set()

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
                if prev_vertex.startswith("phantom_") and i + 1 < len(path):
                    next_vertex = path[i + 1]
                    if next_vertex.startswith("phantom_"):
                        skip_vertex = True
                        logger.debug(f"Skipping segment vertex {vertex} between phantom points")

            # Формируем точку
            point = {"x": coords[0], "y": coords[1]}
            point_tuple = (coords[0], coords[1])  # Для проверки дубликатов

            # Проверяем, является ли текущая вершина частью перехода между этажами
            if prev_vertex and vertex.startswith("segment_") and prev_vertex.startswith("segment_"):
                prev_segment_id = int(prev_vertex.split("_")[1])
                curr_segment_id = int(vertex.split("_")[1])
                connection = db.query(Connection).filter(
                    Connection.type == "лестница",
                    ((Connection.from_segment_id == prev_segment_id) & (Connection.to_segment_id == curr_segment_id)) |
                    ((Connection.from_segment_id == curr_segment_id) & (Connection.to_segment_id == prev_segment_id))
                ).first()
                if connection:
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
                if point_tuple not in added_points:
                    floor_points.append(point)
                    added_points.add(point_tuple)
            elif floor_number != current_floor_number:  # Смена этажа
                if floor_points:
                    # Добавляем точки перехода на предыдущем этаже
                    if transition_points:
                        for tp in transition_points[:2]:
                            tp_tuple = (tp["x"], tp["y"])
                            if tp_tuple not in added_points:
                                floor_points.append(tp)
                                added_points.add(tp_tuple)
                        transition_points = transition_points[2:]
                    route.append({"floor": current_floor_number, "points": floor_points})
                # Создаём новый список точек
                added_points.clear()  # Очищаем для нового этажа
                floor_points = []
                if transition_points:
                    for tp in transition_points:
                        tp_tuple = (tp["x"], tp["y"])
                        if tp_tuple not in added_points:
                            floor_points.append(tp)
                            added_points.add(tp_tuple)
                    transition_points = []
                if point_tuple not in added_points:
                    floor_points.append(point)
                    added_points.add(point_tuple)
                current_floor_number = floor_number
            elif not skip_vertex:  # Добавляем точку, если не пропускаем
                if point_tuple not in added_points:
                    floor_points.append(point)
                    added_points.add(point_tuple)

            last_point = point
            prev_vertex = vertex
            logger.debug(f"Added point for vertex {vertex}: x={coords[0]}, y={coords[1]}")

        except Exception as e:
            logger.error(f"Error processing vertex {vertex}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Ошибка при обработке вершины {vertex}: {str(e)}")

    if floor_points:
        route.append({"floor": current_floor_number, "points": floor_points})

    # Добавляем текстовые инструкции в ответ
    return {"path": route, "weight": weight, "instructions": instructions}