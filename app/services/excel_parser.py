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

def bootstrap_excel_to_db(db: Session, file_path: str, filename: str):
    try:
        header_idx = find_exact_header_row(file_path)
        df = pd.read_excel(file_path, header=header_idx, dtype=str)

        # Очищаем заголовки
        df.columns = [str(col).strip() for col in df.columns]

        # Ищем колонки (логика та же...)
        sticker_col = next((c for c in df.columns if 'код стикера' in c.lower()), None)
        box_col = next((c for c in df.columns if 'коробк' in c.lower()), None)
        # ... остальные колонки ...

        if not sticker_col or not box_col:
            raise ValueError("Обязательные колонки не найдены")

        # СОЗДАЕМ ОБЪЕКТЫ, НО НЕ СОХРАНЯЕМ В БД СРАЗУ
        new_shipment = Shipment(filename=filename)
        db.add(new_shipment)
        db.flush()  # Получаем ID отгрузки, но не завершаем транзакцию

        items_to_create = []
        OK_VALUES = {'нет', 'все хорошо', 'всё хорошо', 'не требуется', 'nan', 'none', '', '0'}

        for _, row in df.iterrows():
            sticker = str(row.get(sticker_col, '')).strip()
            if not sticker or sticker.lower() in OK_VALUES:
                continue

            # ... логика определения s_type ...

            item = Item(
                shipment_id=new_shipment.id,
                sticker_code=sticker,
                box_number=str(row.get(box_col, '')).strip(),
                # ... остальные поля ...
            )
            items_to_create.append(item)

        db.add_all(items_to_create)

        # ТОЛЬКО ТЕПЕРЬ СОХРАНЯЕМ ВСЁ ОДНИМ МАХОМ
        db.commit()
        return new_shipment.id

    except Exception as e:
        db.rollback()  # Если упало — отменяем всё, что успели "накосячить" в БД
        print(f"Ошибка парсинга: {e}")
        raise HTTPException(status_code=400, detail=f"Ошибка парсинга файла: {str(e)}")

