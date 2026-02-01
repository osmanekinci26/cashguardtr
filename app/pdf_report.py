from io import BytesIO
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = Path(__file__).resolve().parent
FONT_DIR = BASE_DIR / "assets" / "fonts"
ICON_PATH = BASE_DIR / "static" / "icon-64.png"

# Web sitenin koyu teması (senin eski temaya yakın)
BG = colors.HexColor("#0b1220")
CARD = colors.HexColor("#0f1b33")
TEXT = colors.HexColor("#e6edf7")
MUTED = colors.HexColor("#a6b3cc")
ACCENT = colors.HexColor("#7c3aed")


def _register_fonts():
    """
    Register a Unicode font so Turkish characters render correctly.
    Call this once per process (safe to call multiple times).
    """
    try:
        pdfmetrics.getFont("DejaVu")
        return
    except KeyError:
        pass

    regular = FONT_DIR / "DejaVuSans.ttf"
    bold = FONT_DIR / "DejaVuSans-Bold.ttf"

    if regular.exists():
        pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))
    else:
        raise FileNotFoundError(f"Font not found: {regular}")

    if bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
    else:
        # bold yoksa regular'ı da bold yerine kullanırız
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(regular)))


def _wrap_text(c, text, max_width, font_name, font_size):
    """
    Basic word-wrapping for ReportLab canvas.
    Returns list of lines.
    """
    words = str(text).split()
    lines = []
    line = ""
    for w in words:
        test = (line + " " + w).strip()
        if c.stringWidth(test, font_name, font_size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def build_pdf_report(payload: dict) -> bytes:
    """
    Returns PDF bytes. payload should include:
    score, level, messages (list[str]) and input fields.
    Optional: company
    """
    _register_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # --- Background ---
    c.setFillColor(BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Content bounds
    margin_x = 18 * mm
    top_y = height - 18 * mm
    y = top_y

    # --- Header row ---
    # icon
    if ICON_PATH.exists():
        c.drawImage(str(ICON_PATH), margin_x, y - 14 * mm, width=12 * mm, height=12 * mm, mask="auto")

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 18)
    c.drawString(margin_x + 15 * mm, y - 4 * mm, "CashGuard TR")
    c.setFont("DejaVu", 11)
    c.setFillColor(MUTED)
    c.drawString(margin_x + 15 * mm, y - 10.5 * mm, "Nakit Risk Taraması Raporu")

    # right side date
    c.setFont("DejaVu", 10)
    c.setFillColor(MUTED)
    c.drawRightString(width - margin_x, y - 6 * mm, datetime.now().strftime("%d.%m.%Y %H:%M"))

    y -= 20 * mm

    # --- Summary Card ---
    card_h = 28 * mm
    c.setFillColor(CARD)
    c.roundRect(margin_x, y - card_h, width - 2 * margin_x, card_h, 10, fill=1, stroke=0)

    score = int(payload.get("score", 0))
    level = str(payload.get("level", "")).upper()
    company = (payload.get("company") or "").strip()

    # score color
    if "GREEN" in level:
        badge = colors.HexColor("#22c55e")
    elif "YELLOW" in level:
        badge = colors.HexColor("#facc15")
    else:
        badge = colors.HexColor("#ef4444")

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 14)
    c.drawString(margin_x + 10, y - 12, "Sonuç Özeti")

    # badge pill
    pill_w = 42 * mm
    pill_h = 8 * mm
    pill_x = width - margin_x - pill_w
    pill_y = y - 16 * mm
    c.setFillColor(badge)
    c.roundRect(pill_x, pill_y, pill_w, pill_h, 8, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("DejaVu-Bold", 10)
    c.drawCentredString(pill_x + pill_w / 2, pill_y + 2.1 * mm, level)

    # score big
    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 26)
    c.drawString(margin_x + 10, y - 24 * mm, f"{score}/100")

    c.setFont("DejaVu", 10.5)
    c.setFillColor(MUTED)
    if company:
        c.drawString(margin_x + 10 + 60 * mm, y - 22.5 * mm, f"Firma: {company}")
    c.drawString(margin_x + 10 + 60 * mm, y - 28 * mm, "Not: Bu rapor hızlı ön tarama amaçlıdır.")

    y -= (card_h + 10 * mm)

    # --- Inputs Section ---
    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 13)
    c.drawString(margin_x, y, "Girilen Bilgiler")
    y -= 7 * mm

    c.setFont("DejaVu", 11)
    c.setFillColor(TEXT)

    inputs = [
        ("Tahsilat günü", payload.get("collection_days")),
        ("Ödeme günü", payload.get("payable_days")),
        ("FX borç oranı (%)", payload.get("fx_debt_ratio")),
        ("FX gelir oranı (%)", payload.get("fx_revenue_ratio")),
        ("Nakit tampon (ay)", payload.get("cash_buffer_months")),
        ("Top müşteri payı (%)", payload.get("top_customer_share")),
        ("Gecikme sorunu", payload.get("delay_issue")),
        ("Kısa vade borç payı (%)", payload.get("short_debt_ratio")),
        ("Limit baskısı", payload.get("limit_pressure")),
        ("Hedge var mı", payload.get("hedging")),
    ]

    col1_x = margin_x
    col2_x = margin_x + (width - 2 * margin_x) / 2
    row_h = 6.5 * mm

    for i, (k, v) in enumerate(inputs):
        x = col1_x if i < 5 else col2_x
        yy = y - (i % 5) * row_h

        c.setFillColor(MUTED)
        c.setFont("DejaVu", 10.5)
        c.drawString(x, yy, f"{k}:")
        c.setFillColor(TEXT)
        c.setFont("DejaVu-Bold", 10.8)
        c.drawString(x + 42 * mm, yy, f"{v}")

    y -= 5 * row_h + 6 * mm

    # --- Messages / Recommendations ---
    if y < 70 * mm:
        c.showPage()
        width, height = A4
        c.setFillColor(BG)
        c.rect(0, 0, width, height, fill=1, stroke=0)
        y = height - 18 * mm

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 13)
    c.drawString(margin_x, y, "Öne Çıkan Başlıklar ve Öneriler")
    y -= 7 * mm

    max_w = width - 2 * margin_x
    c.setFont("DejaVu", 11.5)

    for msg in payload.get("messages", []):
        # bullet
        c.setFillColor(TEXT)
        bullet_x = margin_x
        text_x = margin_x + 6 * mm
        lines = _wrap_text(c, msg, max_w - 6 * mm, "DejaVu", 11.5)

        # page break if needed
        needed = (len(lines) * 6.2 + 5) * mm
        if y - needed < 16 * mm:
            c.showPage()
            c.setFillColor(BG)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            y = height - 18 * mm
            c.setFillColor(TEXT)
            c.setFont("DejaVu-Bold", 13)
            c.drawString(margin_x, y, "Öne Çıkan Başlıklar ve Öneriler (devam)")
            y -= 7 * mm
            c.setFont("DejaVu", 11.5)

        c.setFillColor(ACCENT)
        c.circle(bullet_x + 1.5 * mm, y - 2.2 * mm, 1.2 * mm, fill=1, stroke=0)

        c.setFillColor(TEXT)
        for ln in lines:
            c.drawString(text_x, y, ln)
            y -= 6.2 * mm
        y -= 2.5 * mm

    # Footer
    c.setFillColor(MUTED)
    c.setFont("DejaVu", 9.5)
    c.drawString(margin_x, 12 * mm, "cashguardtr.com • İletişim: info@cashguardtr.com")

    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
