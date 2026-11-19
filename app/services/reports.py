import io
import pandas as pd
from sqlalchemy.orm import Session
from app.models import Item, Shipment, ScanLog


def generate_excel_report(db: Session, shipment_id: int = None) -> io.BytesIO:
    # 1. Определяем нужную партию
    if not shipment_id:
        target = db.query(Shipment).join(Item).order_by(Shipment.id.desc()).first()
        if not target:
            target = db.query(Shipment).order_by(Shipment.id.desc()).first()
        shipment_id = target.id if target else 1

    # 2. Выбираем товары
    items = db.query(Item).filter(Item.shipment_id == shipment_id).all()

    # Страховка: если по ID товаров нет, берем партию, где они точно есть
    if not items:
        fallback = db.query(Item).order_by(Item.id.desc()).first()
        if fallback:
            shipment_id = fallback.shipment_id
            items = db.query(Item).filter(Item.shipment_id == shipment_id).all()

    # 3. Собираем данные
    data_all = []
    for it in items:
        if it.seizure_type == "SEIZURE_PD":
            seiz_label = "ИЗЪЯТИЕ: ПД"
        elif it.seizure_type == "SEIZURE":
            seiz_label = "ИЗЪЯТИЕ"
        else:
            seiz_label = "НЕТ"

        data_all.append({
            "Штрихкод (Стикер)": it.sticker or "",
            "Баркод товара": it.barcode or "",
            "Коробка": it.box_number or "",
            "Наименование": it.title or "",
            "Статус": "ОТСКАНИРОВАН" if it.is_scanned else "НЕ НАЙДЕН",
            "Тип изъятия": seiz_label,
            "Время сканирования": it.scanned_at.strftime("%Y-%m-%d %H:%M:%S") if it.scanned_at else "",
            "Рабочее место": it.desk_id or ""
        })

    df_all = pd.DataFrame(data_all)
    if df_all.empty:
        df_all = pd.DataFrame(columns=[
            "Штрихкод (Стикер)", "Баркод товара", "Коробка", "Наименование",
            "Статус", "Тип изъятия", "Время сканирования", "Рабочее место"
        ])

    df_seizures = df_all[df_all["Тип изъятия"] != "НЕТ"] if not df_all.empty else df_all.copy()
    df_unscanned = df_all[df_all["Статус"] == "НЕ НАЙДЕН"] if not df_all.empty else df_all.copy()

    # Лист со штрихкодами, которых не было в накладной
    unknown_scans = db.query(ScanLog).filter(
        ScanLog.shipment_id == shipment_id,
        ScanLog.status == "NOT_IN_DB"
    ).all()

    data_unknown = [{
        "Отсканированный код": s.scanned_code,
        "Время сканирования": s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "",
        "Рабочее место": s.desk_id or ""
    } for s in unknown_scans]
    df_unknown = pd.DataFrame(data_unknown)

    # 4. Запись в Excel с автофильтром и подгонкой ширины
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_all.to_excel(writer, sheet_name="Все товары", index=False)
        df_seizures.to_excel(writer, sheet_name="Все Изъятия", index=False)
        df_unscanned.to_excel(writer, sheet_name="Не отсканировано", index=False)

        if not df_unknown.empty:
            df_unknown.to_excel(writer, sheet_name="Не было в базе", index=False)

        workbook = writer.book
        for ws in workbook.worksheets:
            # Включаем фильтры-стрелочки на шапку
            if ws.max_row > 1:
                ws.auto_filter.ref = ws.dimensions

            # Автоматическая ширина ячеек, чтобы текст не обрезался
            for col in ws.columns:
                max_len = 0
                col_letter = col[0].column_letter
                for cell in col:
                    val = str(cell.value or '')
                    if len(val) > max_len:
                        max_len = len(val)
                ws.column_dimensions[col_letter].width = max(max_len + 3, 14)

    output.seek(0)
    return output