import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ScanRequest, ScanResponse
from app.services.scanner import process_scan
from app.services.excel_parser import bootstrap_excel_to_db
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="WarehouseScanner API", version="1.0")
os.makedirs("app/static/sounds", exist_ok=True)
templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)


# Главная страница с веб-интерфейсом
@app.get("/", response_class=HTMLResponse)
def get_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# Эндпоинт для загрузки Excel отгрузки
@app.post("/api/shipments/upload")
def upload_shipment(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Файл должен быть Excel (.xlsx/.xls)")

    file_path = f"uploads/{file.filename}"

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        shipment_id = bootstrap_excel_to_db(db, file_path, file.filename)
        return {
            "status": "success",
            "shipment_id": shipment_id,
            "filename": file.filename,
            "message": "Отгрузка успешно загружена в базу"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга файла: {str(e)}")


# Главный эндпоинт СКАНИРОВАНИЯ
@app.post("/api/scan", response_model=ScanResponse)
def scan_code(req: ScanRequest, db: Session = Depends(get_db)):
    return process_scan(db, req)