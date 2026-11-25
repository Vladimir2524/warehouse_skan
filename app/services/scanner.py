from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Shipment, Item, ScanLog
from app.schemas import ScanResponse


def is_seizure(item: Item) -> bool:
    """Проверка, является ли товар изъятием"""
    if not item.seizure_type:
        return False
    st = getattr(item.seizure_type, "value", str(item.seizure_type)).upper()
    return st not in ("NONE", "", "НЕТ")


def is_seizure_pd(item: Item) -> bool:
    """Проверка на изъятие Персональных Данных (ПД)"""
    if not item.seizure_type:
        return False
    st = getattr(item.seizure_type, "value", str(item.seizure_type)).upper()
    return "PD" in st or "ПД" in st


def process_scan(
    db: Session,
    code: str,
    desk_id: str = "PC1",
    is_defect: bool = False
) -> ScanResponse:
    code = code.strip()

    # 1. Получаем последнюю активную партию
    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    if not active_shipment:
        return ScanResponse(
            status="ОШИБКА",
            sound="ok" if is_defect else "not_in_db",
            sound_phrase=None,
            banner_text="БАЗА ДАННЫХ ПУСТА! ЗАГРУЗИТЕ EXCEL",
            banner_color="#dc3545",
            box_number="—",
            box_scanned=0,
            box_total=0,
            box_places_left=0,
            item_title="—",
            global_total_items=0,
            global_scanned_items=0,
            global_total_seizures=0,
            global_scanned_seizures=0,
            message="База пуста"
        )

    # 2. Глобальные счетчики
    total_items = db.query(Item).filter(Item.shipment_id == active_shipment.id).count()
    scanned_items = db.query(Item).filter(
        Item.shipment_id == active_shipment.id,
        Item.is_scanned == True
    ).count()

    total_seizures = db.query(Item).filter(
        Item.shipment_id == active_shipment.id,
        Item.seizure_type.isnot(None),
        Item.seizure_type != "NONE"
    ).count()

    scanned_seizures = db.query(Item).filter(
        Item.shipment_id == active_shipment.id,
        Item.is_scanned == True,
        Item.seizure_type.isnot(None),
        Item.seizure_type != "NONE"
    ).count()

    # 3. Ищем товар по базе
    item = db.query(Item).filter(
        Item.shipment_id == active_shipment.id,
        or_(Item.barcode == code, Item.sticker == code)
    ).first()

    # ========================================================
    # РЕЖИМ БРАКА (F2) — ЛЮБОЙ СКАН: СТРОГО ok.mp3, ГОЛОС МОЛЧИТ!
    # ========================================================
    if is_defect:
        if not item:
            # Заяц в браке: пишем в лог, играем ok, красная табличка "ТОВАРА НЕТ В БАЗЕ"
            db.add(ScanLog(
                shipment_id=active_shipment.id,
                scanned_code=code,
                status="БРАК",
                desk_id=desk_id
            ))
            db.commit()
            return ScanResponse(
                status="БРАК",
                sound="ok",
                sound_phrase=None,
                banner_text="ТОВАРА НЕТ В БАЗЕ",
                banner_color="#dc3545",
                box_number="—",
                box_scanned=0,
                box_total=0,
                box_places_left=0,
                item_title="Товар не найден в базе (Брак)",
                global_total_items=total_items,
                global_scanned_items=scanned_items,
                global_total_seizures=total_seizures,
                global_scanned_seizures=scanned_seizures,
                message="Брак"
            )

        # Товар есть в базе
        item.is_scanned = True
        item.is_defect = True
        item.scanned_at = datetime.utcnow()
        item.desk_id = desk_id

        db.add(ScanLog(
            shipment_id=active_shipment.id,
            item_id=item.id,
            scanned_code=code,
            status="БРАК",
            desk_id=desk_id
        ))
        db.commit()

        box_num = item.box_number or "—"
        box_total = db.query(Item).filter(Item.shipment_id == active_shipment.id, Item.box_number == item.box_number).count()
        box_scanned = db.query(Item).filter(Item.shipment_id == active_shipment.id, Item.box_number == item.box_number, Item.is_scanned == True).count()

        return ScanResponse(
            status="БРАК",
            sound="ok",
            sound_phrase=None,
            banner_text=f"БРАК №{box_num} ({box_scanned}/{box_total})",
            banner_color="#dc3545",
            box_number=str(box_num),
            box_scanned=box_scanned,
            box_total=box_total,
            box_places_left=max(0, box_total - box_scanned),
            item_title=item.title,
            sticker=item.sticker,
            global_total_items=total_items,
            global_scanned_items=scanned_items,
            global_total_seizures=total_seizures,
            global_scanned_seizures=scanned_seizures,
            message="Брак"
        )

    # ========================================================
    # ОБЫЧНЫЙ РЕЖИМ 1: ТОВАР НЕ НАЙДЕН (ЗАЯЦ)
    # ========================================================
    if not item:
        db.add(ScanLog(
            shipment_id=active_shipment.id,
            scanned_code=code,
            status="НЕТ В БАЗЕ",
            desk_id=desk_id
        ))
        db.commit()
        return ScanResponse(
            status="НЕТ В БАЗЕ",
            sound="not_in_db",
            sound_phrase=None,
            banner_text="ЗАЯЦ! ТОВАРА НЕТ В БАЗЕ!",
            banner_color="#dc3545",
            box_number="—",
            box_scanned=0,
            box_total=0,
            box_places_left=0,
            item_title="Товар не числится в текущей поставке",
            global_total_items=total_items,
            global_scanned_items=scanned_items,
            global_total_seizures=total_seizures,
            global_scanned_seizures=scanned_seizures,
            message="Товар не найден"
        )

    # Коробка текущего товара
    box_num = item.box_number or "—"
    box_query = db.query(Item).filter(
        Item.shipment_id == active_shipment.id,
        Item.box_number == item.box_number
    )
    box_total = box_query.count()

    # ========================================================
    # ОБЫЧНЫЙ РЕЖИМ 2: ПОВТОРНЫЙ СКАН
    # ========================================================
    if item.is_scanned:
        box_scanned = box_query.filter(Item.is_scanned == True).count()
        box_left = max(0, box_total - box_scanned)

        item_seizure = is_seizure(item)
        sound_name = "repeat_seizure" if item_seizure else "repeat"
        status_text = "ПОВТОР ИЗЪЯТИЯ" if item_seizure else "ПОВТОР"
        color = "#dc3545" if item_seizure else "#ffc107"

        db.add(ScanLog(
            shipment_id=active_shipment.id,
            item_id=item.id,
            scanned_code=code,
            status=status_text,
            desk_id=desk_id
        ))
        db.commit()

        return ScanResponse(
            status=status_text,
            sound=sound_name,
            sound_phrase=None,
            banner_text=f"{status_text} №{box_num} ({box_scanned}/{box_total})",
            banner_color=color,
            box_number=str(box_num),
            box_scanned=box_scanned,
            box_total=box_total,
            box_places_left=box_left,
            item_title=item.title,
            sticker=item.sticker,
            global_total_items=total_items,
            global_scanned_items=scanned_items,
            global_total_seizures=total_seizures,
            global_scanned_seizures=scanned_seizures,
            message="Повтор"
        )

    # ========================================================
    # ОБЫЧНЫЙ РЕЖИМ 3: УСПЕШНЫЙ ПЕРВЫЙ СКАН
    # ========================================================
    item.is_scanned = True
    item.scanned_at = datetime.utcnow()
    item.desk_id = desk_id

    box_scanned_now = box_query.filter(Item.is_scanned == True).count() + 1
    box_left_now = max(0, box_total - box_scanned_now)

    scanned_items += 1
    item_seizure = is_seizure(item)
    item_seizure_pd = is_seizure_pd(item)

    if item_seizure:
        scanned_seizures += 1

    sound = None
    sound_phrase = None

    is_first_in_box = (box_scanned_now == 1)
    is_box_complete = (box_scanned_now >= box_total)

    if is_box_complete:
        sound = "box_complete"
        if item_seizure_pd:
            sound_phrase = "изъятие ПД коробка полная"
        elif item_seizure:
            sound_phrase = "изъятие коробка полная"
        else:
            sound_phrase = "коробка полная"
    elif is_first_in_box:
        if item_seizure:
            sound = None
            prefix = "изъятие ПД" if item_seizure_pd else "изъятие"
            sound_phrase = f"{prefix} {box_total}"
        else:
            sound = "ok"
            sound_phrase = str(box_total)
    else:
        if item_seizure_pd:
            sound = "seizure_pd"
        elif item_seizure:
            sound = "seizure"
        else:
            sound = "ok"
        sound_phrase = None

    if item_seizure:
        status_text = "ИЗЪЯТИЕ ПД" if item_seizure_pd else "ИЗЪЯТИЕ"
        banner_color = "#dc3545"
    else:
        status_text = "ОТСКАНИРОВАН"
        banner_color = "#198754"

    banner_text = f"{status_text} №{box_num} ({box_scanned_now}/{box_total})"

    db.add(ScanLog(
        shipment_id=active_shipment.id,
        item_id=item.id,
        scanned_code=code,
        status=status_text,
        desk_id=desk_id
    ))
    db.commit()

    return ScanResponse(
        status=status_text,
        sound=sound,
        sound_phrase=sound_phrase,
        banner_text=banner_text,
        banner_color=banner_color,
        box_number=str(box_num),
        box_scanned=box_scanned_now,
        box_total=box_total,
        box_places_left=box_left_now,
        item_title=item.title,
        sticker=item.sticker,
        global_total_items=total_items,
        global_scanned_items=scanned_items,
        global_total_seizures=total_seizures,
        global_scanned_seizures=scanned_seizures,
        message="Успешно отсканировано"
    )

