from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base

class Connection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)
    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    type = Column(String(50), nullable=False)
    weight = Column(Integer, nullable=False)

    room = relationship("Room", back_populates="connections")
    segment = relationship("Segment", back_populates="connections")