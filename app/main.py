from pathlib import Path
from datetime import datetime
from io import BytesIO
import os
import json
import shutil

from dotenv import load_dotenv
load_dotenv()

from email.message import EmailMessage
import smtplib
import ssl

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from app.scoring import calculate_risk
from app.pdf_report import build_pdf_report

# ✅ Admin imports
from app.db import Base, engine, get_db
from app.models import User, Company, Upload, Analysis
from app.auth import hash_password, verify_password, make_session, read_session
from app.analysis_engine import parse_financials_xlsx, analyze_financials
from app.admin_pdf import build_admin_analysis_pdf

app = FastAPI(title="CashGuard TR")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# DB init
DATA_DIR = (BASE_DIR / ".." / "data").resolve()
UPLOAD_DIR = (DATA_DIR / "uploads").resolve()
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
Base.metadata.create_all(bind=engine)

SECTOR_LABELS = {
    "defense": "Savunma Sanayi",
    "construction": "İnşaat",
    "electrical": "Elektrik Taahhüt",
    "energy": "Enerji",
}

LEAD_EMAIL = "rapor@cashguardtr.com"


# =========================
# SMTP MAIL SENDER (supports 465 SSL + 587 STARTTLS)
# =========================
def send_email_smtp(
    *,
    to_email: str,
    subject: str,
    body_text: str,
    attachment_bytes: bytes | None = None,
    attachment_filename: str | None = None,
):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")
    from_email = os.getenv("SMTP_FROM") or user

    if not host or not user or not password:
        raise RuntimeError("SMTP env eksik: SMTP_HOST/SMTP_USER/SMTP_PASSWORD/SMTP_FROM")

    msg = EmailMessage()
    msg["From"] = from_email
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body_text)

    if attachment_bytes and attachment_filename:
        msg.add_attachment(
            attachment_bytes,
            maintype="application",
            subtype="pdf",
            filename=attachment_filename,
        )

    ctx = ssl.create_default_context()

    # 465 => SSL, 587 => STARTTLS
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=25) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=25) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.ehlo()
            server.login(user, password)
            server.send_message(msg)


def _common_ctx(request: Request, title: str):
    return {"request": request, "title": title, "year": datetime.now().year}


def _sanitize_sector(sector: str | None) -> str:
    s = (sector or "defense").strip().lower()
    return s if s in SECTOR_LABELS else "defense"


# =========================
# PUBLIC ROUTES
# =========================
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
            # email feedback placeholders (result.html gösterebilir)
            "email_sent": False,
            "email_to": "",
            "email_error": None,
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


@app.post("/result/email", response_class=HTMLResponse)
def result_email(
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
    email: str = Form(...),
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

    user_subject = f"CashGuard TR Sonuç Raporu — {sector_label} ({score}/100)"
    user_body = (
        "Merhaba,\n\n"
        "CashGuard TR hızlı risk test raporunuz ektedir.\n\n"
        f"Sektör: {sector_label}\n"
        f"Skor: {score}/100\n"
        f"Seviye: {level}\n\n"
        "Öne çıkan başlıklar:\n"
        + "\n".join([f"- {m}" for m in messages]) +
        "\n\nCashGuard TR | cashguardtr.com\n"
    )

    lead_subject = f"[LEAD] Rapor gönderildi — {sector_label} ({score}/100)"
    lead_body = (
        "Yeni lead:\n"
        f"- Kullanıcı email: {email}\n"
        f"- Firma: {company or '-'}\n"
        f"- Sektör: {sector_label} ({sector})\n"
        f"- Skor/Seviye: {score}/100 | {level}\n"
        f"- Zaman (UTC): {datetime.utcnow().isoformat()}Z\n"
    )

    email_sent = False
    email_error = None

    try:
        send_email_smtp(
            to_email=email.strip(),
            subject=user_subject,
            body_text=user_body,
            attachment_bytes=pdf_bytes,
            attachment_filename=filename,
        )
        send_email_smtp(
            to_email=LEAD_EMAIL,
            subject=lead_subject,
            body_text=lead_body,
        )
        email_sent = True
    except Exception as e:
        email_error = str(e)

    ctx = _common_ctx(request, f"Sonuç | {sector_label} | CashGuard TR")
    ctx.update(
        {
            "sector": sector,
            "sector_label": sector_label,
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
            "email_sent": email_sent,
            "email_to": email,
            "email_error": email_error,
        }
    )
    return templates.TemplateResponse("result.html", ctx)


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


@app.get("/why-cash", response_class=HTMLResponse)
def why_cash(request: Request):
    ctx = _common_ctx(request, "Nakit Neden Korunmalı? | CashGuard TR")
    return templates.TemplateResponse("why_cash.html", ctx)


@app.get("/health")
def health():
    return {"status": "ok"}


# =========================
# ADMIN AUTH HELPERS
# =========================
def _admin_ctx(request: Request, title: str, admin_email: str | None = None, error: str | None = None):
    ctx = _common_ctx(request, title)
    ctx.update({"admin_email": admin_email, "error": error})
    return ctx


def _get_admin_email_from_cookie(request: Request) -> str | None:
    token = request.cookies.get("cg_admin")
    if not token:
        return None
    data = read_session(token)
    if not data:
        return None
    return data.get("email")


def require_admin(request: Request, db: Session = Depends(get_db)) -> str:
    email = _get_admin_email_from_cookie(request)
    if not email:
        raise PermissionError("Not logged in")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise PermissionError("Unknown user")
    return email


def ensure_initial_admin(db: Session):
    """
    İlk admin hesabını ENV ile oluşturur:
    ADMIN_EMAIL, ADMIN_PASSWORD
    """
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_email or not admin_password:
        return

    exists = db.query(User).filter(User.email == admin_email).first()
    if exists:
        return

    u = User(email=admin_email, password_hash=hash_password(admin_password), role="admin")
    db.add(u)
    db.commit()


# =========================
# ADMIN ROUTES
# =========================
@app.get("/admin", response_class=HTMLResponse)
def admin_home(request: Request, db: Session = Depends(get_db)):
    ensure_initial_admin(db)

    email = _get_admin_email_from_cookie(request)
    if not email:
        ctx = _admin_ctx(request, "Admin Giriş")
        return templates.TemplateResponse("admin_login.html", ctx)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        ctx = _admin_ctx(request, "Admin Giriş", error="Oturum geçersiz. Tekrar giriş yapın.")
        resp = templates.TemplateResponse("admin_login.html", ctx)
        resp.delete_cookie("cg_admin")
        return resp

    companies = db.query(Company).order_by(Company.created_at.desc()).all()
    ctx = _admin_ctx(request, "Firmalar | Admin", admin_email=email)
    ctx.update({"companies": companies})
    return templates.TemplateResponse("admin_companies.html", ctx)


@app.post("/admin/login")
def admin_login(request: Request, email: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    ensure_initial_admin(db)

    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        ctx = _admin_ctx(request, "Admin Giriş", error="E-posta veya şifre hatalı.")
        return templates.TemplateResponse("admin_login.html", ctx)

    token = make_session(user.email)
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.set_cookie("cg_admin", token, httponly=True, samesite="lax", secure=True)
    return resp


@app.get("/admin/logout")
def admin_logout():
    resp = RedirectResponse(url="/admin", status_code=302)
    resp.delete_cookie("cg_admin")
    return resp


@app.post("/admin/companies/create")
def admin_company_create(
    request: Request,
    name: str = Form(...),
    sector: str = Form("defense"),
    db: Session = Depends(get_db),
):
    try:
        _ = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    sector = _sanitize_sector(sector)
    c = Company(name=name.strip(), sector=sector)
    db.add(c)
    db.commit()
    return RedirectResponse(url=f"/admin/companies/{c.id}", status_code=302)


@app.get("/admin/companies/{company_id}", response_class=HTMLResponse)
def admin_company_page(request: Request, company_id: int, db: Session = Depends(get_db)):
    try:
        email = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        ctx = _admin_ctx(request, "Firma | Admin", admin_email=email, error="Firma bulunamadı.")
        return templates.TemplateResponse("admin_companies.html", ctx)

    uploads = db.query(Upload).filter(Upload.company_id == company_id).order_by(Upload.uploaded_at.desc()).all()
    ctx = _admin_ctx(request, f"{company.name} | Admin", admin_email=email)
    ctx.update({"company": company, "uploads": uploads})
    return templates.TemplateResponse("admin_company.html", ctx)


@app.post("/admin/companies/{company_id}/upload")
def admin_upload_excel(
    request: Request,
    company_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        _ = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return RedirectResponse(url="/admin", status_code=302)

    if not file.filename.lower().endswith(".xlsx"):
        return RedirectResponse(url=f"/admin/companies/{company_id}", status_code=302)

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest = UPLOAD_DIR / f"company_{company_id}_{int(datetime.utcnow().timestamp())}_{safe_name}"
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    up = Upload(company_id=company_id, kind="excel", filename=safe_name, path=str(dest))
    db.add(up)
    db.commit()

    return RedirectResponse(url=f"/admin/companies/{company_id}", status_code=302)


@app.post("/admin/companies/{company_id}/analyze")
def admin_analyze(request: Request, company_id: int, db: Session = Depends(get_db)):
    try:
        email = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return RedirectResponse(url="/admin", status_code=302)

    last_upload = (
        db.query(Upload)
        .filter(Upload.company_id == company_id, Upload.kind == "excel")
        .order_by(Upload.uploaded_at.desc())
        .first()
    )
    if not last_upload:
        return RedirectResponse(url=f"/admin/companies/{company_id}", status_code=302)

    try:
        fin = parse_financials_xlsx(last_upload.path)
        result = analyze_financials(fin, sector=company.sector)
    except Exception as e:
        ctx = _admin_ctx(request, f"{company.name} | Admin", admin_email=email, error=str(e))
        uploads = db.query(Upload).filter(Upload.company_id == company_id).order_by(Upload.uploaded_at.desc()).all()
        ctx.update({"company": company, "uploads": uploads})
        return templates.TemplateResponse("admin_company.html", ctx)

    analysis = Analysis(company_id=company_id, result_json=json.dumps(result, ensure_ascii=False))
    db.add(analysis)
    db.commit()

    # PDF üretip dosyaya yaz (isteğe bağlı)
    sector_label = SECTOR_LABELS.get(company.sector, company.sector)
    pdf_bytes = build_admin_analysis_pdf(company.name, sector_label, result.get("bullets", [])[:10])
    pdf_path = UPLOAD_DIR / f"analysis_{analysis.id}.pdf"
    pdf_path.write_bytes(pdf_bytes)

    analysis.pdf_path = str(pdf_path)
    db.commit()

    return RedirectResponse(url=f"/admin/analyses/{analysis.id}", status_code=302)


@app.get("/admin/analyses/{analysis_id}", response_class=HTMLResponse)
def admin_analysis_view(request: Request, analysis_id: int, db: Session = Depends(get_db)):
    try:
        email = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == analysis.company_id).first()
    data = json.loads(analysis.result_json)

    sector_label = SECTOR_LABELS.get(company.sector, company.sector)
    ctx = _admin_ctx(request, "Analiz | Admin", admin_email=email)
    ctx.update({"company": company, "sector_label": sector_label, "bullets": data.get("bullets", [])[:10], "analysis_id": analysis.id})
    return templates.TemplateResponse("admin_analysis.html", ctx)


@app.get("/admin/analyses/{analysis_id}/pdf")
def admin_analysis_pdf(request: Request, analysis_id: int, db: Session = Depends(get_db)):
    try:
        _ = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        return RedirectResponse(url="/admin", status_code=302)

    if analysis.pdf_path and Path(analysis.pdf_path).exists():
        pdf_bytes = Path(analysis.pdf_path).read_bytes()
    else:
        company = db.query(Company).filter(Company.id == analysis.company_id).first()
        data = json.loads(analysis.result_json)
        sector_label = SECTOR_LABELS.get(company.sector, company.sector)
        pdf_bytes = build_admin_analysis_pdf(company.name, sector_label, data.get("bullets", [])[:10])

    filename = f"cashguard-admin-analiz-{analysis_id}.pdf"
    return StreamingResponse(BytesIO(pdf_bytes), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# =========================
# ✅ NEW: MAPPING DEBUG ROUTES
# =========================
@app.get("/admin/companies/{company_id}/mapping-debug", response_class=HTMLResponse)
def admin_company_mapping_debug(request: Request, company_id: int, db: Session = Depends(get_db)):
    """
    Son yüklenen Excel üzerinden parse_financials_xlsx çalıştırır ve mapping log'u gösterir.
    """
    try:
        email = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return RedirectResponse(url="/admin", status_code=302)

    last_upload = (
        db.query(Upload)
        .filter(Upload.company_id == company_id, Upload.kind == "excel")
        .order_by(Upload.uploaded_at.desc())
        .first()
    )
    if not last_upload:
        ctx = _admin_ctx(request, "Mapping Debug | Admin", admin_email=email, error="Bu firmaya ait Excel upload bulunamadı.")
        return templates.TemplateResponse("admin_company.html", ctx)

    try:
        fin = parse_financials_xlsx(last_upload.path)
        mlog = fin.get("mapping_log", {}) or {}
    except Exception as e:
        ctx = _admin_ctx(request, "Mapping Debug | Admin", admin_email=email, error=str(e))
        ctx.update({"company": company})
        return templates.TemplateResponse("admin_mapping_debug.html", ctx)

    ctx = _admin_ctx(request, "Mapping Debug | Admin", admin_email=email)
    ctx.update(
        {
            "company": company,
            "source": "last_upload",
            "upload_filename": last_upload.filename,
            "upload_path": last_upload.path,
            "bs_log": mlog.get("balance_sheet", []),
            "is_log": mlog.get("income_statement", []),
            "bs_unmapped": mlog.get("unmapped_balance_sheet", []),
            "is_unmapped": mlog.get("unmapped_income_statement", []),
            "year_bs": fin.get("year_bs"),
            "year_is": fin.get("year_is"),
        }
    )
    return templates.TemplateResponse("admin_mapping_debug.html", ctx)


@app.get("/admin/analyses/{analysis_id}/mapping-debug", response_class=HTMLResponse)
def admin_analysis_mapping_debug(request: Request, analysis_id: int, db: Session = Depends(get_db)):
    """
    Kayıtlı Analysis.result_json içindeki mapping_log'u gösterir.
    """
    try:
        email = require_admin(request, db)
    except PermissionError:
        return RedirectResponse(url="/admin", status_code=302)

    analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
    if not analysis:
        return RedirectResponse(url="/admin", status_code=302)

    company = db.query(Company).filter(Company.id == analysis.company_id).first()
    data = json.loads(analysis.result_json)
    mlog = (data.get("mapping_log") or {})

    ctx = _admin_ctx(request, "Mapping Debug | Admin", admin_email=email)
    ctx.update(
        {
            "company": company,
            "source": "analysis",
            "analysis_id": analysis.id,
            "bs_log": mlog.get("balance_sheet", []),
            "is_log": mlog.get("income_statement", []),
            "bs_unmapped": mlog.get("unmapped_balance_sheet", []),
            "is_unmapped": mlog.get("unmapped_income_statement", []),
            "year_bs": (data.get("meta") or {}).get("year_bs"),
            "year_is": (data.get("meta") or {}).get("year_is"),
        }
    )
    return templates.TemplateResponse("admin_mapping_debug.html", ctx)
