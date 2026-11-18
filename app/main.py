import os
import shutil
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.schemas import ScanRequest, ScanResponse
from app.services.scanner import process_scan
from app.services.excel_parser import bootstrap_excel_to_db
from app.services.reports import generate_excel_report

app = FastAPI(title="WarehouseScanner API", version="1.0")

os.makedirs("app/static/sounds", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

templates = Jinja2Templates(directory="app/templates")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", response_class=HTMLResponse)
def get_ui(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")


# Загрузка реестра отгрузки
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
        raise HTTPException(status_code=500, detail=f"Ошибка парсинга: {str(e)}")


# Эндпоинт сканирования (строго принимает JSON от index.html)
@app.post("/api/scan", response_model=ScanResponse)
def scan_code(req: ScanRequest, db: Session = Depends(get_db)):
    return process_scan(db, req.code, req.desk_id)


# Скачивание отчета по ID или по последней партии
@app.get("/api/shipments/{shipment_id}/report")
@app.get("/api/shipments/last/report")
def download_report(shipment_id: int | None = None, db: Session = Depends(get_db)):
    if shipment_id:
        shipment = db.query(models.Shipment).filter(models.Shipment.id == shipment_id).first()
    else:
        shipment = db.query(models.Shipment).order_by(models.Shipment.id.desc()).first()

    if not shipment:
        raise HTTPException(status_code=404, detail="Нет загруженных партий в базе")

    excel_bytes = generate_excel_report(db, shipment.id)
    safe_filename = f"Report_Shipment_{shipment.id}.xlsx"

    return StreamingResponse(
        excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
    )