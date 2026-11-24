from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class Shipment(Base):
    __tablename__ = "shipments"
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)
    items = relationship("Item", back_populates="shipment", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"))
    sticker = Column(String, index=True)
    barcode = Column(String, index=True)
    box_number = Column(String, index=True)
    title = Column(String)
    weight = Column(String, nullable=True)          # <--- ВОТ ОНО: ВЕС
    is_scanned = Column(Boolean, default=False)
    is_defect = Column(Boolean, default=False)       # <--- ВОТ ОНО: БРАК
    scanned_at = Column(DateTime, nullable=True)
    desk_id = Column(String, nullable=True)
    seizure_type = Column(String, default="NONE")
    shipment = relationship("Shipment", back_populates="items")

class ScanLog(Base):
    __tablename__ = "scan_logs"
    id = Column(Integer, primary_key=True, index=True)
    shipment_id = Column(Integer, ForeignKey("shipments.id"))
    item_id = Column(Integer, ForeignKey("items.id"), nullable=True)
    scanned_code = Column(String)
    status = Column(String)
    desk_id = Column(String, default="PC1")
    created_at = Column(DateTime, default=datetime.utcnow)