from app.database import SessionLocal
from app.models import Shipment, Item

db = SessionLocal()
last_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()

if last_shipment:
    count = db.query(Item).filter(Item.shipment_id == last_shipment.id).count()
    print(f"ПОСЛЕДНЯЯ ОТГРУЗКА В БАЗЕ: ID = {last_shipment.id}, ТОВАРОВ = {count}")
    # Покажем один реальный код из этой отгрузки:
    sample_item = db.query(Item).filter(Item.shipment_id == last_shipment.id).first()
    print(f"ПРИМЕР КОДА ДЛЯ СКАНИРОВАНИЯ: '{sample_item.sticker_code}'")
else:
    print("БАЗА ПУСТА! Нужен импорт через test_parse.py")