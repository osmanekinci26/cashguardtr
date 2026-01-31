from pathlib import Path

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from app.scoring import calculate_risk

app = FastAPI(title="CashGuard TR")

# Base directory: ...\Desktop\cashguard\app
BASE_DIR = Path(__file__).resolve().parent

# Static files: ...\app\static\style.css will be served at /static/style.css
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# Templates: ...\app\templates\index.html etc.
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/check", response_class=HTMLResponse)
def check(request: Request):
    return templates.TemplateResponse("check.html", {"request": request})


@app.post("/result", response_class=HTMLResponse)
def result(
    request: Request,
    collection_days: int = Form(...),
    payable_days: int = Form(...),
    fx_debt_ratio: int = Form(...),
    fx_revenue_ratio: int = Form(...),
    cash_buffer_months: int = Form(...),
    top_customer_share: int = Form(...),
    delay_issue: str = Form(...),
    short_debt_ratio: int = Form(...),
    limit_pressure: str = Form(...),
    hedging: str = Form(...),
):
    score, level, messages = calculate_risk(
        collection_days=collection_days,
        payable_days=payable_days,
        fx_debt_ratio=fx_debt_ratio,
        fx_revenue_ratio=fx_revenue_ratio,
        cash_buffer_months=cash_buffer_months,
        top_customer_share=top_customer_share,
        delay_issue=delay_issue,
        short_debt_ratio=short_debt_ratio,
        limit_pressure=limit_pressure,
        hedging=hedging,
    )

    return templates.TemplateResponse(
        "result.html",
        {"request": request, "score": score, "level": level, "messages": messages},
    )
