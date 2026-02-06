# app/analysis_engine.py
from __future__ import annotations

from openpyxl import load_workbook
from typing import Dict, Any, Tuple, Optional

from app.fin_mapping import map_item_to_key, explain_key

# Beklenen sheet adları:
SHEET_BS = "BILANCO"
SHEET_IS = "GELIR"


def _to_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except Exception:
        return None


def _read_two_year_block(
    ws,
    item_col: int,
    y1_col: int,
    y2_col: int,
    years: Tuple[str, str] = ("2024", "2025"),
) -> Tuple[Dict[str, Dict[str, float]], list]:
    """
    Generic reader for a block:
      item_col: item text
      y1_col: year1 values
      y2_col: year2 values
    Returns:
      data_by_year: { "2024": {canonical_key: value}, "2025": {...} }
      unmapped: [raw_item_str,...]
    """
    y1, y2 = years
    data_by_year: Dict[str, Dict[str, float]] = {y1: {}, y2: {}}
    unmapped: list = []

    for r in range(1, ws.max_row + 1):
        raw_item = ws.cell(row=r, column=item_col).value
        if raw_item is None:
            continue
        raw_item_str = str(raw_item).strip()
        if raw_item_str == "":
            continue

        v1 = _to_float(ws.cell(row=r, column=y1_col).value)
        v2 = _to_float(ws.cell(row=r, column=y2_col).value)

        # satırda değer yoksa geç
        if v1 is None and v2 is None:
            continue

        key = map_item_to_key(raw_item_str)
        if not key:
            unmapped.append(raw_item_str)
            continue

        if v1 is not None:
            data_by_year[y1][key] = v1
        if v2 is not None:
            data_by_year[y2][key] = v2

    return data_by_year, unmapped


def parse_financials_xlsx(xlsx_path: str) -> dict:
    """
    Bu parse, senin excel formatına göre çalışır:

    BILANCO:
      Sol blok:  Kalem=B(2), 2024=D(4), 2025=E(5)
      Sağ blok:  Kalem=F(6), 2024=H(8), 2025=I(9)

    GELIR:
      Kalem=B(2), 2024=C(3), 2025=D(4)

    Çıktı:
      {
        "balance_sheet_by_year": {"2024": {...}, "2025": {...}},
        "income_statement_by_year": {"2024": {...}, "2025": {...}},
        "balance_sheet": {...},   # default year seçili
        "income_statement": {...},
        "default_year": "2025" veya "2024",
        "unmapped": {"balance": [...], "income": [...]}
      }
    """
    wb = load_workbook(xlsx_path, data_only=True)

    if SHEET_BS not in wb.sheetnames or SHEET_IS not in wb.sheetnames:
        raise ValueError(f"Excel sheet adları {SHEET_BS} ve {SHEET_IS} olmalı.")

    ws_bs = wb[SHEET_BS]
    ws_is = wb[SHEET_IS]

    # --- Balance sheet: two blocks ---
    bs_left, unm_bs_left = _read_two_year_block(ws_bs, item_col=2, y1_col=4, y2_col=5, years=("2024", "2025"))
    bs_right, unm_bs_right = _read_two_year_block(ws_bs, item_col=6, y1_col=8, y2_col=9, years=("2024", "2025"))

    balance_by_year = {"2024": {}, "2025": {}}
    for y in ("2024", "2025"):
        balance_by_year[y].update(bs_left.get(y, {}))
        balance_by_year[y].update(bs_right.get(y, {}))

    # --- Income statement: single block ---
    inc_by_year, unm_income = _read_two_year_block(ws_is, item_col=2, y1_col=3, y2_col=4, years=("2024", "2025"))

    # default year: 2025 varsa 2025, yoksa 2024
    default_year = "2025" if len(balance_by_year.get("2025", {})) or len(inc_by_year.get("2025", {})) else "2024"

    return {
        "balance_sheet_by_year": balance_by_year,
        "income_statement_by_year": inc_by_year,
        "balance_sheet": balance_by_year.get(default_year, {}),
        "income_statement": inc_by_year.get(default_year, {}),
        "default_year": default_year,
        "unmapped": {
            "balance": sorted(set(unm_bs_left + unm_bs_right)),
            "income": sorted(set(unm_income)),
        },
    }


def analyze_financials(fin: dict, sector: str) -> dict:
    """
    Sector: defense / construction / electrical / energy
    Canonical key'ler üzerinden oranları hesaplar.
    """
    bs = fin.get("balance_sheet", {}) or {}
    inc = fin.get("income_statement", {}) or {}

    # Canonical getter
    def g(d, key: str) -> float:
        v = d.get(key, None)
        try:
            return float(v) if v is not None else 0.0
        except Exception:
            return 0.0

    # ---- Canonical kalemler
    cash = g(bs, "cash_and_equivalents")
    ar = g(bs, "trade_receivables")
    inv = g(bs, "inventories")

    # Not: bazı Excel’lerde “dönen varlıklar toplamı” gelmeyebilir.
    # Biz mümkün olduğunca toplamı yakalamaya çalışıyoruz:
    other_ca = g(bs, "other_current_assets") + g(bs, "prepaid_expenses") + g(bs, "other_receivables")
    ca_proxy = cash + ar + inv + other_ca  # minimum proxy

    cl = g(bs, "short_term_liabilities")
    debt_st = g(bs, "short_term_fin_debt")
    debt_lt = g(bs, "long_term_fin_debt")
    equity = g(bs, "equity_total")

    revenue = g(inc, "revenue")
    cogs = g(inc, "cogs")
    opex = g(inc, "opex")
    ebit = g(inc, "ebit")
    fin_exp = g(inc, "finance_expense") or g(inc, "interest_expense")

    # ---- Oranlar
    current_ratio = (ca_proxy / cl) if cl else None
    quick_ratio = ((ca_proxy - inv) / cl) if cl else None
    net_debt = (debt_st + debt_lt) - cash
    debt_to_equity = ((debt_st + debt_lt) / equity) if equity else None
    interest_cover = (ebit / fin_exp) if fin_exp else None
    gross_margin = ((revenue - cogs) / revenue) if revenue else None
    nwc = ca_proxy - cl

    # ---- Sektör profili (yorum tonu)
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
        bullets.append("Faiz karşılama oranı hesaplanamadı (finansman gideri bulunamadı/0).")
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
        if gm < 10 and prof["margin_expect"] != "low":
            bullets.append(f"Brüt marj düşük (%{gm:.1f}). Fiyatlama/iskonto/kur etkisi kontrol edilmeli.")
        else:
            bullets.append(f"Brüt marj yaklaşık %{gm:.1f}. (Sektör kıyasına göre yorumlanmalı.)")

    # 7) İşletme sermayesi
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

    # 8) Nakit pozisyonu
    if cash <= 0:
        bullets.append("Nakit kalemi düşük/0 görünüyor. Günlük nakit akışı takibi şart.")
    else:
        bullets.append("Nakit var; kritik soru: bu nakit, kısa vadeli borç ve faaliyet giderlerini kaç ay taşır?")

    # 9) Alacak kalitesi
    if ar > 0 and revenue > 0 and (ar / revenue) > 0.35:
        bullets.append("Alacakların ciroya oranı yüksek görünüyor. Tahsilat disiplini ve müşteri limitleri önemli.")
    else:
        bullets.append("Alacak/ciro oranı makul seviyede görünüyor (veri uygunsa).")

    # 10) Yönetim aksiyonu
    bullets.append("Öneri: Haftalık 13-hafta nakit projeksiyonu + borç vade haritası çıkarıp tek sayfada izleyelim.")

    return {
        "metrics": {
            "current_ratio": current_ratio,
            "quick_ratio": quick_ratio,
            "net_debt": net_debt,
            "debt_to_equity": debt_to_equity,
            "interest_cover": interest_cover,
            "gross_margin": gross_margin,
            "nwc": nwc,
            "year": fin.get("default_year"),
        },
        "bullets": bullets[:10],
        "unmapped": fin.get("unmapped", {}),
        "debug": {
            # İstersen admin ekranda göstermek için:
            "cash": cash,
            "ar": ar,
            "inv": inv,
            "ca_proxy": ca_proxy,
            "cl": cl,
            "debt_st": debt_st,
            "debt_lt": debt_lt,
            "equity": equity,
            "revenue": revenue,
            "ebit": ebit,
            "fin_exp": fin_exp,
        },
    }
