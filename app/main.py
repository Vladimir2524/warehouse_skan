import os
from fastapi import FastAPI, Depends, UploadFile, File, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import engine, Base, get_db
from app.models import Shipment, Item, ScanLog
from app.schemas import ScanRequest, ScanResponse
from app.services.scanner import process_scan
from app.services.excel_parser import parse_excel_to_db
from app.services.reports import generate_excel_report

# Создаем таблицы в БД, если их нет
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WarehouseScanner")

# Подключение статики и шаблонов
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, db: Session = Depends(get_db)):
    active_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"active_shipment": active_shipment}
    )


@app.post("/api/shipments/upload")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы Excel (.xlsx, .xls)")

    content = await file.read()
    shipment_id, total_rows, seizures_count = parse_excel_to_db(content, file.filename, db)

    return {
        "status": "ok",
        "shipment_id": shipment_id,
        "filename": file.filename,
        "total_items": total_rows,
        "seizures_count": seizures_count
    }


@app.post("/api/scan", response_model=ScanResponse)
def scan_item(req: ScanRequest, db: Session = Depends(get_db)):
    return process_scan(
        db,
        code=req.code,
        desk_id=req.desk_id or "PC1",
        is_defect=getattr(req, "is_defect", False)
    )


@app.get("/api/shipments/last/report")
def download_last_report(db: Session = Depends(get_db)):
    last_shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()
    if not last_shipment:
        raise HTTPException(status_code=404, detail="Нет загруженных партий")

    excel_stream = generate_excel_report(db, shipment_id=last_shipment.id)
    filename = f"report_shipment_{last_shipment.id}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@app.get("/api/shipments")
def get_all_shipments(db: Session = Depends(get_db)):
    shipments = db.query(Shipment).order_by(Shipment.id.desc()).all()
    result = []
    for s in shipments:
        total = db.query(Item).filter(Item.shipment_id == s.id).count()
        scanned = db.query(Item).filter(Item.shipment_id == s.id, Item.is_scanned == True).count()
        defects = db.query(Item).filter(Item.shipment_id == s.id, Item.is_defect == True).count()
        seizures = db.query(Item).filter(Item.shipment_id == s.id, Item.seizure_type != "NONE").count()
        result.append({
            "id": s.id,
            "filename": s.filename,
            "date": s.created_at.strftime("%d.%m.%Y %H:%M") if s.created_at else "—",
            "total": total,
            "scanned": scanned,
            "defects": defects,
            "seizures": seizures
        })
    return result


@app.get("/api/shipments/{shipment_id}/report")
def download_specific_report(shipment_id: int, db: Session = Depends(get_db)):
    shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Партия не найдена")

    excel_stream = generate_excel_report(db, shipment_id=shipment.id)
    filename = f"report_party_{shipment_id}.xlsx"

    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )