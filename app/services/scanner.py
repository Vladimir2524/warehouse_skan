from sqlalchemy.orm import Session
from datetime import datetime
from app.models import Item
from app.schemas import ScanRequest, ScanResponse

def process_scan(db: Session, req: ScanRequest) -> ScanResponse:
    code = req.sticker_code.strip()

    # 1. Ошибка формата ШК
    if not code.startswith('*') or len(code) < 7:
        return ScanResponse(
            status="INVALID",
            message="Неверный формат штрихкода",
            sound_file="invalid.mp3",
            sound_phrase="Не тот штрихкод"
        )

    item = db.query(Item).filter(
        Item.shipment_id == req.shipment_id,
        Item.sticker_code == code
    ).first()

    # 2. Нет в базе
    if not item:
        return ScanResponse(
            status="NOT_IN_DB",
            message=f"Товар {code} не найден",
            sound_file="not_in_db.mp3",
            sound_phrase="Нет в базе"
        )

    box_items = db.query(Item).filter(
        Item.shipment_id == req.shipment_id,
        Item.box_number == item.box_number
    ).all()

    # 3. Повторный скан
    if item.is_scanned:
        b_total = len(box_items)
        b_scanned = sum(1 for i in box_items if i.is_scanned)
        b_seizures = sum(1 for i in box_items if i.seizure_type != 'NONE')
        b_seizures_found = sum(1 for i in box_items if i.is_scanned and i.seizure_type != 'NONE')

        s_file = "repeat_seizure.mp3" if item.seizure_type != 'NONE' else "repeat.mp3"
        s_phrase = "Повтор. Изъятие" if item.seizure_type != 'NONE' else "Повторный скан"

        return ScanResponse(
            status="REPEAT",
            message=f"Повторный скан товара {code}",
            sound_file=s_file,
            sound_phrase=s_phrase,
            title=item.title,
            box_number=item.box_number,
            box_total=b_total,
            box_scanned=b_scanned,
            box_seizures_total=b_seizures,
            box_seizures_found=b_seizures_found
        )

    # 4. Успешный новый скан
    item.is_scanned = True
    item.scanned_at = datetime.utcnow()
    item.scanned_by_desk = req.desk_id
    db.commit()

    b_total = len(box_items)
    b_scanned = sum(1 for i in box_items if i.is_scanned)
    b_seizures = sum(1 for i in box_items if i.seizure_type != 'NONE')
    b_seizures_found = sum(1 for i in box_items if i.is_scanned and i.seizure_type != 'NONE')

    if item.seizure_type == 'SEIZURE_PD':
        s_file = "seizure_pd.mp3"
        s_phrase = "Изъятие Персональные Данные"
        status = "SEIZURE_PD"
    elif item.seizure_type == 'SEIZURE':
        s_file = "seizure.mp3"
        s_phrase = "Изъятие"
        status = "SEIZURE"
    else:
        s_file = "ok.mp3"
        s_phrase = f"В коробке {b_scanned} место"
        status = "OK"

    # Считаем общие цифры по всей партии (shipment)
    shipment_total = db.query(Item).filter(Item.shipment_id == req.shipment_id).count()
    shipment_scanned = db.query(Item).filter(Item.shipment_id == req.shipment_id, Item.is_scanned == True).count()

    return ScanResponse(
        status=status,
        message="Успешно",
        sound_file=s_file,
        sound_phrase=s_phrase,
        title=item.title,
        box_number=item.box_number,
        box_total=b_total,
        box_scanned=b_scanned,
        box_seizures_total=b_seizures,
        box_seizures_found=b_seizures_found,
        # Передаем общие цифры
        shipment_total=shipment_total,
        shipment_scanned=shipment_scanned
    )

