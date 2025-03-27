from sqlalchemy import Column, Integer, String, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.database.database import Base

class Building(Base):
    __tablename__ = "buildings"
    id = Column(Integer, primary_key=True, index=True)
    campus_id = Column(Integer, ForeignKey("campuses.id"), nullable=False)
    name = Column(String(255), nullable=False)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    description = Column(Text, nullable=True)
    image_path = Column(String(255), nullable=True)

    campus = relationship("Campus", back_populates="buildings")
    floors = relationship("Floor", back_populates="building")
    rooms = relationship("Room", back_populates="building")
    segments = relationship("Segment", back_populates="building")
    outdoor_segments_start = relationship(
        "OutdoorSegment",
        foreign_keys="[OutdoorSegment.start_building_id]",
        back_populates="start_building"
    )
    outdoor_segments_end = relationship(
        "OutdoorSegment",
        foreign_keys="[OutdoorSegment.end_building_id]",
        back_populates="end_building"
    )