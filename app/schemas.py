from pydantic import BaseModel
from typing import Optional

class ScanRequest(BaseModel):
    shipment_id: int
    sticker_code: str
    desk_id: Optional[str] = "Касса 1"


class ScanResponse(BaseModel):
    status: str
    message: str
    sound_file: str
    sound_phrase: str
    title: Optional[str] = None
    box_number: Optional[str] = None

    # Статистика КОРОБКИ (то, что у тебя сейчас)
    box_total: int = 0
    box_scanned: int = 0
    box_seizures_total: int = 0
    box_seizures_found: int = 0

    # Общая статистика ПАРТИИ (добавляем)
    shipment_total: int = 0
    shipment_scanned: int = 0
