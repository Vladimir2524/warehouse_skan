import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from sqlalchemy.orm import Session
from app.models import Item, ScanLog, Shipment

def generate_excel_report(db: Session, shipment_id: int = None) -> io.BytesIO:
    if shipment_id:
        shipment = db.query(Shipment).filter(Shipment.id == shipment_id).first()
    else:
        shipment = db.query(Shipment).order_by(Shipment.id.desc()).first()

    if not shipment:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Пусто"
        ws["A1"] = "База пуста или партия не найдена"
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        return output

    items = db.query(Item).filter(Item.shipment_id == shipment.id).all()
    logs = db.query(ScanLog).filter(ScanLog.shipment_id == shipment.id).all()

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="Calibri", size=10)
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )

    def apply_sheet_style(ws, headers):
        ws.append(headers)
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

    # 1. Все товары
    ws_all = wb.create_sheet(title="Все товары")
    headers_all = ["Штрихкод", "Стикер", "Коробка", "Название", "Вес", "Статус", "Изъятие", "Брак", "Время скана", "Стол"]
    apply_sheet_style(ws_all, headers_all)

    for it in items:
        status_txt = "Отсканирован" if it.is_scanned else "Не отсканирован"
        scan_time = it.scanned_at.strftime("%Y-%m-%d %H:%M:%S") if it.scanned_at else ""
        is_def = getattr(it, 'is_defect', False)
        defect_txt = "ДА (БРАК)" if is_def else "Нет"
        weight_txt = getattr(it, 'weight', '') or ""
        ws_all.append([
            it.barcode, it.sticker, it.box_number, it.title, weight_txt,
            status_txt, it.seizure_type, defect_txt, scan_time, it.desk_id or ""
        ])

    # 2. Все Изъятия
    ws_seiz = wb.create_sheet(title="Все Изъятия")
    headers_seiz = ["Штрихкод", "Стикер", "Коробка", "Название", "Вес", "Тип изъятия", "Статус", "Время скана", "Стол"]
    apply_sheet_style(ws_seiz, headers_seiz)

    for it in items:
        if it.seizure_type != "NONE":
            status_txt = "Отсканирован" if it.is_scanned else "Не отсканирован"
            scan_time = it.scanned_at.strftime("%Y-%m-%d %H:%M:%S") if it.scanned_at else ""
            weight_txt = getattr(it, 'weight', '') or ""
            ws_seiz.append([
                it.barcode, it.sticker, it.box_number, it.title, weight_txt,
                it.seizure_type, status_txt, scan_time, it.desk_id or ""
            ])

    # 3. Не отсканировано
    ws_not = wb.create_sheet(title="Не отсканировано")
    headers_not = ["Штрихкод", "Стикер", "Коробка", "Название", "Вес", "Изъятие"]
    apply_sheet_style(ws_not, headers_not)

    for it in items:
        if not it.is_scanned:
            weight_txt = getattr(it, 'weight', '') or ""
            ws_not.append([
                it.barcode, it.sticker, it.box_number, it.title, weight_txt, it.seizure_type
            ])

    # 4. Зайцы
    ws_rabbits = wb.create_sheet(title="Зайцы")
    headers_rabbits = ["Отсканированный ШХ / Код", "Статус", "Время скана", "Стол"]
    apply_sheet_style(ws_rabbits, headers_rabbits)

    for lg in logs:
        if lg.status in ["НЕТ В БАЗЕ", "НЕ ТОТ ШТРИХКОД"]:
            l_time = lg.created_at.strftime("%Y-%m-%d %H:%M:%S") if lg.created_at else ""
            ws_rabbits.append([lg.scanned_code, "ЗАЯЦ (НЕТ В БАЗЕ)", l_time, lg.desk_id or ""])

    # 5. Брак
    ws_defect = wb.create_sheet(title="Брак")
    headers_defect = ["Штрихкод", "Стикер", "Коробка", "Название", "Вес", "Изъятие", "Время скана", "Стол"]
    apply_sheet_style(ws_defect, headers_defect)

    for it in items:
        if getattr(it, 'is_defect', False):
            scan_time = it.scanned_at.strftime("%Y-%m-%d %H:%M:%S") if it.scanned_at else ""
            weight_txt = getattr(it, 'weight', '') or ""
            ws_defect.append([
                it.barcode, it.sticker, it.box_number, it.title, weight_txt,
                it.seizure_type, scan_time, it.desk_id or ""
            ])

    for sheet in wb.worksheets:
        if sheet.max_row >= 1:
            sheet.auto_filter.ref = sheet.dimensions
        for row in sheet.iter_rows(min_row=2):
            for cell in row:
                cell.font = data_font
                cell.border = thin_border
                cell.alignment = left_align

        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or "")
                max_len = max(max_len, len(val))
            sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output