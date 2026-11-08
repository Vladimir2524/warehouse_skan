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

    sticker_code = Column(String, index=True, nullable=False)  # *DL9UXtOS (сканируем его)
    barcode = Column(String, nullable=True)  # ШК
    box_number = Column(String, index=True, nullable=False)  # Номер коробки
    title = Column(String, nullable=True)  # Наименование

    # Тип товара/изъятия: 'NONE', 'SEIZURE', 'SEIZURE_PD'
    seizure_type = Column(String, default='NONE', index=True)

    # Статус сканирования
    is_scanned = Column(Boolean, default=False)
    scanned_at = Column(DateTime, nullable=True)

    shipment = relationship("Shipment", back_populates="items")