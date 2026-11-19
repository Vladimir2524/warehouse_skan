from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Item, ScanLog, Shipment
from app.schemas import ScanResponse

def process_scan(db: Session, code: str, desk_id: str = "PC1") -> ScanResponse:
    cleaned = code.strip()

    # 1. Проверка формата: начинается с * и длина >= 8
    if not cleaned.startswith("*") or len(cleaned) < 8:
        return ScanResponse(
            status="INVALID",
            sound="invalid",
            sound_phrase=None,
            banner_text="НЕ ТОТ ШТРИХКОД",
            banner_color="danger"
        )

    # 2. Ищем товар в активной партии
    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    shipment_id = active_shipment.id if active_shipment else 1

    item = db.query(Item).filter(
        Item.shipment_id == shipment_id,
        Item.sticker == cleaned
    ).first()

    # Если по текущей партии не найден, ищем в любой последней
    if not item:
        item = db.query(Item).filter(Item.sticker == cleaned).order_by(Item.id.desc()).first()
        if item:
            shipment_id = item.shipment_id

    # 3. Товара нет в базе
    if not item:
        log = ScanLog(
            shipment_id=shipment_id,
            scanned_code=cleaned,
            status="NOT_IN_DB",
            desk_id=desk_id
        )
        db.add(log)
        db.commit()
        return ScanResponse(
            status="NOT_IN_DB",
            sound="not_in_db",
            sound_phrase=None,
            banner_text="НЕТ В БАЗЕ",
            banner_color="danger"
        )

    box_num = item.box_number

    # 4. Проверяем состояние коробки
    box_total = db.query(Item).filter(
        Item.shipment_id == shipment_id,
        Item.box_number == box_num
    ).count()

    # 5. Обработка ПОВТОРНОГО сканирования
    if item.is_scanned:
        box_scanned = db.query(Item).filter(
            Item.shipment_id == shipment_id,
            Item.box_number == box_num,
            Item.is_scanned == True
        ).count()

        # ЕСЛИ КОРОБКА УЖЕ ПОЛНАЯ — повторяем "Коробка полная!"
        if box_scanned >= box_total and box_total > 0:
            return ScanResponse(
                status="BOX_COMPLETE",
                sound="box_complete",
                sound_phrase="Коробка полная!",
                banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned} из {box_total})",
                banner_color="success",
                box_number=box_num,
                box_scanned=box_scanned,
                box_total=box_total,
                box_places_left=0,
                item_title=item.title,
                sticker=item.sticker
            )

        # Если это повтор изъятия — играем специальный звук repeat_seizure!
        if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
            return ScanResponse(
                status="REPEAT_SEIZURE",
                sound="repeat_seizure",
                sound_phrase=None,
                banner_text=f"ПОВТОР: ИЗЪЯТИЕ №кор: {box_num}",
                banner_color="danger",
                box_number=box_num,
                item_title=item.title,
                sticker=item.sticker
            )

        # Обычный повтор
        return ScanResponse(
            status="REPEAT",
            sound="repeat",
            sound_phrase=None,
            banner_text=f"ПОВТОР: ТОВАР УЖЕ БЫЛ №кор: {box_num}",
            banner_color="warning",
            box_number=box_num,
            box_scanned=box_scanned,
            box_total=box_total,
            box_places_left=max(0, box_total - box_scanned),
            item_title=item.title,
            sticker=item.sticker
        )

    # 6. ПЕРВОЕ УСПЕШНОЕ СКАНИРОВАНИЕ — фиксируем дату и рабочее место!
    item.is_scanned = True
    item.scanned_at = datetime.utcnow()
    item.desk_id = desk_id

    log = ScanLog(
        shipment_id=shipment_id,
        item_id=item.id,
        scanned_code=cleaned,
        status="SCANNED",
        desk_id=desk_id
    )
    db.add(log)
    db.commit()

    # Считаем коробку после обновления
    box_scanned = db.query(Item).filter(
        Item.shipment_id == shipment_id,
        Item.box_number == box_num,
        Item.is_scanned == True
    ).count()

    places_left = max(0, box_total - box_scanned)

    # 7. Если это ИЗЪЯТИЕ
    if item.seizure_type in ["SEIZURE", "SEIZURE_PD"]:
        snd = "seizure_pd" if item.seizure_type == "SEIZURE_PD" else "seizure"
        return ScanResponse(
            status="SEIZURE",
            sound=snd,
            sound_phrase=None,
            banner_text=f"ИЗЪЯТИЕ №кор: {box_num} ({box_scanned} из {box_total})",
            banner_color="danger",
            box_number=box_num,
            box_scanned=box_scanned,
            box_total=box_total,
            box_places_left=places_left,
            item_title=item.title,
            sticker=item.sticker
        )

    # 8. Если коробка заполнилась
    if box_scanned >= box_total and box_total > 0:
        return ScanResponse(
            status="BOX_COMPLETE",
            sound="box_complete",
            sound_phrase="Коробка полная!",
            banner_text=f"КОРОБКА ПОЛНАЯ №кор: {box_num} ({box_scanned} из {box_total})",
            banner_color="success",
            box_number=box_num,
            box_scanned=box_scanned,
            box_total=box_total,
            box_places_left=0,
            item_title=item.title,
            sticker=item.sticker
        )

    # 9. Обычный чистый товар (озвучка оставшихся мест)
    phrase = f"В коробке {places_left} место" if places_left == 1 else (
             f"В коробке {places_left} места" if 1 < places_left < 5 else f"В коробке {places_left} мест")

    return ScanResponse(
        status="OK",
        sound="ok",
        sound_phrase=phrase,
        banner_text=f"ОК №кор: {box_num} ({box_scanned} из {box_total})",
        banner_color="success",
        box_number=box_num,
        box_scanned=box_scanned,
        box_total=box_total,
        box_places_left=places_left,
        item_title=item.title,
        sticker=item.sticker
    )
