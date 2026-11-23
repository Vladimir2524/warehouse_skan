from datetime import datetime
from sqlalchemy.orm import Session
from app.models import Item, ScanLog, Shipment
from app.schemas import ScanResponse


def process_scan(db: Session, code: str, desk_id: str = "PC1") -> ScanResponse:
    clean_code = code.strip()
    now = datetime.utcnow()

    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    if not active_shipment:
        return ScanResponse(status="ОШИБКА", sound="invalid", banner_text="БАЗА ПУСТА", banner_color="danger")

    shipment_id = active_shipment.id

    def get_global_stats():
        total_items = db.query(Item).filter(Item.shipment_id == shipment_id).count()
        scanned_items = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True).count()
        total_seizures = db.query(Item).filter(Item.shipment_id == shipment_id, Item.seizure_type != "NONE").count()
        scanned_seizures = db.query(Item).filter(Item.shipment_id == shipment_id, Item.is_scanned == True,
                                                 Item.seizure_type != "NONE").count()
        return total_items, scanned_items, total_seizures, scanned_seizures

    # 1. Поиск товара
    search_code = clean_code.replace("*", "") if clean_code.startswith("*") else clean_code
    item = db.query(Item).filter(
        Item.shipment_id == shipment_id,
        (Item.barcode == search_code) | (Item.sticker == search_code) |
        (Item.barcode == clean_code) | (Item.sticker == clean_code)
    ).first()

    # 2. НЕТ В БАЗЕ
    if not item:
        log = ScanLog(shipment_id=shipment_id, scanned_code=clean_code, status="НЕТ В БАЗЕ", desk_id=desk_id)
        db.add(log)
        db.commit()
        g_total, g_scanned, g_s_total, g_s_scanned = get_global_stats()
        return ScanResponse(
            status="НЕТ В БАЗЕ", sound="not_in_db", sound_file="not_in_db", sound_phrase=None,
            banner_text="НЕТ В БАЗЕ!", banner_color="danger",
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # 3. DEBOUNCE (дребезг сканера)
    if item.is_scanned and item.scanned_at and (now - item.scanned_at).total_seconds() < 0.35:
        g_total, g_scanned, g_s_total, g_s_scanned = get_global_stats()
        return ScanResponse(
            status="ОТМЕНА", sound=None, sound_phrase=None,
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # 4. ПОВТОР (ДАЖЕ ЕСЛИ КОРОБКА БЫЛА ПОЛНОЙ!)
    if item.is_scanned:
        is_seizure = item.seizure_type != "NONE"
        status = "ПОВТОР ИЗЪЯТИЯ" if is_seizure else "ПОВТОР"
        sound_to_play = "repeat_seizure" if is_seizure else "repeat"

        box_total = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == item.box_number).count()
        box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == item.box_number,
                                            Item.is_scanned == True).count()
        g_total, g_scanned, g_s_total, g_s_scanned = get_global_stats()

        # ТОЛЬКО звук повтора, НИКАКИХ фраз о полной коробке!
        return ScanResponse(
            status=status, sound=sound_to_play, sound_file=sound_to_play, sound_phrase=None,
            banner_text=f"{status} №{item.box_number} ({box_scanned}/{box_total})",
            banner_color="warning",
            box_number=item.box_number, box_scanned=box_scanned, box_total=box_total,
            box_places_left=max(0, box_total - box_scanned),
            item_title=item.title, sticker=item.sticker,
            global_total_items=g_total, global_scanned_items=g_scanned,
            global_total_seizures=g_s_total, global_scanned_seizures=g_s_scanned
        )

    # 5. ПЕРВИЧНЫЙ СКАН (ТОВАР ПРИНЯТ)
    item.is_scanned = True
    item.scanned_at = now
    item.desk_id = desk_id
    db.commit()

    box_total = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == item.box_number).count()
    box_scanned = db.query(Item).filter(Item.shipment_id == shipment_id, Item.box_number == item.box_number,
                                        Item.is_scanned == True).count()
    is_seizure = item.seizure_type != "NONE"
    is_pd = "ПД" in (item.seizure_type or "")
    seizure_sound = "seizure_pd" if is_pd else "seizure"

    res_sound = "ok"
    res_phrase = None

    # --- ЖЕЛЕЗНАЯ ЛОГИКА ОЗВУЧКИ ---
    if box_scanned >= box_total and box_total > 1:
        # КОРОБКА ЗАПОЛНИЛАСЬ
        res_sound = "box_complete"
        res_phrase = "изъятие коробка полная" if is_seizure else "коробка полная"

    elif box_scanned == 1:
        # ПЕРВЫЙ СКАН В КОРОБКЕ (НАЧАЛО 1/Х)
        if box_total == 1:
            # Если коробка вообще состоит из 1 места
            res_sound = "box_complete"
            res_phrase = "изъятие коробка полная" if is_seizure else "коробка полная"
        else:
            if is_seizure:
                # ВАЖНО: Выключаем mp3, чтобы синтезатор СРАЗУ и без задержек сказал комбо!
                res_sound = None
                seizure_word = "изъятие ПД" if is_pd else "изъятие"
                res_phrase = f"{seizure_word} {box_total}"
            else:
                # Чистый первый скан: пик + число мест
                res_sound = "ok"
                res_phrase = str(box_total)
    else:
        # СЕРЕДИНА КОРОБКИ (2/X, 3/X и т.д.)
        if is_seizure:
            # Обычные изъятия в середине: играет наш MP3 голос из папки, синтезатор молчит!
            res_sound = seizure_sound
            res_phrase = None
        else:
            # Обычный чистый: просто пик ok.mp3
            res_sound = "ok"
            res_phrase = None

    # Баннер (Статус №Коробки X/Y)
    status_label = "ИЗЪЯТИЕ" if is_seizure else "ОТСКАНИРОВАН"
    banner_text = f"{status_label} №{item.box_number} ({box_scanned}/{box_total})"
    banner_color = "danger" if is_seizure else "success"

    log = ScanLog(shipment_id=shipment_id, item_id=item.id, scanned_code=clean_code, status=status_label,
                  desk_id=desk_id)
    db.add(log)
    db.commit()

    g_total, g_scanned, g_s_total, g_s_scanned = get_global_stats()

    return ScanResponse(
        status=status_label,
        sound=res_sound,
        sound_file=res_sound,
        sound_phrase=res_phrase,
        banner_text=banner_text,
        banner_color=banner_color,
        box_number=item.box_number,
        box_scanned=box_scanned,
        box_total=box_total,
        box_places_left=max(0, box_total - box_scanned),
        item_title=item.title,
        sticker=item.sticker,
        global_total_items=g_total,
        global_scanned_items=g_scanned,
        global_total_seizures=g_s_total,
        global_scanned_seizures=g_s_scanned
    )

