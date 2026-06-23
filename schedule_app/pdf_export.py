"""PDF export using ReportLab."""

from datetime import datetime, timedelta
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from . import database as db
from .config import DAYS_SHORT


# Cell background colors
STATUS_COLORS = {
    "off": colors.Color(0.84, 0.85, 0.86),        # Gray
    "leave": colors.Color(0.98, 0.91, 0.62),       # Yellow
}

LOCATION_COLORS = {
    "Clinic": colors.Color(0.68, 0.84, 0.95),       # Blue
    "Office": colors.Color(0.67, 0.92, 0.78),       # Green
    "NIZWA": colors.Color(0.82, 0.71, 0.87),        # Purple
    "MOO": colors.Color(0.6, 0.11, 0.11),             # Dark Red
    "MGM": colors.Color(1.0, 0.95, 0.0),              # Neon Yellow
    "SCC": colors.Color(0.51, 0.09, 0.26),           # Dark Dark Pink
    "AV": colors.Color(1.0, 0.84, 0.67),             # Orange-Brown
    "CCC": colors.Color(0.82, 0.98, 0.90),           # Green
    "QCC": colors.Color(0.86, 0.93, 1.0),            # Blue
    "SALALAH": colors.Color(0.78, 0.58, 0.04),       # Gold
}


def export_schedule_pdf(schedule_id: int, filepath: str):
    """Export a schedule to a PDF file."""
    schedule = None
    for s in db.get_all_schedules():
        if s.id == schedule_id:
            schedule = s
            break

    if not schedule:
        return

    assignments = db.get_schedule_assignments(schedule_id)

    # Group assignments by staff
    staff_data = {}
    for a in assignments:
        if a.staff_name not in staff_data:
            staff_data[a.staff_name] = [""] * 7
        staff_data[a.staff_name][a.day_of_week] = a.display_text()

    # Sort staff alphabetically
    sorted_staff = sorted(staff_data.keys())

    # Day headers with dates, e.g. "Sat 21/6"
    try:
        ws = datetime.strptime(schedule.week_start, "%Y-%m-%d")
    except Exception:
        ws = None
    day_headers = []
    for i in range(7):
        if ws:
            dd = ws + timedelta(days=i)
            day_headers.append(f"{DAYS_SHORT[i]}<br/>{dd.day}/{dd.month}")
        else:
            day_headers.append(DAYS_SHORT[i])

    # Per-location colors from a palette (matches the app's location colors).
    palette = ["#6366f1", "#0ea5e9", "#10b981", "#f59e0b", "#ef4444", "#ec4899",
               "#8b5cf6", "#14b8a6", "#f97316", "#84cc16", "#06b6d4", "#a855f7",
               "#eab308", "#3b82f6"]
    loc_color = {}
    for idx, loc in enumerate(db.get_all_locations(active_only=False)):
        c = colors.HexColor(palette[idx % len(palette)])
        if loc.short_code:
            loc_color[loc.short_code.upper()] = c
        if loc.name:
            loc_color[loc.name.upper()] = c

    def readable_text(c):
        lum = 0.299 * c.red + 0.587 * c.green + 0.114 * c.blue
        return colors.white if lum < 0.6 else colors.HexColor("#1f2937")

    # Scale font + padding so the table fits the page even with many staff.
    n = len(sorted_staff)
    if n <= 12:
        fs, pad = 9, 5
    elif n <= 20:
        fs, pad = 8, 3.5
    elif n <= 30:
        fs, pad = 7, 2.5
    else:
        fs, pad = 6, 1.5

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('CustomTitle', parent=styles['Title'], fontSize=18,
                                 alignment=TA_CENTER, spaceAfter=2 * mm,
                                 textColor=colors.HexColor("#1f2937"))
    subtitle_style = ParagraphStyle('Subtitle', parent=styles['Normal'], fontSize=11,
                                    alignment=TA_CENTER, spaceAfter=6 * mm,
                                    textColor=colors.HexColor("#64748b"))
    hdr_style = ParagraphStyle('hdr', parent=styles['Normal'], fontName='Helvetica-Bold',
                               fontSize=fs + 1, alignment=TA_CENTER, textColor=colors.white,
                               leading=fs + 3)
    name_style = ParagraphStyle('name', parent=styles['Normal'], fontName='Helvetica-Bold',
                                fontSize=fs, leading=fs + 2, textColor=colors.HexColor("#1f2937"))
    cell_base = ParagraphStyle('cell', parent=styles['Normal'], fontName='Helvetica',
                               fontSize=fs, alignment=TA_CENTER, leading=fs + 2)

    # Build table rows (Paragraphs so text wraps and never overflows)
    header_row = [Paragraph("Staff", hdr_style)] + [Paragraph(h, hdr_style) for h in day_headers]
    table_data = [header_row]
    bg_cmds = []
    for r, name in enumerate(sorted_staff, start=1):
        row = [Paragraph(name, name_style)]
        for ci in range(7):
            text = staff_data[name][ci] or ""
            up = text.upper()
            txt_color = colors.HexColor("#1f2937")
            bg = None
            if up == "OFF":
                bg = STATUS_COLORS["off"]
            elif up == "LEAVE":
                bg = STATUS_COLORS["leave"]
            else:
                for key, c in loc_color.items():
                    if key in up:
                        bg = c
                        txt_color = readable_text(c)
                        break
            if bg is not None:
                bg_cmds.append(('BACKGROUND', (ci + 1, r), (ci + 1, r), bg))
            cs = ParagraphStyle('c', parent=cell_base, textColor=txt_color)
            row.append(Paragraph(text or "-", cs))
        table_data.append(row)

    # Document + title
    doc = SimpleDocTemplate(
        filepath, pagesize=landscape(A4),
        leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm,
    )
    elements = []
    business = db.get_setting("business_name", "Finland Optical")
    elements.append(Paragraph(f"{business} — Weekly Schedule", title_style))
    elements.append(Paragraph(f"{schedule.week_start} to {schedule.week_end}", subtitle_style))

    page_width = landscape(A4)[0] - 24 * mm
    name_w = 38 * mm
    day_w = (page_width - name_w) / 7
    table = Table(table_data, colWidths=[name_w] + [day_w] * 7, repeatRows=1)

    style = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.HexColor("#1f2937")),
        ('TOPPADDING', (0, 0), (-1, -1), pad),
        ('BOTTOMPADDING', (0, 0), (-1, -1), pad),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor("#f8fafc")))
    style += bg_cmds
    table.setStyle(TableStyle(style))
    elements.append(table)

    doc.build(elements)
