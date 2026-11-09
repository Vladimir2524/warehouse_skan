from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    items = relationship("Item", back_populates="shipment", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"), nullable=False)

    sticker_code = Column(String, index=True, nullable=False)
    barcode = Column(String, nullable=True)
    box_number = Column(String, index=True, nullable=False)
    title = Column(String, nullable=True)

    seizure_type = Column(String, default='NONE', index=True)

    is_scanned = Column(Boolean, default=False)
    scanned_at = Column(DateTime, nullable=True)
    scanned_by_desk = Column(String, nullable=True)  # <-- ВОТ ЭТА СТРОКА!

    shipment = relationship("Shipment", back_populates="items")