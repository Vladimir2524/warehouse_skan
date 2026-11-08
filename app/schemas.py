from pydantic import BaseModel
from typing import Optional

class ScanRequest(BaseModel):
    shipment_id: int
    sticker_code: str
    desk_id: Optional[str] = "Касса 1"

class ScanResponse(BaseModel):
    status: str
    message: str
    sound_file: str      # Имя MP3 файла (например: "seizure_pd.mp3")
    sound_phrase: str    # Текст на экране
    title: Optional[str] = None
    box_number: Optional[str] = None
    box_total: int = 0
    box_scanned: int = 0
    box_seizures_total: int = 0
    box_seizures_found: int = 0
