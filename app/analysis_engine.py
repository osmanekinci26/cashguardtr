from __future__ import annotations

from openpyxl import load_workbook
from typing import Dict, Tuple, List, Optional, Any

from app.fin_mapping import map_item_to_key, normalize_text, explain_key

# Beklenen sheet adları:
SHEET_BS = "BILANCO"
SHEET_IS = "GELIR"


# =========================
# Helpers
# =========================
def _as_float(v: Any) -> float:
    """
    Excel hücresinden güvenli float dönüşümü.
    TR format: 1.234.567,89
    Negatif: (1.234) veya -1.234
    """
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)

        s = str(v).strip()
        if s == "":
            return 0.0

        # Negatif parantez: (1.234,56)
        neg = False
        if s.startswith("(") and s.endswith(")"):
            neg = True
            s = s[1:-1].strip()

        # bazı excel export: " - " / "—"
        if s in {"-", "—", "–"}:
            return 0.0

        # TR format normalize
        s = s.replace(".", "").replace(",", ".")
        x = float(s)

        return -x if neg else x
    except Exception:
        return 0.0


def _find_kalem_headers(ws, max_scan_rows: int = 25) -> List[Tuple[int, int]]:
    """
    Sheet içinde 'KALEM' yazan hücreleri bulur.
    Bilanço sheet'inde genelde 2 tane olur (AKTİF / PASİF blokları).
    """
    headers: List[Tuple[int, int]] = []
    for r in range(1, min(ws.max_row, max_scan_rows) + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and v.strip().upper() == "KALEM":
                headers.append((r, c))
    headers.sort(key=lambda x: (x[0], x[1]))
    return headers


def _year_cols_from_header(ws, header_row: int, kalem_col: int, max_years: int = 10) -> List[Tuple[int, int]]:
    """
    'KALEM' hücresinin sağındaki yıl kolonlarını bulur.
    Örn: KALEM | 2022 | % | 2023 -> [(2022, col+1), (2023, col+3)]
    Arada % gibi kolonlar olabiliyor.
    """
    out: List[Tuple[int, int]] = []
    scanned = 0
    c = kalem_col + 1

    while c <= ws.max_column and scanned < 25 and len(out) < max_years:
        v = ws.cell(header_row, c).value
        yr: Optional[int] = None

        if isinstance(v, int) and 1900 <= v <= 2200:
            yr = v
        elif isinstance(v, float) and 1900 <= int(v) <= 2200:
            yr = int(v)
        elif isinstance(v, str):
            vv = v.strip()
            if vv.isdigit():
                iv = int(vv)
                if 1900 <= iv <= 2200:
                    yr = iv

        if yr is not None:
            out.append((yr, c))

        c += 1
        scanned += 1

    out.sort(key=lambda x: x[0])
    return out


def _is_noise_row(name: str) -> bool:
    """
    Başlık/alt başlık satırları.
    Burayı çok agresif yaparsan oranlar bozulur.
    """
    n = str(name).strip().upper()
    if n in {"AKTIF", "PASIF", "VARLIKLAR", "KAYNAKLAR"}:
        return True
    if n.startswith("GENEL TOPLAM"):
        return True
    if n == "TOPLAM":
        return True
    return False


def _block_rows(
    ws,
    start_row: int,
    end_row: int,
    kalem_col: int,
    value_col: int,
    stop_on_empty_streak: int = 25,
) -> List[Tuple[str, float]]:
    """
    Bir blok: (kalem_col -> kalem adı) ve (value_col -> tutar)
    Excel'in aşağısındaki boş/çöp alanları okumamak için
    ardışık boş satır sayısı belirli bir eşiği geçince durur.
    """
    items: List[Tuple[str, float]] = []
    empty_streak = 0

    for r in range(start_row, min(end_row, ws.max_row) + 1):
        k = ws.cell(r, kalem_col).value

        if k is None or str(k).strip() == "":
            empty_streak += 1
            if empty_streak >= stop_on_empty_streak:
                break
            continue

        empty_streak = 0
        name = str(k).strip()

        if _is_noise_row(name):
            continue

        v = ws.cell(r, value_col).value
        items.append((name, _as_float(v)))

    return items


# =========================
# Mapping guard (TOTAL mis-map fix)
# =========================
TOTAL_KEYS = {
    "current_assets_total",
    "non_current_assets_total",
    "total_assets",
    "short_term_liabilities",
    "long_term_liabilities",
    "total_liabilities",
    "equity_total",
    "total_liabilities_and_equity",
}

def _is_totalish(norm_name: str) -> bool:
    """
    Satır gerçek bir toplam satırı mı?
    En temel kural: 'toplam' kelimesi geçsin veya bilinen total ifadeler olsun.
    """
    n = norm_name
    if "toplam" in n:
        return True
    # bazı şablonlarda toplam yazmadan "donen varliklar" tek başına total gibi kullanılır
    if n in {
        "donen varliklar",
        "duran varliklar",
        "kisa vadeli yukumlulukler",
        "uzun vadeli yukumlulukler",
        "ozkaynaklar",
        "aktif toplami",
        "pasif toplami",
        "toplam varliklar",
        "toplam kaynaklar",
    }:
        return True
    return False


def _safe_map_item_to_key(raw_name: str) -> Optional[str]:
    """
    fin_mapping içindeki contains-match'in yanlışlıkla TOTAL key üretmesini engeller.
    Örn: 'diger donen varliklar' içinde 'donen varliklar' geçiyor diye
         current_assets_total'a gitmesin.
    """
    norm = normalize_text(raw_name)
    key = map_item_to_key(raw_name)

    if not key:
        return None

    # total key geldiyse ama satır total değilse iptal et
    if key in TOTAL_KEYS and not _is_totalish(norm):
        return None

    return key


def _items_to_canonical(items: List[Tuple[str, float]]) -> Tuple[Dict[str, float], List[Dict[str, Any]]]:
    """
    Excel satır isimlerini canonical key'lere çevirip toplar.
    Ek olarak mapping log döndürür (debug için).
    """
    out: Dict[str, float] = {}
    log: List[Dict[str, Any]] = []

    for name, val in items:
        n = normalize_text(name)
        key = _safe_map_item_to_key(name)

        if key:
            out[key] = out.get(key, 0.0) + float(val)

        log.append({
            "raw": name,
            "norm": n,
            "key": key,
            "key_label": explain_key(key) if key else None,
            "value": float(val),
        })

    return out, log


# =========================
# Parse
# =========================
def parse_financials_xlsx(xlsx_path: str) -> dict:
    wb = load_workbook(xlsx_path, data_only=True)

    if SHEET_BS not in wb.sheetnames or SHEET_IS not in wb.sheetnames:
        raise ValueError(f"Excel sheet adları {SHEET_BS} ve {SHEET_IS} olmalı.")

    ws_bs = wb[SHEET_BS]
    ws_is = wb[SHEET_IS]

    # ========== BILANCO ==========
    bs_headers = _find_kalem_headers(ws_bs)
    if not bs_headers:
        raise ValueError("BILANCO sheet içinde 'KALEM' başlığı bulunamadı.")

    bs_years_found: List[int] = []
    bs_items_all: List[Tuple[str, float]] = []

    # Header’ları bloklara böl: her KALEM, bir sonraki KALEM’e kadar
    for idx, (hr, kc) in enumerate(bs_headers):
        next_hr = bs_headers[idx + 1][0] if idx + 1 < len(bs_headers) else ws_bs.max_row + 1
        end_row = next_hr - 1

        years = _year_cols_from_header(ws_bs, hr, kc)
        if not years:
            continue

        # en güncel yıl ve kolon
        year, vc = years[-1]
        bs_years_found.append(year)

        items = _block_rows(ws_bs, start_row=hr + 1, end_row=end_row, kalem_col=kc, value_col=vc)
        bs_items_all.extend(items)

    if not bs_items_all:
        raise ValueError("BILANCO sheet'inde okunabilir satır bulunamadı (KALEM blokları boş görünüyor).")

    bs_year = max(bs_years_found) if bs_years_found else None

    # ========== GELIR ==========
    is_headers = _find_kalem_headers(ws_is)
    if not is_headers:
        raise ValueError("GELIR sheet içinde 'KALEM' başlığı bulunamadı.")

    hr, kc = is_headers[0]
    years = _year_cols_from_header(ws_is, hr, kc)
    if not years:
        raise ValueError("GELIR sheet'inde yıl kolonları bulunamadı (KALEM'in sağında 2022/2023 gibi).")

    is_year, vc = years[-1]
    next_hr = is_headers[1][0] if len(is_headers) > 1 else ws_is.max_row + 1
    is_items = _block_rows(ws_is, start_row=hr + 1, end_row=next_hr - 1, kalem_col=kc, value_col=vc)

    # canonical dönüşüm + mapping log
    bs_canon, bs_log = _items_to_canonical(bs_items_all)
    is_canon, is_log = _items_to_canonical(is_items)

    bs_unmapped = [x for x in bs_log if not x["key"]]
    is_unmapped = [x for x in is_log if not x["key"]]

    return {
        "year_bs": bs_year,
        "year_is": is_year,

        "balance_sheet_raw": bs_items_all,
        "income_statement_raw": is_items,

        "balance_sheet": bs_canon,
        "income_statement": is_canon,

        # Debug
        "mapping_log": {
            "balance_sheet": bs_log,
            "income_statement": is_log,
            "unmapped_balance_sheet": bs_unmapped,
            "unmapped_income_statement": is_unmapped,
        },
    }


# =========================
# Analyze
# =========================
def analyze_financials(fin: dict, sector: str) -> dict:
    """
    Sector: defense / construction / electrical / energy
    10 madde üretir.
    """
    bs = fin.get("balance_sheet", {}) or {}
    inc = fin.get("income_statement", {}) or {}

    def g(d: Dict[str, float], key: str) -> float:
        return float(d.get(key, 0.0) or 0.0)

    # Canonical
    cash = g(bs, "cash_and_equivalents")
    ar = g(bs, "trade_receivables")
    inv = g(bs, "inventories")

    ca = g(bs, "current_assets_total")
    cl = g(bs, "short_term_liabilities")

    debt_st = g(bs, "short_term_fin_debt")
    debt_lt = g(bs, "long_term_fin_debt")
    equity = g(bs, "equity_total")
    total_assets = g(bs, "total_assets")

    revenue = g(inc, "revenue")
    cogs = g(inc, "cogs")
    ebit = g(inc, "ebit")
    fin_exp = g(inc, "finance_expense")
    interest_exp = g(inc, "interest_expense")

    # Fallback totals
    if ca <= 0:
        ca = (
            cash
            + ar
            + inv
            + g(bs, "other_current_assets")
            + g(bs, "other_receivables")
            + g(bs, "prepaid_expenses")
        )

    if cl <= 0:
        cl = (
            g(bs, "trade_payables")
            + debt_st
            + g(bs, "tax_liabilities")
            + g(bs, "provisions_st")
            + g(bs, "lease_liabilities_st")
        )

    # Ratios
    current_ratio = (ca / cl) if cl else None
    quick_ratio = ((ca - inv) / cl) if cl else None
    net_debt = (debt_st + debt_lt) - cash

    # equity 0/negatifse ratio anlamlı değil
    debt_to_equity = ((debt_st + debt_lt) / equity) if equity and equity > 0 else None

    fin_cost = fin_exp if fin_exp else interest_exp
    interest_cover = (ebit / fin_cost) if fin_cost else None
    gross_margin = ((revenue - cogs) / revenue) if revenue else None

    sector_profiles = {
        "defense": {"wc_risk": "medium"},
        "construction": {"wc_risk": "high"},
        "electrical": {"wc_risk": "high"},
        "energy": {"wc_risk": "medium"},
    }
    prof = sector_profiles.get(sector, sector_profiles["defense"])

    bullets: List[str] = []

    # 1) Likidite
    if current_ratio is None:
        bullets.append("Cari oran hesaplanamadı (kısa vadeli yükümlülük bulunamadı).")
    elif current_ratio < 1:
        bullets.append(f"Cari oran düşük ({current_ratio:.2f}). Kısa vadeli ödeme baskısı riski var.")
    elif current_ratio < 1.5:
        bullets.append(f"Cari oran sınırda ({current_ratio:.2f}). Nakit tamponu güçlendirilebilir.")
    else:
        bullets.append(f"Cari oran iyi ({current_ratio:.2f}). Kısa vadeli likidite daha rahat görünüyor.")

    # 2) Asit-test
    if quick_ratio is not None:
        if quick_ratio < 0.8:
            bullets.append(f"Asit-test oranı düşük ({quick_ratio:.2f}). Stoksuz çevrimde zorlanma riski.")
        else:
            bullets.append(f"Asit-test oranı kabul edilebilir ({quick_ratio:.2f}).")

    # 3) Net borç
    bullets.append(f"Net borç (finansal borç - nakit): {net_debt:,.0f} (yaklaşık).")

    # 4) Borç/Özkaynak
    if debt_to_equity is None:
        bullets.append("Borç/Özkaynak hesaplanamadı (özkaynak bulunamadı veya 0/negatif).")
    else:
        if debt_to_equity > 2.0:
            bullets.append(f"Borç/Özkaynak yüksek ({debt_to_equity:.2f}). Finansal kaldıraç riski artmış.")
        elif debt_to_equity > 1.0:
            bullets.append(f"Borç/Özkaynak orta ({debt_to_equity:.2f}). Borç yönetimi disiplin gerektiriyor.")
        else:
            bullets.append(f"Borç/Özkaynak makul ({debt_to_equity:.2f}).")

    # 5) Faiz karşılama
    if interest_cover is None:
        bullets.append("Faiz karşılama oranı hesaplanamadı (finansman/faiz gideri bulunamadı/0).")
    else:
        if interest_cover < 1.5:
            bullets.append(f"Faiz karşılama zayıf ({interest_cover:.2f}). Faiz yükü operasyonu sıkıştırıyor olabilir.")
        elif interest_cover < 3:
            bullets.append(f"Faiz karşılama sınırda ({interest_cover:.2f}). Faiz şoklarına hassasiyet var.")
        else:
            bullets.append(f"Faiz karşılama iyi ({interest_cover:.2f}).")

    # 6) Brüt marj
    if gross_margin is not None:
        gm = gross_margin * 100
        bullets.append(f"Brüt marj yaklaşık %{gm:.1f}. (Sektör kıyasına göre yorumlanmalı.)")

    # 7) İşletme sermayesi
    nwc = ca - cl
    if prof["wc_risk"] == "high":
        if nwc < 0:
            bullets.append("Net işletme sermayesi negatif. Proje/taahhüt işlerinde nakit kırılması riski yüksek.")
        else:
            bullets.append("Net işletme sermayesi pozitif; yine de proje tahsilat/avans dengesi yakından izlenmeli.")
    else:
        if nwc < 0:
            bullets.append("Net işletme sermayesi negatif. Vade yönetimi ve kısa vade refinansman planı kritik.")
        else:
            bullets.append("Net işletme sermayesi pozitif. Vade makası bozulursa tampon azalabilir.")

    # 8) Nakit
    if cash <= 0:
        bullets.append("Nakit kalemi düşük/0 görünüyor. Günlük nakit akışı takibi şart.")
    else:
        bullets.append("Nakit var; kritik soru: bu nakit, kısa vadeli borç ve faaliyet giderlerini kaç ay taşır?")

    # 9) Alacak/ciro
    if ar > 0 and revenue > 0 and (ar / revenue) > 0.35:
        bullets.append("Alacakların ciroya oranı yüksek görünüyor. Tahsilat disiplini ve müşteri limitleri önemli.")
    else:
        bullets.append("Alacak/ciro oranı makul seviyede görünüyor (veri uygunsa).")

    # 10) Aksiyon
    bullets.append("Öneri: Haftalık 13-hafta nakit projeksiyonu + borç vade haritası çıkarıp tek sayfada izleyelim.")

    return {
        "meta": {"year_bs": fin.get("year_bs"), "year_is": fin.get("year_is")},
        "metrics": {
            "current_ratio": current_ratio,
            "quick_ratio": quick_ratio,
            "net_debt": net_debt,
            "debt_to_equity": debt_to_equity,
            "interest_cover": interest_cover,
            "gross_margin": gross_margin,
            "nwc": nwc,
            "revenue": revenue,
            "cogs": cogs,
            "cash": cash,
            "current_assets": ca,
            "current_liabilities": cl,
            "equity": equity,
            "total_assets": total_assets,
        },
        "bullets": bullets[:10],
        "mapping_log": fin.get("mapping_log", {}),
    }
