from sqlalchemy import Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.database.database import Base

class Segment(Base):
    __tablename__ = "segments"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False)
    building_id = Column(Integer, ForeignKey("buildings.id"), nullable=False)
    floor = Column(Integer, nullable=False)
    connection_type = Column(String(50), nullable=False)
    start_x = Column(Float, nullable=False)
    start_y = Column(Float, nullable=False)
    end_x = Column(Float, nullable=False)
    end_y = Column(Float, nullable=False)

    building = relationship("Building", back_populates="segments")
    connections = relationship("Connection", foreign_keys="[Connection.segment_id]", back_populates="segment")