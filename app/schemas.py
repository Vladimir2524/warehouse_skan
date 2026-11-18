from pydantic import BaseModel
from typing import Optional

class ScanRequest(BaseModel):
    code: str
    desk_id: str = "PC1"

class ScanResponse(BaseModel):
    status: str
    message: str
    sound_file: str
    sound_phrase: Optional[str] = None
    title: Optional[str] = None
    box_number: Optional[str] = None
    box_total: int = 0
    box_scanned: int = 0
    box_seizures_total: int = 0
    box_seizures_found: int = 0
    box_place_text: Optional[str] = None
    shipment_total: int = 0
    shipment_scanned: int = 0
    shipment_seizures_total: int = 0
    shipment_seizures_found: int = 0
    shipment_name: Optional[str] = None
