import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app import models
from app.schemas import ScanResponse


class Status:
    OK = "OK"
    INVALID = "INVALID"
    NOT_IN_DB = "NOT_IN_DB"
    REPEAT = "REPEAT"
    REPEAT_SEIZURE = "REPEAT_SEIZURE"
    SEIZURE = "SEIZURE"
    SEIZURE_PD = "SEIZURE_PD"
    BOX_COMPLETE = "BOX_COMPLETE"


def process_scan(db: Session, code: str, desk_id: str = "PC1") -> ScanResponse:
    # 1. Валидация формата (должен начинаться со звездочки и быть не короче 8 символов)
    if not code.startswith('*') or len(code) < 8:
        return ScanResponse(
            status=Status.INVALID,
            message=f"НЕ ТОТ ШТРИХКОД: {code}",
            sound_file="invalid.mp3",
            sound_phrase="Не тот штрихкод"
        )


    # 2. Поиск товара в базе
    item = db.query(models.Item).filter(models.Item.sticker_code == code).first()
    if not item:
        return ScanResponse(
            status=Status.NOT_IN_DB,
            message=f"НЕТ В БАЗЕ: {code}",
            sound_file="not_in_db.mp3",
            sound_phrase="Нет в базе"
        )

    # Инфо о партии для шапки
    shipment = db.query(models.Shipment).filter(models.Shipment.id == item.shipment_id).first()
    shipment_name = shipment.filename if shipment else "Неизвестная партия"

    # Считаем актуальную статистику по партии
    shipment_total = db.query(func.count(models.Item.id)).filter(models.Item.shipment_id == item.shipment_id).scalar()
    shipment_scanned = db.query(func.count(models.Item.id)).filter(models.Item.shipment_id == item.shipment_id,
                                                                   models.Item.is_scanned == True).scalar()
    s_total = db.query(func.count(models.Item.id)).filter(models.Item.shipment_id == item.shipment_id,
                                                          models.Item.seizure_type != 'NONE').scalar()
    s_found = db.query(func.count(models.Item.id)).filter(models.Item.shipment_id == item.shipment_id,
                                                          models.Item.seizure_type != 'NONE',
                                                          models.Item.is_scanned == True).scalar()

    if item.is_scanned:
        if item.seizure_type != 'NONE':
            status = Status.REPEAT_SEIZURE
            sound = "repeat_seizure.mp3"
            msg = f"ПОВТОР: ИЗЪЯТИЕ! №кор: {item.box_number}"
        else:
            status = Status.REPEAT
            sound = "repeat.mp3"
            msg = f"УЖЕ СКАНИРОВАЛИ №кор: {item.box_number}"

    # 4. Первый скан: сохраняем факт сканирования
    item.is_scanned = True
    item.scanned_at = datetime.datetime.now()
    item.scanned_by_desk = desk_id
    db.commit()

    # Обновляем счетчик отсканированных после коммита
    shipment_scanned += 1
    if item.seizure_type != 'NONE':
        s_found += 1

    # 5. Статистика по коробке
    b_total = db.query(func.count(models.Item.id)).filter(
        models.Item.shipment_id == item.shipment_id,
        models.Item.box_number == item.box_number
    ).scalar()

    b_scanned = db.query(func.count(models.Item.id)).filter(
        models.Item.shipment_id == item.shipment_id,
        models.Item.box_number == item.box_number,
        models.Item.is_scanned == True
    ).scalar()

    # 6. Определение звука и статуса
    place_text = f"{b_scanned} из {b_total}"

    if item.seizure_type in ['SEIZURE', 'SEIZURE_PD']:
        status = Status.SEIZURE_PD if item.seizure_type == 'SEIZURE_PD' else Status.SEIZURE
        sound = "seizure_pd.mp3" if item.seizure_type == 'SEIZURE_PD' else "seizure.mp3"
        msg = f"ИЗЪЯТИЕ №кор: {item.box_number}"
    elif b_scanned == b_total:
        status = Status.BOX_COMPLETE
        sound = "ok.mp3"
        msg = f"КОРОБКА ПОЛНАЯ №кор: {item.box_number} ({place_text})"
    else:
        status = Status.OK
        sound = "ok.mp3"
        msg = f"ОК №кор: {item.box_number} ({place_text})"

    return ScanResponse(
        status=status,
        message=msg,
        sound_file=sound,
        sound_phrase=f"В коробке {b_scanned} место",
        title=item.title,
        box_number=item.box_number,
        box_total=b_total,
        box_scanned=b_scanned,
        box_place_text=place_text,
        shipment_total=shipment_total,
        shipment_scanned=shipment_scanned,
        shipment_seizures_total=s_total,
        shipment_seizures_found=s_found,
        shipment_name=shipment_name
    )

