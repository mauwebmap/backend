from sqlalchemy import Column, Integer, String, ForeignKey, Text, Float, JSON
from sqlalchemy.orm import relationship
from app.database.database import Base

class Room(Base):
    __tablename__ = "rooms"
    id = Column(Integer, primary_key=True, index=True)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)  # ID здания
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False)  # ID этажа
    name = Column(String(255), nullable=False)  # Название комнаты
    cab_id = Column(String(50), nullable=False)  # Кабинетный номер
    coordinates = Column(JSON, nullable=True)  # Координаты комнаты (JSON)
    cab_x = Column(Float, nullable=True)  # Координата X кабинета
    cab_y = Column(Float, nullable=True)  # Координата Y кабинета
    description = Column(Text, nullable=True)  # Описание комнаты
    image_path = Column(String(255), nullable=True)  # Путь к изображению комнаты

    # Связи с другими моделями
    building = relationship("Building", back_populates="rooms")  # Здание, к которому относится комната
    floor = relationship("Floor", back_populates="rooms")  # Этаж, к которому относится комната
    connections = relationship("Connection", foreign_keys="[Connection.room_id]", back_populates="room")  # Соединения