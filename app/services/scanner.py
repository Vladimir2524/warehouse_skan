from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Item, ScanLog, Shipment
from app.schemas import ScanResponse

def process_scan(db: Session, code: str, desk_id: str = "PC1") -> ScanResponse:
    cleaned = code.strip()

    # 1. Активная партия
    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    shipment_id = active_shipment.id if active_shipment else 1

    # Функция для получения глобальных счетчиков (синхронизация)
    def get_globals():
        total = db.query(Item).filter(Item.shipment_id == shipment_id).count()
        scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True).count()
        seiz_total = db.query(Item).filter(Item.shipment_id == shipment_id, Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])).count()
        seiz_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True, Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])).count()
        return total, scanned, seiz_total, seiz_scanned

    g_total, g_scanned, g_s_total, g_s_scanned = get_globals()

    # 2. Валидация штрихкода
    if not cleaned.startswith("*") or len(cleaned) < 8:
        return ScanResponse(
            status="INVALID", sound="invalid", banner_text="НЕ ТОТ ШТРИХКОД", banner_color="danger",
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # 3. Поиск товара
    item = db.query(Item).filter(Item.shipment_id == shipment_id, Item.sticker == cleaned).first()
    if not item:
        log = ScanLog(shipment_id=shipment_id, scanned_code=cleaned, status="NOT_IN_DB", desk_id=desk_id)
        db.add(log)
        db.commit()
        return ScanResponse(
            status="NOT_IN_DB", sound="not_in_db", banner_text="НЕТ В БАЗЕ", banner_color="danger",
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    box_num = item.box_number
    box_total = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num).count()

    # 4. ЛОГИКА ПОВТОРА
    if item.is_scanned:
        # Защита от дребезга (0.3 сек)
        if item.scanned_at and (datetime.utcnow() - item.scanned_at).total_seconds() < 0.3:
            return ScanResponse(
                status="SCANNED", sound=None, banner_text="УЖЕ БЫЛ", banner_color="secondary",
                global_total_items=g_total, global_scanned_items=g_scanned,
                global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
            )

        box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num, Item.is_scanned == True).count()

        if box_scanned >= box_total and box_total > 0:
            return ScanResponse(
                status="BOX_COMPLETE", sound=None, sound_phrase="Коробка полностью отсканирована!",
                banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned}/{box_total})", banner_color="success",
                global_total_items=g_total, global_scanned_items=g_scanned,
                global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
            )

        if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
            return ScanResponse(
                status="REPEAT_SEIZURE", sound="repeat_seizure", banner_text="ПОВТОР ИЗЪЯТИЯ", banner_color="danger",
                global_total_items=g_total, global_scanned_items=g_scanned,
                global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
            )

        return ScanResponse(
            status="REPEAT", sound="repeat", banner_text="ПОВТОР ТОВАРА", banner_color="warning",
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # 5. ПЕРВЫЙ УСПЕШНЫЙ СКАН
    item.is_scanned = True
    item.scanned_at = datetime.utcnow()
    item.desk_id = desk_id
    db.commit()

    # Пересчитываем глобальные после записи
    g_total, g_scanned, g_s_total, g_s_scanned = get_globals()
    box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == box_num, Item.is_scanned == True).count()

    # ПРИОРИТЕТ 1: ИЗЪЯТИЕ (Только сирена!)
    if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
        snd = "seizure_pd" if item.seizure_type == "SEIZURE_PD" else "seizure"
        return ScanResponse(
            status="SEIZURE", sound=snd, sound_phrase=None,
            banner_text=f"ИЗЪЯТИЕ №кор: {box_num} ({box_scanned}/{box_total})", banner_color="danger",
            item_title=item.title, sticker=item.sticker,
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # ПРИОРИТЕТ 2: КОРОБКА ЗАПОЛНИЛАСЬ
    if box_scanned >= box_total and box_total > 0:
        return ScanResponse(
            status="BOX_COMPLETE", sound=None, sound_phrase="Коробка полностью отсканирована!",
            banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned}/{box_total})", banner_color="success",
            item_title=item.title, sticker=item.sticker,
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # ПРИОРИТЕТ 3: ОЗВУЧКА ПЕРВОГО ТОВАРА
    phrase = str(box_total) if (box_scanned == 1 and box_total > 1) else None

    return ScanResponse(
        status="OK", sound="ok", sound_phrase=phrase,
        banner_text=f"ОК №кор: {box_num} ({box_scanned}/{box_total})", banner_color="success",
        item_title=item.title, sticker=item.sticker,
        global_total_items=g_total, global_scanned_items=g_scanned,
        global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
    )

