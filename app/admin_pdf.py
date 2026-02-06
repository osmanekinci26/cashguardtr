# app/admin_pdf.py
from io import BytesIO
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


# ===============================
# Colors
# ===============================
BG = colors.HexColor("#0b1220")
TEXT = colors.HexColor("#e6edf7")
MUTED = colors.HexColor("#a6b3cc")
ACCENT = colors.HexColor("#7c3aed")


# ===============================
# Font setup (Render-safe)
# ===============================
BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"


def _register_fonts():
    """
    Register a Unicode font so Turkish characters render correctly.
    Uses repo path: app/assets/fonts/DejaVuSans.ttf
    """
    # already registered?
    try:
        pdfmetrics.getFont("DejaVu")
        pdfmetrics.getFont("DejaVu-Bold")
        return
    except KeyError:
        pass

    if not FONT_REGULAR.exists():
        raise FileNotFoundError(
            f"Font not found: {FONT_REGULAR}. "
            f"Make sure it's committed under app/assets/fonts/"
        )

    pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_REGULAR)))

    # Bold optional: fallback to regular if missing
    if FONT_BOLD.exists():
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_BOLD)))
    else:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_REGULAR)))


def build_admin_analysis_pdf(company_name: str, sector_label: str, bullets: list[str]) -> bytes:
    _register_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    # background
    c.setFillColor(BG)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    mx = 18 * mm
    y = h - 18 * mm

    # header
    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 18)
    c.drawString(mx, y, "CashGuard — Admin Analiz Raporu")
    y -= 8 * mm

    c.setFont("DejaVu", 11)
    c.setFillColor(MUTED)
    c.drawString(mx, y, f"Firma: {company_name}  |  Sektör: {sector_label}")
    c.drawRightString(w - mx, y, datetime.now().strftime("%d.%m.%Y %H:%M"))
    y -= 12 * mm

    # title
    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 13)
    c.drawString(mx, y, "10 Maddede Özet")
    y -= 8 * mm

    # bullets
    c.setFont("DejaVu", 11)
    for i, b in enumerate(bullets, start=1):
        if y < 20 * mm:
            c.showPage()
            c.setFillColor(BG)
            c.rect(0, 0, w, h, fill=1, stroke=0)
            y = h - 18 * mm

            c.setFillColor(TEXT)
            c.setFont("DejaVu-Bold", 13)
            c.drawString(mx, y, "10 Maddede Özet (devam)")
            y -= 10 * mm
            c.setFont("DejaVu", 11)

        c.setFillColor(ACCENT)
        c.circle(mx + 2 * mm, y + 1.5 * mm, 1.2 * mm, fill=1, stroke=0)

        c.setFillColor(TEXT)
        c.drawString(mx + 7 * mm, y, f"{i}) {b}")
        y -= 7 * mm

    # footer
    c.setFillColor(MUTED)
    c.setFont("DejaVu", 9.5)
    c.drawString(mx, 12 * mm, "cashguardtr.com • admin raporu")

    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
