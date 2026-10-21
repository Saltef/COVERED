"""Render an ApplicationPackage into a clean, ready-to-review PDF."""
from __future__ import annotations

from io import BytesIO

from app.domain.applications import APPLICANT, PRACTITIONER, ApplicationPackage

_WHO_LABEL = {"prefilled": "Pre-filled", APPLICANT: "You complete", PRACTITIONER: "Doctor completes"}


def render_package_pdf(pkg: ApplicationPackage) -> bytes:
    # Imported lazily so the app loads even if reportlab isn't installed.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        leftMargin=0.9 * inch, rightMargin=0.9 * inch,
        title=pkg.form_name,
    )
    styles = getSampleStyleSheet()
    brand = colors.HexColor("#c8102e")
    ink = colors.HexColor("#11223a")
    muted = colors.HexColor("#5b6b82")

    h1 = ParagraphStyle("h1", parent=styles["Title"], fontSize=18, textColor=ink, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=styles["Normal"], fontSize=10, textColor=muted, spaceAfter=14)
    sec = ParagraphStyle("sec", parent=styles["Heading2"], fontSize=12, textColor=brand, spaceBefore=12, spaceAfter=6)
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10.5, textColor=ink, leading=15)

    story = [
        Paragraph(pkg.form_name, h1),
        Paragraph("Prepared by Covered &mdash; review before submitting. Nothing is filed automatically.", sub),
        Paragraph("Application details", sec),
    ]

    rows = [["Field", "Value", "Who"]]
    for f in pkg.fields:
        value = f.value if f.value is not None else "— to complete —"
        rows.append([f.label, value, _WHO_LABEL.get(f.who, f.who)])

    table = Table(rows, colWidths=[2.9 * inch, 2.6 * inch, 1.2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ink),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f7fb")]),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f2")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)

    def bullet_list(items):
        return ListFlowable(
            [ListItem(Paragraph(it, body), leftIndent=10) for it in items],
            bulletType="bullet", start="•",
        )

    if pkg.still_needed:
        story += [Paragraph("What you still need to do", sec), bullet_list(pkg.still_needed)]
    if pkg.submission:
        story += [Paragraph("How to submit", sec), bullet_list(pkg.submission)]

    story += [
        Spacer(1, 16),
        Paragraph("<i>Covered helps you find and prepare benefits you may be owed. Figures use 2025 "
                  "CRA / Ontario rates and are estimates that depend on your situation. This is not "
                  "legal, tax, or financial advice.</i>",
                  ParagraphStyle("foot", parent=body, fontSize=8.5, textColor=muted)),
    ]

    doc.build(story)
    return buf.getvalue()
