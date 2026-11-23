from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Item, ScanLog, Shipment
from app.schemas import ScanResponse

def process_scan(db: Session, code: str, desk_id: str = "PC1") -> ScanResponse:
    cleaned = code.strip()

    if not cleaned.startswith("*") or len(cleaned) < 8:
        return ScanResponse(status="INVALID", sound="invalid", banner_text="НЕ ТОТ ШТРИХКОД", banner_color="danger")

    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    shipment_id = active_shipment.id if active_shipment else 1

    item = db.query(Item).filter(Item.shipment_id == shipment_id, Item.sticker == cleaned).first()

    if not item:
        log = ScanLog(shipment_id=shipment_id, scanned_code=cleaned, status="NOT_IN_DB", desk_id=desk_id)
        db.add(log)
        db.commit()
        return ScanResponse(status="NOT_IN_DB", sound="not_in_db", banner_text="НЕТ В БАЗЕ", banner_color="danger")

    box_num = item.box_number
    box_total = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num).count()

    # --- ЛОГИКА ПОВТОРА ---
    if item.is_scanned:
        # Защита от дребезга (0.3 сек)
        if item.scanned_at and (datetime.utcnow() - item.scanned_at).total_seconds() < 0.3:
            return ScanResponse(status="SCANNED", sound=None, banner_text="УЖЕ БЫЛ", banner_color="secondary")

        box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num, Item.is_scanned == True).count()

        # ПРИОРИТЕТ 1: Если коробка уже полная (даже если это изъятие)
        if box_scanned >= box_total and box_total > 0:
            return ScanResponse(
                status="BOX_COMPLETE",
                sound=None,
                sound_phrase="Коробка полностью отсканирована!",
                banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned}/{box_total})",
                banner_color="success"
            )

        # ПРИОРИТЕТ 2: Повтор изъятия
        if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
            return ScanResponse(status="REPEAT_SEIZURE", sound="repeat_seizure", banner_text="ПОВТОР ИЗЪЯТИЯ", banner_color="danger")

        return ScanResponse(status="REPEAT", sound="repeat", banner_text="ПОВТОР ТОВАРА", banner_color="warning")

    # --- ПЕРВЫЙ СКАН ---
    item.is_scanned = True
    item.scanned_at = datetime.utcnow()
    item.desk_id = desk_id
    db.commit()

    box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num, Item.is_scanned == True).count()

    # ПРИОРИТЕТ 1: ИЗЪЯТИЕ (Всегда сирена, никакой болтовни про коробку!)
    if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
        snd = "seizure_pd" if item.seizure_type == "SEIZURE_PD" else "seizure"
        return ScanResponse(
            status="SEIZURE",
            sound=snd,
            sound_phrase=None, # ТИШИНА для голоса
            banner_text=f"ИЗЪЯТИЕ №кор: {box_num} ({box_scanned}/{box_total})",
            banner_color="danger"
        )

    # ПРИОРИТЕТ 2: КОРОБКА ЗАПОЛНИЛАСЬ
    if box_scanned >= box_total and box_total > 0:
        return ScanResponse(
            status="BOX_COMPLETE",
            sound=None,
            sound_phrase="Коробка полностью отсканирована!",
            banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned}/{box_total})",
            banner_color="success"
        )

    # ПРИОРИТЕТ 3: ОЗВУЧКА ПЕРВОГО ТОВАРА (если в коробке больше 1 места)
    phrase = None
    if box_scanned == 1 and box_total > 1:
        phrase = str(box_total)

    global_total = db.query(Item).filter(Item.shipment_id == shipment_id).count()
    global_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True).count()
    global_seiz_total = db.query(Item).filter(Item.shipment_id == shipment_id,
                                              Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])).count()
    global_seiz_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True,
                                                Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])).count()

    # И передаем их в ScanResponse (добавь эти поля в каждый return ScanResponse в файле)
    # Пример для финального return:
    return ScanResponse(
        status="OK",  # или другой статус
        sound="ok",
        sound_phrase=phrase,
        banner_text=f"ОК №кор: {box_num} ({box_scanned}/{box_total})",
        banner_color="success",
        global_total_items=global_total,
        global_scanned_items=global_scanned,
        global_total_seizures=global_seiz_total,
        global_scanned_seizures=global_seiz_scanned
    )

