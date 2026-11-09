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
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Ошибка чтения Excel: {str(e)}")

    df.columns = [str(col).strip() for col in df.columns]

    # Поиск колонок
    sticker_col = next((c for c in df.columns if 'код стикера' in c.lower()), None)
    if not sticker_col:
        sticker_col = next((c for c in df.columns if c.lower() == 'стикер'), None)

    box_col = next((c for c in df.columns if 'коробк' in c.lower()), None)

    # Ищем колонки с причинами/запретами
    prohibition_col = next((c for c in df.columns if 'причина' in c.lower() or 'запрет' in c.lower()), None)

    title_col = next((c for c in df.columns if 'наименование' in c.lower() or 'товар' in c.lower()), None)
    barcode_col = next((c for c in df.columns if c.lower() in ('шк', 'штрихкод')), None)

    if not sticker_col or not box_col:
        raise HTTPException(
            status_code=400,
            detail=f"Не найдены обязательные колонки в файле! (Найдены: {', '.join(df.columns[:5])})"
        )

    new_shipment = Shipment(filename=filename)
    db.add(new_shipment)
    db.commit()
    db.refresh(new_shipment)

    # Список фраз, которые означают ЧИСТЫЙ ТОВАР (НЕТ ИЗЪЯТИЯ)
    OK_VALUES = {'нет', 'все хорошо', 'всё хорошо', 'не требуется', 'nan', 'none', '', '0'}

    items_to_create = []

    for _, row in df.iterrows():
        sticker = str(row.get(sticker_col, '')).strip()

        if not sticker or sticker.lower() in OK_VALUES:
            continue

        prohibition_raw = str(row.get(prohibition_col, '')).strip().lower() if prohibition_col else ''

        # ОПРЕДЕЛЕНИЕ ТИПА ИЗЪЯТИЯ
        if prohibition_raw in OK_VALUES:
            # Товар чистый!
            s_type = 'NONE'
        elif prohibition_raw == 'пд' or 'персональн' in prohibition_raw:
            # Изъятие ПД
            s_type = 'SEIZURE_PD'
        else:
            # Реальное изъятие (акциз, вето, контрафакт и т.д.)
            s_type = 'SEIZURE'

        item = Item(
            shipment_id=new_shipment.id,
            sticker_code=sticker,
            barcode=str(row.get(barcode_col, '')).strip() if barcode_col and pd.notna(row.get(barcode_col)) else '',
            box_number=str(row.get(box_col, '')).strip() if pd.notna(row.get(box_col)) else '',
            title=str(row.get(title_col, '')).strip() if title_col and pd.notna(row.get(title_col)) else '',
            seizure_type=s_type
        )
        items_to_create.append(item)

    db.add_all(items_to_create)
    db.commit()

    return new_shipment.id
