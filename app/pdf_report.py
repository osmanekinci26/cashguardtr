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
ICON_PATH = BASE_DIR / "static" / "icon-512.png"

# Web sitenin koyu teması
BG = colors.HexColor("#0b1220")
CARD = colors.HexColor("#0f1b33")
TEXT = colors.HexColor("#e6edf7")
MUTED = colors.HexColor("#a6b3cc")
ACCENT = colors.HexColor("#7c3aed")


def _register_fonts():
    """Register a Unicode font so Turkish characters render correctly."""
    try:
        pdfmetrics.getFont("DejaVu")
        return
    except KeyError:
        pass

    regular = FONT_DIR / "DejaVuSans.ttf"
    bold = FONT_DIR / "DejaVuSans-Bold.ttf"

    if not regular.exists():
        raise FileNotFoundError(f"Font not found: {regular}")

    pdfmetrics.registerFont(TTFont("DejaVu", str(regular)))

    # Bold yoksa regular ile devam
    if bold.exists():
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(bold)))
    else:
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(regular)))


def _wrap_text(c, text, max_width, font_name, font_size):
    """Basic word-wrapping for ReportLab canvas. Returns list of lines."""
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
    Optional: company, sector
    """
    _register_fonts()

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    # --- Background ---
    c.setFillColor(BG)
    c.rect(0, 0, width, height, fill=1, stroke=0)

    # Layout constants
    margin_x = 18 * mm
    top_y = height - 18 * mm

    # =========================
    # Header (logo left-top)
    # =========================
    logo_size = 18 * mm
    logo_x = 6 * mm
    logo_y = height - 6 * mm - logo_size  # top padding

    if ICON_PATH.exists():
        c.drawImage(
            str(ICON_PATH),
            logo_x,
            logo_y,
            width=logo_size,
            height=logo_size,
            mask="auto",
            preserveAspectRatio=True,
        )

    title_x = logo_x + logo_size + 6 * mm

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 18)
    c.drawString(title_x, height - 10 * mm, "CashGuard")

    c.setFont("DejaVu", 11)
    c.setFillColor(MUTED)
    c.drawString(title_x, height - 16 * mm, "Nakit Risk Taraması Raporu")

    # ✅ NEW: Sector line (optional)
    sector = (payload.get("sector") or "").strip()
    if sector:
        c.setFont("DejaVu", 10.5)
        c.setFillColor(MUTED)
        c.drawString(title_x, height - 21.5 * mm, f"Sektör: {sector}")

    c.setFont("DejaVu", 10)
    c.setFillColor(MUTED)
    c.drawRightString(width - margin_x, height - 10 * mm, datetime.now().strftime("%d.%m.%Y %H:%M"))

    # content y start
    y = top_y - 10 * mm

    # Eğer sektör satırı yazıldıysa içerik yukarıdan biraz daha aşağı başlasın (çakışma olmasın)
    if sector:
        y -= 6 * mm

    # =========================
    # Summary Card
    # =========================
    card_h = 28 * mm
    c.setFillColor(CARD)
    c.roundRect(margin_x, y - card_h, width - 2 * margin_x, card_h, 10, fill=1, stroke=0)

    score = int(payload.get("score", 0))
    level = str(payload.get("level", "")).upper()
    company = (payload.get("company") or "").strip()

    if "GREEN" in level:
        badge = colors.HexColor("#22c55e")
    elif "YELLOW" in level:
        badge = colors.HexColor("#facc15")
    else:
        badge = colors.HexColor("#ef4444")

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 14)
    c.drawString(margin_x + 10, y - 12, "Sonuç Özeti")

    pill_w = 42 * mm
    pill_h = 8 * mm
    pill_x = width - margin_x - pill_w
    pill_y = y - 16 * mm

    c.setFillColor(badge)
    c.roundRect(pill_x, pill_y, pill_w, pill_h, 8, fill=1, stroke=0)
    c.setFillColor(colors.black)
    c.setFont("DejaVu-Bold", 10)
    c.drawCentredString(pill_x + pill_w / 2, pill_y + 2.1 * mm, level)

    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 26)
    c.drawString(margin_x + 10, y - 24 * mm, f"{score}/100")

    c.setFont("DejaVu", 10.5)
    c.setFillColor(MUTED)
    if company:
        c.drawString(margin_x + 10 + 60 * mm, y - 22.5 * mm, f"Firma: {company}")
    c.drawString(margin_x + 10 + 60 * mm, y - 28 * mm, "Not: Bu rapor hızlı ön tarama amaçlıdır.")

    y -= (card_h + 10 * mm)

    # =========================
    # Inputs Section (fix alignment)
    # =========================
    c.setFillColor(TEXT)
    c.setFont("DejaVu-Bold", 13)
    c.drawString(margin_x, y, "Girilen Bilgiler")
    y -= 7 * mm

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

    # Two columns with fixed widths
    content_w = width - 2 * margin_x
    gap = 8 * mm
    col_w = (content_w - gap) / 2

    col1_x = margin_x
    col2_x = margin_x + col_w + gap

    row_h = 7.2 * mm
    label_w = 52 * mm
    pad = 4 * mm

    for i, (k, v) in enumerate(inputs):
        x0 = col1_x if i < 5 else col2_x
        yy = y - (i % 5) * row_h

        c.setFillColor(MUTED)
        c.setFont("DejaVu", 10.8)
        c.drawString(x0, yy, f"{k}:")

        c.setFillColor(TEXT)
        c.setFont("DejaVu-Bold", 11.2)
        vx = x0 + label_w + pad

        max_value_w = x0 + col_w - vx
        value_lines = _wrap_text(c, str(v), max_value_w, "DejaVu-Bold", 11.2)

        c.drawString(vx, yy, value_lines[0])
        extra_y = yy
        for extra in value_lines[1:]:
            extra_y -= 6.2 * mm
            c.drawString(vx, extra_y, extra)

    y -= 5 * row_h + 6 * mm

    # =========================
    # Messages / Recommendations (fix bullet alignment)
    # =========================
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
    font_name = "DejaVu"
    font_size = 11.5
    line_h = 6.4 * mm

    c.setFont(font_name, font_size)

    for msg in payload.get("messages", []):
        text_x = margin_x + 7 * mm
        bullet_cx = margin_x + 2.2 * mm

        lines = _wrap_text(c, msg, max_w - 7 * mm, font_name, font_size)

        needed_h = (len(lines) * line_h) + (3.0 * mm)
        if y - needed_h < 16 * mm:
            c.showPage()
            c.setFillColor(BG)
            c.rect(0, 0, width, height, fill=1, stroke=0)
            y = height - 18 * mm
            c.setFillColor(TEXT)
            c.setFont("DejaVu-Bold", 13)
            c.drawString(margin_x, y, "Öne Çıkan Başlıklar ve Öneriler (devam)")
            y -= 7 * mm
            c.setFont(font_name, font_size)

        c.setFillColor(ACCENT)
        c.circle(bullet_cx, y - (line_h * 0.35), 1.1 * mm, fill=1, stroke=0)

        c.setFillColor(TEXT)
        for ln in lines:
            c.drawString(text_x, y, ln)
            y -= line_h
        y -= 2.2 * mm

    # Footer
    c.setFillColor(MUTED)
    c.setFont("DejaVu", 9.5)
    c.drawString(margin_x, 12 * mm, "cashguardtr.com • İletişim: info@cashguardtr.com")

    c.save()
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
