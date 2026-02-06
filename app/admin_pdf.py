from io import BytesIO
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm

BG = colors.HexColor("#0b1220")
TEXT = colors.HexColor("#e6edf7")
MUTED = colors.HexColor("#a6b3cc")
ACCENT = colors.HexColor("#7c3aed")


def build_admin_analysis_pdf(company_name: str, sector_label: str, bullets: list[str]) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    c.setFillColor(BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    mx = 18 * mm
    y = h - 18 * mm

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(mx, y, "CashGuard — Admin Analiz Raporu")
    y -= 8 * mm

    c.setFont("Helvetica", 11)
    c.setFillColor(MUTED)
    c.drawString(mx, y, f"Firma: {company_name}  |  Sektör: {sector_label}")
    c.drawRightString(w - mx, y, datetime.now().strftime("%d.%m.%Y %H:%M"))
    y -= 12 * mm

    c.setFillColor(TEXT)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(mx, y, "10 Maddede Özet")
    y -= 8 * mm

    c.setFont("Helvetica", 11)
    for i, b in enumerate(bullets, start=1):
        if y < 20 * mm:
            c.showPage()
            c.setFillColor(BG)
            c.rect(0, 0, w, h, fill=1, stroke=0)
            y = h - 18 * mm
            c.setFillColor(TEXT)
            c.setFont("Helvetica-Bold", 13)
            c.drawString(mx, y, "10 Maddede Özet (devam)")
            y -= 10 * mm
            c.setFont("Helvetica", 11)

        c.setFillColor(ACCENT)
        c.circle(mx + 2 * mm, y + 1.5 * mm, 1.2 * mm, fill=1, stroke=0)
        c.setFillColor(TEXT)
        c.drawString(mx + 7 * mm, y, f"{i}) {b}")
        y -= 7 * mm

    c.setFillColor(MUTED)
    c.setFont("Helvetica", 9.5)
    c.drawString(mx, 12 * mm, "cashguardtr.com • admin raporu")

    c.save()
    out = buf.getvalue()
    buf.close()
    return out
