"""
PDF Report Generator
=====================
Renders a Profit & Loss statement (as built by report_engine.get_pnl) into a
formatted PDF. Only ever called from the /reports/pnl/pdf endpoint, i.e.
generated on explicit user request — nothing in this codebase generates a
report automatically or on a schedule.

Category names are rendered without their emoji icon: reportlab's built-in
fonts (Helvetica et al.) don't have emoji glyphs, so keeping icons would
just print as missing-glyph boxes.
"""
import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_HEADER_BG = colors.HexColor("#1f2937")
_ROW_ALT_BG = colors.HexColor("#f9fafb")
_GRID_COLOR = colors.HexColor("#d1d5db")


def _money(amount: float, currency: str) -> str:
    return f"{currency} {amount:,.2f}"


def _breakdown_table(rows: list[dict], currency: str) -> Table:
    total = sum(r["total"] for r in rows) or 0
    data = [["Category", "Amount", "% of total"]]
    for r in rows:
        pct = f"{(r['total'] / total * 100):.1f}%" if total else "—"
        data.append([r["name"], _money(r["total"], currency), pct])

    table = Table(data, colWidths=[8 * cm, 4.5 * cm, 3 * cm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, _GRID_COLOR),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT_BG]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return table


def generate_pnl_pdf(statement: dict) -> bytes:
    """Build a P&L PDF report from the dict returned by report_engine.get_pnl."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm, leftMargin=2 * cm, rightMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("PnlTitle", parent=styles["Title"], fontSize=18, spaceAfter=4)
    subtitle_style = ParagraphStyle("PnlSubtitle", parent=styles["Normal"], fontSize=10, textColor=colors.grey)
    heading_style = ParagraphStyle("PnlHeading", parent=styles["Heading2"], spaceBefore=18, spaceAfter=6)

    currency = statement["currency"]
    story = [
        Paragraph("LedgerFlow — Profit &amp; Loss Statement", title_style),
        Paragraph(f"{statement['from_date']} to {statement['to_date']}", subtitle_style),
        Spacer(1, 0.6 * cm),
    ]

    summary_table = Table(
        [
            ["Total income", _money(statement["total_income"], currency)],
            ["Total expenses", _money(statement["total_expenses"], currency)],
            ["Net income", _money(statement["net_income"], currency)],
        ],
        colWidths=[8 * cm, 7.5 * cm],
    )
    summary_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 11),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, 1), 0.5, _GRID_COLOR),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(summary_table)

    story.append(Paragraph("Income by category", heading_style))
    story.append(
        _breakdown_table(statement["income"], currency)
        if statement["income"]
        else Paragraph("No income in this period.", styles["Normal"])
    )

    story.append(Paragraph("Expenses by category", heading_style))
    story.append(
        _breakdown_table(statement["expenses"], currency)
        if statement["expenses"]
        else Paragraph("No expenses in this period.", styles["Normal"])
    )

    doc.build(story)
    return buffer.getvalue()
