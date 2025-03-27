from sqlalchemy import Column, Integer, String, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.database import Base

class Floor(Base):
    __tablename__ = "floors"
    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)  # ID здания
    floor_number = Column(Integer, nullable=False)  # Номер этажа
    image_path = Column(String(255), nullable=True)  # Путь к изображению этажа
    description = Column(Text, nullable=True)  # Описание этажа

    # Связи с другими моделями
    building = relationship("Building", back_populates="floors")  # Здание, к которому относится этаж
    rooms = relationship("Room", back_populates="floor")  # Комнаты на этаже
    segments = relationship("Segment", back_populates="floor")  # Сегменты (коридоры) на этаже

    # Связи для соединений между этажами
    connections_from = relationship(
        "Connection",
        foreign_keys="[Connection.from_floor_id]",
        back_populates="from_floor"
    )
    connections_to = relationship(
        "Connection",
        foreign_keys="[Connection.to_floor_id]",
        back_populates="to_floor"
    )