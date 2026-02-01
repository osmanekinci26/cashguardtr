from io import BytesIO
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_pdf_report(payload: dict) -> bytes:
    """
    Returns PDF bytes. payload must include:
    company (optional), score, level, messages (list[str]) and input fields.
    """
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    width, height = A4

    y = height - 60

    # Header
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, y, "CashGuard TR - Nakit Risk Taramasi Raporu")
    y -= 22

    c.setFont("Helvetica", 10)
    c.drawString(50, y, f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    y -= 18

    company = payload.get("company") or ""
    if company.strip():
        c.drawString(50, y, f"Firma: {company}")
        y -= 18

    # Score
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"Skor: {payload['score']}   Seviye: {payload['level']}")
    y -= 18

    c.setFont("Helvetica", 10)
    c.drawString(50, y, "Ozet:")
    y -= 14

    # Inputs summary
    inputs = [
        ("Tahsilat gunu", payload.get("collection_days")),
        ("Odeme gunu", payload.get("payable_days")),
        ("FX borc oran (%)", payload.get("fx_debt_ratio")),
        ("FX gelir oran (%)", payload.get("fx_revenue_ratio")),
        ("Nakit tampon (ay)", payload.get("cash_buffer_months")),
        ("Top musteri payi (%)", payload.get("top_customer_share")),
        ("Gecikme sorunu", payload.get("delay_issue")),
        ("Kisa vade borc payi (%)", payload.get("short_debt_ratio")),
        ("Limit baskisi", payload.get("limit_pressure")),
        ("Hedge var mi", payload.get("hedging")),
    ]

    for k, v in inputs:
        c.drawString(60, y, f"- {k}: {v}")
        y -= 13
        if y < 80:
            c.showPage()
            y = height - 60
            c.setFont("Helvetica", 10)

    # Recommendations / messages
    y -= 6
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Oneriler / Notlar:")
    y -= 14

    c.setFont("Helvetica", 10)
    for m in payload.get("messages", []):
        # Basic line wrapping
        line = str(m)
        while len(line) > 100:
            c.drawString(60, y, f"- {line[:100]}")
            line = line[100:]
            y -= 13
            if y < 80:
                c.showPage()
                y = height - 60
                c.setFont("Helvetica", 10)
        c.drawString(60, y, f"- {line}")
        y -= 13
        if y < 80:
            c.showPage()
            y = height - 60
            c.setFont("Helvetica", 10)

    # Footer
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(50, 40, "Not: Bu rapor hizli tarama amaclidir; detayli analiz icin iletisime gecin.")
    c.save()

    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes
