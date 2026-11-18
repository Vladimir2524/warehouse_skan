import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Shipment, Item


def find_exact_header_row(file_path: str) -> int:
    df_raw = pd.read_excel(file_path, nrows=15, header=None)
    for idx, row in df_raw.iterrows():
        row_str = " ".join([str(val).lower() for val in row.values if pd.notna(val)])
        if 'код стикера' in row_str or 'номер коробки' in row_str or 'причина' in row_str:
            return idx
    return 0


def bootstrap_excel_to_db(db: Session, file_path: str, filename: str) -> int:
    try:
        header_idx = find_exact_header_row(file_path)

        # Читаем Excel и сразу заменяем все пустые значения (NaN) на пустые строки
        df = pd.read_excel(file_path, header=header_idx, dtype=str)
        df = df.fillna("")
        df.columns = [str(col).strip() for col in df.columns]

        # Ищем ключевые колонки
        sticker_col = next((c for c in df.columns if 'код стикера' in str(c).lower()), None) or \
                      next((c for c in df.columns if 'стикер' in str(c).lower()), None)

        box_col = next((c for c in df.columns if 'номер коробки' in str(c).lower()), None) or \
                  next((c for c in df.columns if 'коробк' in str(c).lower()), None)

        barcode_col = next((c for c in df.columns if any(k in str(c).lower() for k in ['баркод', 'штрихкод'])), None)
        title_col = next((c for c in df.columns if
                          any(k in str(c).lower() for k in ['наименование', 'предмет', 'название', 'товар'])), None)
        reason_col = next((c for c in df.columns if any(k in str(c).lower() for k in ['причина', 'запрет'])), None)

        if not sticker_col or not box_col:
            raise ValueError("Обязательные колонки (стикер / коробка) не найдены в файле")

        # Создаем запись о партии
        new_shipment = Shipment(filename=filename)
        db.add(new_shipment)
        db.flush()

        OK_VALUES = {'нет', 'все хорошо', 'всё хорошо', 'не требуется', 'nan', 'none', '', '0'}
        items_to_create = []

        # Быстрый проход через список словарей (в разы быстрее iterrows)
        records = df.to_dict('records')

        for row in records:
            stk = str(row.get(sticker_col, '')).strip()
            if stk.endswith('.0'):
                stk = stk[:-2]

            if not stk or stk.lower() in OK_VALUES:
                continue

            box = str(row.get(box_col, '')).strip()
            if box.endswith('.0'):
                box = box[:-2]

            # Безопасное чтение баркода и названия
            bc = str(row.get(barcode_col, '')).strip() if barcode_col else ""
            if bc.endswith('.0'):
                bc = bc[:-2]
            bc_val = bc if bc and bc.lower() not in OK_VALUES else None

            ttl = str(row.get(title_col, '')).strip() if title_col else ""
            ttl_val = ttl if ttl and ttl.lower() not in OK_VALUES else None

            # Определение причины изъятия
            rsn = str(row.get(reason_col, '')).strip().lower() if reason_col else ""
            if not rsn or rsn in OK_VALUES:
                s_type = 'NONE'
            elif 'пд' in rsn or 'персональн' in rsn:
                s_type = 'SEIZURE_PD'
            else:
                s_type = 'SEIZURE'

            items_to_create.append({
                "shipment_id": new_shipment.id,
                "sticker_code": stk,
                "barcode": bc_val,
                "box_number": box,
                "title": ttl_val,
                "seizure_type": s_type,
                "is_scanned": False,
                "scanned_at": None,
                "scanned_by_desk": None
            })

        # Мгновенная вставка всей пачки в SQLite
        if items_to_create:
            db.bulk_insert_mappings(Item, items_to_create)
            db.commit()

        return new_shipment.id

    except Exception as e:
        db.rollback()
        print(f"Ошибка парсинга: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга файла: {str(e)}")

