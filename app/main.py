from pathlib import Path
from datetime import datetime
from io import BytesIO

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.scoring import calculate_risk
from app.pdf_report import build_pdf_report

app = FastAPI(title="CashGuard TR")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


SECTOR_LABELS = {
    "defense": "Savunma Sanayi",
    "construction": "İnşaat",
    "electrical": "Elektrik Taahhüt",
    "energy": "Enerji",
}


def _common_ctx(request: Request, title: str):
    return {"request": request, "title": title, "year": datetime.now().year}


def _sanitize_sector(sector: str | None) -> str:
    s = (sector or "defense").strip().lower()
    return s if s in SECTOR_LABELS else "defense"


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    ctx = _common_ctx(request, "CashGuard TR | cashguardtr.com")
    return templates.TemplateResponse("index.html", ctx)


@app.get("/check", response_class=HTMLResponse)
def check(request: Request, sector: str = "defense"):
    sector = _sanitize_sector(sector)
    sector_label = SECTOR_LABELS[sector]

    ctx = _common_ctx(request, f"{sector_label} Risk Testi | CashGuard TR")
    ctx.update({"sector": sector, "sector_label": sector_label})
    return templates.TemplateResponse("check.html", ctx)


@app.post("/result", response_class=HTMLResponse)
def result(
    request: Request,
    sector: str = Form("defense"),

    collection_days: int = Form(...),
    payable_days: int = Form(...),
    fx_debt_ratio: int = Form(...),
    fx_revenue_ratio: int = Form(...),
    cash_buffer_months: int = Form(...),
    top_customer_share: int = Form(...),

    top_customer_2m_gap_month: int = Form(...),
    unplanned_deferral_12m: str = Form(...),

    delay_issue: str = Form(...),
    short_debt_ratio: int = Form(...),
    limit_pressure: str = Form(...),
    hedging: str = Form(...),
):
    sector = _sanitize_sector(sector)
    sector_label = SECTOR_LABELS[sector]

    score, level, messages = calculate_risk(
        sector=sector,

        collection_days=collection_days,
        payable_days=payable_days,
        fx_debt_ratio=fx_debt_ratio,
        fx_revenue_ratio=fx_revenue_ratio,
        cash_buffer_months=cash_buffer_months,
        top_customer_share=top_customer_share,

        top_customer_2m_gap_month=top_customer_2m_gap_month,
        unplanned_deferral_12m=unplanned_deferral_12m,

        delay_issue=delay_issue,
        short_debt_ratio=short_debt_ratio,
        limit_pressure=limit_pressure,
        hedging=hedging,
    )

    ctx = _common_ctx(request, f"Sonuç | {sector_label} | CashGuard TR")
    ctx.update(
        {
            "sector": sector,
            "sector_label": sector_label,

            "score": score,
            "level": level,
            "messages": messages,

            # PDF için geri taşı
            "collection_days": collection_days,
            "payable_days": payable_days,
            "fx_debt_ratio": fx_debt_ratio,
            "fx_revenue_ratio": fx_revenue_ratio,
            "cash_buffer_months": cash_buffer_months,
            "top_customer_share": top_customer_share,

            "top_customer_2m_gap_month": top_customer_2m_gap_month,
            "unplanned_deferral_12m": unplanned_deferral_12m,

            "delay_issue": delay_issue,
            "short_debt_ratio": short_debt_ratio,
            "limit_pressure": limit_pressure,
            "hedging": hedging,
        }
    )
    return templates.TemplateResponse("result.html", ctx)


@app.post("/result/pdf")
def result_pdf(
    request: Request,
    sector: str = Form("defense"),

    collection_days: int = Form(...),
    payable_days: int = Form(...),
    fx_debt_ratio: int = Form(...),
    fx_revenue_ratio: int = Form(...),
    cash_buffer_months: int = Form(...),
    top_customer_share: int = Form(...),

    top_customer_2m_gap_month: int = Form(...),
    unplanned_deferral_12m: str = Form(...),

    delay_issue: str = Form(...),
    short_debt_ratio: int = Form(...),
    limit_pressure: str = Form(...),
    hedging: str = Form(...),

    company: str = Form(""),
):
    sector = _sanitize_sector(sector)
    sector_label = SECTOR_LABELS[sector]

    score, level, messages = calculate_risk(
        sector=sector,

        collection_days=collection_days,
        payable_days=payable_days,
        fx_debt_ratio=fx_debt_ratio,
        fx_revenue_ratio=fx_revenue_ratio,
        cash_buffer_months=cash_buffer_months,
        top_customer_share=top_customer_share,

        top_customer_2m_gap_month=top_customer_2m_gap_month,
        unplanned_deferral_12m=unplanned_deferral_12m,

        delay_issue=delay_issue,
        short_debt_ratio=short_debt_ratio,
        limit_pressure=limit_pressure,
        hedging=hedging,
    )

    payload = {
        "company": company,
        "sector": sector_label,

        "score": score,
        "level": level,
        "messages": messages,

        "collection_days": collection_days,
        "payable_days": payable_days,
        "fx_debt_ratio": fx_debt_ratio,
        "fx_revenue_ratio": fx_revenue_ratio,
        "cash_buffer_months": cash_buffer_months,
        "top_customer_share": top_customer_share,

        "top_customer_2m_gap_month": top_customer_2m_gap_month,
        "unplanned_deferral_12m": unplanned_deferral_12m,

        "delay_issue": delay_issue,
        "short_debt_ratio": short_debt_ratio,
        "limit_pressure": limit_pressure,
        "hedging": hedging,
    }

    pdf_bytes = build_pdf_report(payload)
    filename = f"cashguardtr-{sector}-skor-{score}.pdf"

    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/about", response_class=HTMLResponse)
def about(request: Request):
    ctx = _common_ctx(request, "Hakkında | CashGuard TR")
    return templates.TemplateResponse("about.html", ctx)


@app.get("/team", response_class=HTMLResponse)
def team(request: Request):
    ctx = _common_ctx(request, "Biz Kimiz | CashGuard TR")
    return templates.TemplateResponse("team.html", ctx)


@app.get("/services", response_class=HTMLResponse)
def services(request: Request):
    ctx = _common_ctx(request, "Hizmetlerimiz | CashGuard TR")
    return templates.TemplateResponse("services.html", ctx)


@app.get("/contact", response_class=HTMLResponse)
def contact(request: Request):
    ctx = _common_ctx(request, "İletişim | CashGuard TR")
    return templates.TemplateResponse("contact.html", ctx)


@app.get("/health")
def health():
    return {"status": "ok"}
