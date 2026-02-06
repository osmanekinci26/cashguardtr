from __future__ import annotations

from openpyxl import load_workbook
from typing import Dict, Tuple, List, Optional, Any

from app.fin_mapping import map_item_to_key

# Beklenen sheet adları:
SHEET_BS = "BILANCO"
SHEET_IS = "GELIR"


def _as_float(v: Any) -> float:
    try:
        if v is None:
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip()
        if s == "":
            return 0.0
        # TR format (1.234.567,89) gelirse:
        s = s.replace(".", "").replace(",", ".")
        return float(s)
    except Exception:
        return 0.0


def _find_kalem_headers(ws, max_scan_rows: int = 15) -> List[Tuple[int, int]]:
    """
    Sheet içinde 'KALEM' yazan hücreleri bulur.
    Bilanço sheet'inde genelde 2 tane olur (AKTİF / PASİF blokları).
    """
    headers = []
    for r in range(1, min(ws.max_row, max_scan_rows) + 1):
        for c in range(1, ws.max_column + 1):
            v = ws.cell(r, c).value
            if isinstance(v, str) and v.strip().upper() == "KALEM":
                headers.append((r, c))
    return headers


def _year_cols_from_header(ws, header_row: int, kalem_col: int, max_years: int = 6) -> List[Tuple[int, int]]:
    """
    'KALEM' hücresinin sağındaki yıl kolonlarını bulur.
    Örn: KALEM | 2024 | 2025  -> [(2024, col+1), (2025, col+2)]
    """
    out = []
    for i in range(1, max_years + 1):
        c = kalem_col + i
        v = ws.cell(header_row, c).value
        if isinstance(v, int) and 1900 <= v <= 2200:
            out.append((v, c))
        elif isinstance(v, float) and 1900 <= int(v) <= 2200:
            out.append((int(v), c))
        else:
            # yıl zinciri bozulduysa dur
            break
    return out


def _block_rows(ws, start_row: int, kalem_col: int, value_col: int) -> List[Tuple[str, float]]:
    """
    Bir blok: (kalem_col -> kalem adı) ve (value_col -> tutar)
    """
    items: List[Tuple[str, float]] = []
    for r in range(start_row, ws.max_row + 1):
        k = ws.cell(r, kalem_col).value
        if k is None:
            continue
        name = str(k).strip()
        if name == "":
            continue
        v = ws.cell(r, value_col).value
        items.append((name, _as_float(v)))
    return items


def _items_to_canonical(items: List[Tuple[str, float]]) -> Dict[str, float]:
    """
    Excel satır isimlerini fin_mapping üzerinden canonical key'lere çevirip toplar.
    """
    out: Dict[str, float] = {}
    for name, val in items:
        key = map_item_to_key(name)
        if not key:
            continue
        out[key] = out.get(key, 0.0) + float(val)
    return out


def parse_financials_xlsx(xlsx_path: str) -> dict:
    wb = load_workbook(xlsx_path, data_only=True)

    if SHEET_BS not in wb.sheetnames or SHEET_IS not in wb.sheetnames:
        raise ValueError(f"Excel sheet adları {SHEET_BS} ve {SHEET_IS} olmalı.")

    ws_bs = wb[SHEET_BS]
    ws_is = wb[SHEET_IS]

    # --- BILANCO: KALEM başlıklarını bul (genelde 2 adet: AKTIF ve PASIF)
    bs_headers = _find_kalem_headers(ws_bs)
    if not bs_headers:
        raise ValueError("BILANCO sheet içinde 'KALEM' başlığı bulunamadı.")

    # her header için yıl kolonlarını bul, en büyük yılı seç
    bs_blocks: List[List[Tuple[str, float]]] = []
    bs_years_found: List[int] = []

    for (hr, kc) in bs_headers:
        years = _year_cols_from_header(ws_bs, hr, kc)
        if not years:
            continue
        # en güncel yıl
        year, vc = sorted(years, key=lambda x: x[0])[-1]
        bs_years_found.append(year)
        items = _block_rows(ws_bs, start_row=hr + 1, kalem_col=kc, value_col=vc)
        bs_blocks.append(items)

    if not bs_blocks:
        raise ValueError("BILANCO sheet'inde yıl kolonları bulunamadı (KALEM'in sağında 2024/2025 gibi).")

    bs_year = max(bs_years_found) if bs_years_found else None
    bs_items = [it for block in bs_blocks for it in block]

    # --- GELIR: tek KALEM başlığı bekliyoruz
    is_headers = _find_kalem_headers(ws_is)
    if not is_headers:
        raise ValueError("GELIR sheet içinde 'KALEM' başlığı bulunamadı.")

    hr, kc = is_headers[0]
    years = _year_cols_from_header(ws_is, hr, kc)
    if not years:
        raise ValueError("GELIR sheet'inde yıl kolonları bulunamadı (KALEM'in sağında 2024/2025 gibi).")

    is_year, vc = sorted(years, key=lambda x: x[0])[-1]
    is_items = _block_rows(ws_is, start_row=hr + 1, kalem_col=kc, value_col=vc)

    # canonical dönüşüm
    bs_canon = _items_to_canonical(bs_items)
    is_canon = _items_to_canonical(is_items)

    return {
        "year_bs": bs_year,
        "year_is": is_year,
        "balance_sheet_raw": bs_items,        # (satır adı, değer)
        "income_statement_raw": is_items,     # (satır adı, değer)
        "balance_sheet": bs_canon,            # canonical -> değer
        "income_statement": is_canon,         # canonical -> değer
    }


def analyze_financials(fin: dict, sector: str) -> dict:
    """
    Sector: defense / construction / electrical / energy
    10 madde üretir (explainable).
    """
    bs = fin.get("balance_sheet", {}) or {}
    inc = fin.get("income_statement", {}) or {}

    def g(d: Dict[str, float], key: str) -> float:
        return float(d.get(key, 0.0) or 0.0)

    # --- Canonical'dan çek
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

    # --- Fallback: toplam kalem gelmediyse (bazı Excel’lerde toplam satır yok)
    if ca <= 0:
        ca = cash + ar + inv + g(bs, "other_current_assets") + g(bs, "other_receivables") + g(bs, "prepaid_expenses")
    if cl <= 0:
        # kısa vadeli yükümlülükler toplamı yoksa: ticari borç + KV finansal + vergi + karşılık + kiralama vb.
        cl = g(bs, "trade_payables") + debt_st + g(bs, "tax_liabilities") + g(bs, "provisions_st") + g(bs, "lease_liabilities_st")

    # --- Oranlar
    current_ratio = (ca / cl) if cl else None
    quick_ratio = ((ca - inv) / cl) if cl else None
    net_debt = (debt_st + debt_lt) - cash
    debt_to_equity = ((debt_st + debt_lt) / equity) if equity else None

    # faiz karşılama: önce finance_expense, yoksa interest_expense
    fin_cost = fin_exp if fin_exp else interest_exp
    interest_cover = (ebit / fin_cost) if fin_cost else None
    gross_margin = ((revenue - cogs) / revenue) if revenue else None

    sector_profiles = {
        "defense": {"wc_risk": "medium", "margin_expect": "medium"},
        "construction": {"wc_risk": "high", "margin_expect": "low"},
        "electrical": {"wc_risk": "high", "margin_expect": "medium"},
        "energy": {"wc_risk": "medium", "margin_expect": "low"},
    }
    prof = sector_profiles.get(sector, sector_profiles["defense"])

    bullets = []

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
        bullets.append("Borç/Özkaynak hesaplanamadı (özkaynak bulunamadı).")
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
    }
