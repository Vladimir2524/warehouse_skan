import pandas as pd
from sqlalchemy.orm import Session
from app.models import Shipment, Item

def bootstrap_excel_to_db(db: Session, file_path: str, filename: str):
    df = pd.read_excel(file_path, dtype={'Код стикера': str, 'ШК': str, 'Номер коробки': str})

    new_shipment = Shipment(filename=filename)
    db.add(new_shipment)
    db.commit()
    db.refresh(new_shipment)

    items_to_create = []

    for _, row in df.iterrows():
        # Читаем Колонку AH ("Причина запрета")
        prohibition_raw = str(row.get('Причина запрета', '')).strip()

        # 1. Если колонка пустая или 'nan' -> Товар обычный (ОК)
        if not prohibition_raw or prohibition_raw.lower() == 'nan':
            s_type = 'NONE'
        # 2. Если в причине прямо указано ПД
        elif prohibition_raw.upper() == 'ПД':
            s_type = 'SEIZURE_PD'
        # 3. Любая другая причина запрета (акциз, контрафакт и т.д.)
        else:
            s_type = 'SEIZURE'

        sticker = str(row.get('Код стикера', '')).strip()

        item = Item(
            shipment_id=new_shipment.id,
            sticker_code=sticker,
            barcode=str(row.get('ШК', '')).strip(),
            box_number=str(row.get('Номер коробки', '')).strip(),
            title=str(row.get('Наименование товара', '')).strip(),
            seizure_type=s_type
        )
        items_to_create.append(item)

    db.add_all(items_to_create)
    db.commit()

    return new_shipment.id