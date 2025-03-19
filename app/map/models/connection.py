from sqlalchemy import Column, Integer, String, ForeignKey, Float
from sqlalchemy.orm import relationship
from app.database.database import Base

class Connection(Base):
    __tablename__ = "connections"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False)
    weight = Column(Float, nullable=False)

    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=True)

    segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    from_segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)

    to_segment_id = Column(Integer, ForeignKey("segments.id"), nullable=True)
    from_outdoor_id = Column(Integer, ForeignKey("outdoor_segments.id"), nullable=True)
    to_outdoor_id = Column(Integer, ForeignKey("outdoor_segments.id"), nullable=True)

    from_floor_id = Column(Integer, ForeignKey("floors.id"), nullable=True)
    to_floor_id = Column(Integer, ForeignKey("floors.id"), nullable=True)

    room = relationship("Room", back_populates="connections")

    segment = relationship("Segment", foreign_keys=[segment_id], back_populates="connections")

    from_segment = relationship("Segment", foreign_keys=[from_segment_id], back_populates="from_connections")
    to_segment = relationship("Segment", foreign_keys=[to_segment_id], back_populates="to_connections")

    from_outdoor = relationship("OutdoorSegment", foreign_keys=[from_outdoor_id], back_populates="connections_from")
    to_outdoor = relationship("OutdoorSegment", foreign_keys=[to_outdoor_id], back_populates="connections_to")

    from_floor = relationship("Floor", foreign_keys=[from_floor_id], back_populates="connections_from")
    to_floor = relationship("Floor", foreign_keys=[to_floor_id], back_populates="connections_to")