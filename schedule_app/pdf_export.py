"""PDF export using ReportLab."""

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

    # Build table data
    header = ["Staff"] + [f"{DAYS_SHORT[i]}\n{schedule.week_start}" for i in range(7)]
    # Simplify: just use day names
    header = ["Staff"] + DAYS_SHORT

    table_data = [header]
    for name in sorted_staff:
        row = [name] + staff_data[name]
        table_data.append(row)

    # Create PDF
    doc = SimpleDocTemplate(
        filepath,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm
    )

    elements = []

    # Title
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle', parent=styles['Title'],
        fontSize=16, alignment=TA_CENTER, spaceAfter=5 * mm
    )
    subtitle_style = ParagraphStyle(
        'Subtitle', parent=styles['Normal'],
        fontSize=10, alignment=TA_CENTER, spaceAfter=8 * mm
    )

    elements.append(Paragraph("Finland Optical Center - Weekly Schedule", title_style))
    elements.append(Paragraph(
        f"{schedule.week_start} to {schedule.week_end}", subtitle_style
    ))

    # Calculate column widths
    page_width = landscape(A4)[0] - 30 * mm
    name_col_width = 70 * mm
    day_col_width = (page_width - name_col_width) / 7

    col_widths = [name_col_width] + [day_col_width] * 7

    table = Table(table_data, colWidths=col_widths, repeatRows=1)

    # Style
    style_commands = [
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), colors.Color(0.17, 0.24, 0.31)),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

        # Body
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),

        # Grid
        ('GRID', (0, 0), (-1, -1), 0.5, colors.Color(0.7, 0.7, 0.7)),
        ('LINEBELOW', (0, 0), (-1, 0), 1.5, colors.Color(0.17, 0.24, 0.31)),

        # Row padding
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),

        # Alternating row colors
    ]

    # Add alternating row backgrounds
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            style_commands.append(
                ('BACKGROUND', (0, i), (-1, i), colors.Color(0.95, 0.95, 0.95))
            )

    # Color-code specific cells
    for row_idx, name in enumerate(sorted_staff, start=1):
        for col_idx in range(7):
            cell_text = staff_data[name][col_idx]
            cell_upper = cell_text.upper() if cell_text else ""

            if cell_upper == "OFF":
                style_commands.append(
                    ('BACKGROUND', (col_idx + 1, row_idx), (col_idx + 1, row_idx),
                     STATUS_COLORS["off"])
                )
            elif cell_upper == "LEAVE":
                style_commands.append(
                    ('BACKGROUND', (col_idx + 1, row_idx), (col_idx + 1, row_idx),
                     STATUS_COLORS["leave"])
                )
            else:
                # Check for branch code in cell text (e.g. "10-7 MOO", "SALALAH", "CLINIC")
                color = None
                for code, c in LOCATION_COLORS.items():
                    if code in cell_upper:
                        color = c
                        break
                if color:
                    style_commands.append(
                        ('BACKGROUND', (col_idx + 1, row_idx), (col_idx + 1, row_idx), color)
                    )
                    if code in ("MOO", "SCC", "SALALAH"):
                        style_commands.append(
                            ('TEXTCOLOR', (col_idx + 1, row_idx), (col_idx + 1, row_idx), colors.white)
                        )

    table.setStyle(TableStyle(style_commands))
    elements.append(table)

    doc.build(elements)
