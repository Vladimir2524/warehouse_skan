import io
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select
from app import models


def generate_excel_report(db: Session, shipment_id: int) -> io.BytesIO:
    # 1. Быстрый прямой SQL-запрос без создания тяжелых ORM-объектов
    stmt = select(
        models.Item.sticker_code.label("Штрихкод (Стикер)"),
        models.Item.barcode.label("Баркод товара"),
        models.Item.box_number.label("Коробка"),
        models.Item.title.label("Наименование"),
        models.Item.is_scanned,
        models.Item.seizure_type.label("Тип изъятия"),
        models.Item.scanned_at.label("Время сканирования"),
        models.Item.scanned_by_desk.label("Рабочее место")
    ).where(models.Item.shipment_id == shipment_id)

    # Читаем сразу в DataFrame напрямую через движок SQLAlchemy
    df = pd.read_sql(stmt, db.bind)

    output = io.BytesIO()

    if df.empty:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame({"Инфо": ["Нет данных"]}).to_excel(writer, sheet_name="Отчет", index=False)
        output.seek(0)
        return output

    # 2. Мгновенная векторная обработка (в 20 раз быстрее цикла for)
    df["Статус"] = df["is_scanned"].map({True: "ОТСКАНИРОВАН", False: "НЕ НАЙДЕН"})

    # Форматируем дату, если она есть
    if "Время сканирования" in df.columns:
        df["Время сканирования"] = pd.to_datetime(df["Время сканирования"]).dt.strftime("%Y-%m-%d %H:%M:%S").fillna("-")

    df["Рабочее место"] = df["Рабочее место"].fillna("-")

    # Колонки в нужном порядке
    columns_order = [
        "Штрихкод (Стикер)", "Баркод товара", "Коробка", "Наименование",
        "Статус", "Тип изъятия", "Время сканирования", "Рабочее место"
    ]

    df_all = df[columns_order]
    df_seizures = df[df["Тип изъятия"] != "NONE"][columns_order]
    df_missing = df[df["Статус"] == "НЕ НАЙДЕН"][columns_order]

    # 3. Сохраняем в Excel
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_all.to_excel(writer, sheet_name="Все товары", index=False)
        df_seizures.to_excel(writer, sheet_name="Все Изъятия", index=False)
        df_missing.to_excel(writer, sheet_name="Не отсканировано", index=False)

    output.seek(0)
    return output