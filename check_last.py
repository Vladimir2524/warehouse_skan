from app.database import SessionLocal
from app.models import Shipment, Item

db = SessionLocal()
last_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()

print("--- ДИАГНОСТИКА ---")
if last_shipment:
    print(f"1. ПОСЛЕДНИЙ ID ОТГРУЗКИ В БАЗЕ: {last_shipment.id}")
    print(f"2. ФАЙЛ: {last_shipment.filename}")

    items = db.query(Item).filter(Item.shipment_id == last_shipment.id).all()
    print(f"3. ВСЕГО ТОВАРОВ ЗАГРУЖЕНО: {len(items)}")

    if items:
        print("\n4. ПЕРВЫЕ 5 КОДОВ ИЗ ЭТОГО ФАЙЛА В БАЗЕ:")
        for i in items[:5]:
            print(f"   - '{i.sticker_code}' (Коробка: {i.box_number}, Тип: {i.seizure_type})")
else:
    print("База пуста!")

db.close()