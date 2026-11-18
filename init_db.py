from app.database import engine, Base
from app.models import Shipment, Item
import app.models

print("Создаем таблицы в БД...")
Base.metadata.create_all(bind=engine)
print("База данных успешно создана!")