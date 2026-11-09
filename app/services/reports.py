import io
import pandas as pd
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import Item, Shipment


def generate_excel_report(db: Session, shipment_id: int) -> io.BytesIO:
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Отгрузка с таким ID не найдена")

    items = db.query(Item).filter(Item.shipment_id == shipment_id).all()
    if not items:
        raise HTTPException(status_code=400, detail="В этой отгрузке нет товаров")

    data = []
    for item in items:
        if item.seizure_type == 'SEIZURE_PD':
            cat = "Изъятие: ПД"
        elif item.seizure_type == 'SEIZURE':
            cat = "Изъятие: Простой код"
        else:
            cat = "Обычный товар"

        data.append({
            "Код стикера": item.sticker_code,
            "Штрихкод": item.barcode,
            "Номер коробки": item.box_number,
            "Наименование": item.title,
            "Категория": cat,
            "Отсканирован": "ДА" if item.is_scanned else "НЕТ",
            "Время сканирования": item.scanned_at.strftime("%Y-%m-%d %H:%M:%S") if item.scanned_at else "",
            "Рабочее место": item.scanned_by_desk or ""
        })

    df = pd.DataFrame(data)

    # Формируем Excel в оперативной памяти (без мусора на диске)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        # Лист 1: Все товары
        df.to_excel(writer, sheet_name='Все товары', index=False)

        # Лист 2: Только Изъятия
        df_seizures = df[df['Категория'].str.contains('Изъятие')]
        df_seizures.to_excel(writer, sheet_name='Только Изъятия', index=False)

        # Лист 3: Не отсканировано (Остатки)
        df_missing = df[df['Отсканирован'] == 'НЕТ']
        df_missing.to_excel(writer, sheet_name='Не отсканировано', index=False)

    output.seek(0)
    return output