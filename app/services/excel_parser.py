import pandas as pd
import io
from sqlalchemy.orm import Session
from app.models import Shipment, Item


def parse_excel_to_db(content: bytes, filename: str, db: Session):
    # 1. Читаем Excel из байтов (ровно как у тебя было)
    df = pd.read_excel(io.BytesIO(content))
    df = df.fillna("")

    # 2. Создаем запись о поставке
    shipment = Shipment(filename=filename)
    db.add(shipment)
    db.commit()
    db.refresh(shipment)

    # 3. Точный поиск колонок без захвата ссылок и фото
    col_map = {
        "sticker": "",
        "barcode": "",
        "box": "",
        "title": "",
        "prohibition": "",
        "weight": ""  # <--- Добавили колонку веса
    }

    for col in df.columns:
        c_low = str(col).lower().strip()

        # Штрихкод / Стикер
        if "стикер" in c_low or ("штрих" in c_low and "код" in c_low):
            col_map["sticker"] = col
        # Баркод
        elif "баркод" in c_low:
            col_map["barcode"] = col
        # Коробка
        elif "короб" in c_low:
            col_map["box"] = col
        # Вес (НОВОЕ)
        elif any(k in c_low for k in ["вес", "масс", "weight", "брутто"]):
            col_map["weight"] = col
        # Название товара (строго исключаем ссылки и фото)
        elif ("наименование" in c_low or "предмет" in c_low) and not any(
                x in c_low for x in ["ссылк", "url", "фото", "link"]):
            col_map["title"] = col
        elif "товар" in c_low and not col_map["title"] and not any(
                x in c_low for x in ["ссылк", "url", "фото", "link"]):
            col_map["title"] = col
        # Причина запрета / изъятие
        elif "причина" in c_low or "запрет" in c_low:
            col_map["prohibition"] = col

    # Запасной вариант для колонки запрета (AH / 33)
    if not col_map["prohibition"] and len(df.columns) >= 34:
        col_map["prohibition"] = df.columns[33]

    items_to_create = []
    seizures_count = 0

    # 4. Сбор строк
    for _, row in df.iterrows():
        raw_sticker = str(row.get(col_map["sticker"], "")).strip()
        if not raw_sticker:
            continue

        proh_val = str(row.get(col_map["prohibition"], "")).lower()

        s_type = "NONE"
        if any(x in proh_val for x in ["пд", "персональн"]):
            s_type = "SEIZURE_PD"
            seizures_count += 1
        elif proh_val and proh_val not in ["нет", "nan", "все хорошо", "не требуется"]:
            s_type = "SEIZURE"
            seizures_count += 1

        # Вес (если колонка найдена)
        w_val = str(row.get(col_map["weight"], "")).strip() if col_map["weight"] else ""
        if w_val.endswith(".0"):
            w_val = w_val[:-2]

        items_to_create.append({
            "shipment_id": shipment.id,
            "sticker": raw_sticker,
            "barcode": str(row.get(col_map["barcode"], "")).strip(),
            "box_number": str(row.get(col_map["box"], "")).strip(),
            "title": str(row.get(col_map["title"], "")).strip(),
            "weight": w_val,
            "seizure_type": s_type,
            "is_scanned": False,
            "is_defect": False
        })

    # 5. Массовая вставка
    if items_to_create:
        db.bulk_insert_mappings(Item, items_to_create)
        db.commit()

    return shipment.id, len(items_to_create), seizures_count

