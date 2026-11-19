from fastapi import FastAPI, Depends, UploadFile, File, Request
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

Base.metadata.create_all(bind=engine)

app = FastAPI(title="WarehouseScanner")

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
def index_page(request: Request):
    # Явно передаем именованные параметры request и name
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/shipments/current")
def get_current_shipment(db: Session = Depends(get_db)):
    shipment = db.query(Shipment).join(Item).order_by(Shipment.id.desc()).first()
    if not shipment:
        shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()

    if not shipment:
        return {"has_active": False}

    total_items = db.query(Item).filter(Item.shipment_id == shipment.id).count()
    scanned_items = db.query(Item).filter(Item.shipment_id == shipment.id, Item.is_scanned == True).count()

    total_seizures = db.query(Item).filter(
        Item.shipment_id == shipment.id,
        Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])
    ).count()

    scanned_seizures = db.query(Item).filter(
        Item.shipment_id == shipment.id,
        Item.is_scanned == True,
        Item.seizure_type.in_(["SEIZURE", "SEIZURE_PD"])
    ).count()

    recent_logs = db.query(ScanLog).filter(
        ScanLog.shipment_id == shipment.id
    ).order_by(ScanLog.id.desc()).limit(15).all()

    history = []
    for l in recent_logs:
        history.append({
            "code": l.scanned_code,
            "status": l.status,
            "time": l.created_at.strftime("%H:%M:%S") if l.created_at else ""
        })

    return {
        "has_active": True,
        "id": shipment.id,
        "filename": shipment.filename,
        "total_items": total_items,
        "scanned_items": scanned_items,
        "total_seizures": total_seizures,
        "scanned_seizures": scanned_seizures,
        "history": history
    }


@app.post("/api/scan", response_model=ScanResponse)
@app.post("/scan", response_model=ScanResponse)
def scan_barcode(payload: ScanRequest, db: Session = Depends(get_db)):
    return process_scan(db, payload.code, payload.desk_id)


@app.post("/api/shipments/upload")
@app.post("/upload-excel")
async def upload_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    shipment_id, total_rows, seizures_count = parse_excel_to_db(content, file.filename, db)
    return {
        "status": "success",
        "shipment_id": shipment_id,
        "total_rows": total_rows,
        "seizures_count": seizures_count
    }


@app.get("/api/shipments/last/report")
def download_last_report(db: Session = Depends(get_db)):
    shipment = db.query(Shipment).join(Item).order_by(Shipment.id.desc()).first()
    if not shipment:
        shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()

    ship_id = shipment.id if shipment else 1
    report_file = generate_excel_report(db, shipment_id=ship_id)

    filename = f"Report_Shipment_{ship_id}.xlsx"
    return StreamingResponse(
        report_file,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )