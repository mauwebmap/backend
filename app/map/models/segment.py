from sqlalchemy import Column, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base

class Segment(Base):
    __tablename__ = "segments"
    id = Column(Integer, primary_key=True, index=True)
    start_x = Column(Float, nullable=False)  # Координата X начала сегмента
    start_y = Column(Float, nullable=False)  # Координата Y начала сегмента
    end_x = Column(Float, nullable=False)  # Координата X конца сегмента
    end_y = Column(Float, nullable=False)  # Координата Y конца сегмента
    floor_id = Column(Integer, ForeignKey("floors.id"), nullable=False)  # ID этажа
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)  # ID здания

    # Связи с другими моделями
    floor = relationship("Floor", back_populates="segments")  # Этаж, к которому относится сегмент
    building = relationship("Building", back_populates="segments")  # Здание, к которому относится сегмент

    # Связи для соединений
    connections = relationship(
        "Connection",
        foreign_keys="[Connection.segment_id]",
        back_populates="segment"
    )
    from_connections = relationship(
        "Connection",
        foreign_keys="[Connection.from_segment_id]",
        back_populates="from_segment"
    )
    to_connections = relationship(
        "Connection",
        foreign_keys="[Connection.to_segment_id]",
        back_populates="to_segment"
    )