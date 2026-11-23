from pydantic import BaseModel
from typing import Optional


class ScanRequest(BaseModel):
    code: str
    desk_id: Optional[str] = "PC1"


class ScanResponse(BaseModel):
    status: str
    sound: Optional[str] = None
    sound_phrase: Optional[str] = None
    banner_text: Optional[str] = ""
    banner_color: Optional[str] = "secondary"

    box_number: Optional[str] = None
    box_scanned: Optional[int] = 0
    box_total: Optional[int] = 0
    item_title: Optional[str] = None
    sticker: Optional[str] = None

    # Поля для синхронизации всех ПК
    global_total_items: int = 0
    global_scanned_items: int = 0
    global_total_seizures: int = 0
    global_scanned_seizures: int = 0

    class Config:
        from_attributes = True
