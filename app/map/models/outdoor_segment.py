from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base

class OutdoorSegment(Base):
    __tablename__ = "outdoor_segments"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String(50), nullable=False)
    start_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    end_building_id = Column(Integer, ForeignKey("buildings.id"), nullable=True)
    start_x = Column(Float, nullable=False)
    start_y = Column(Float, nullable=False)
    end_x = Column(Float, nullable=False)
    end_y = Column(Float, nullable=False)
    weight = Column(Integer, nullable=False)

    start_building = relationship(
        "Building",
        foreign_keys=[start_building_id],
        back_populates="outdoor_segments_start",
        overlaps="outdoor_segments_start"
    )
    end_building = relationship(
        "Building",
        foreign_keys=[end_building_id],
        back_populates="outdoor_segments_end",
        overlaps="outdoor_segments_end"
    )
    connections_from = relationship("Connection", foreign_keys="[Connection.from_outdoor_id]", back_populates="from_outdoor")
    connections_to = relationship("Connection", foreign_keys="[Connection.to_outdoor_id]", back_populates="to_outdoor")