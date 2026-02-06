from openpyxl import load_workbook

# Beklenen sheet adları:
SHEET_BS = "BILANCO"
SHEET_IS = "GELIR"


def _sheet_to_dict(ws):
    """
    A sütunu: kalem adı
    B sütunu: tutar
    """
    data = {}
    for r in range(1, ws.max_row + 1):
        k = ws.cell(row=r, column=1).value
        v = ws.cell(row=r, column=2).value
        if k is None:
            continue
        key = str(k).strip().upper()
        if key == "":
            continue
        try:
            val = float(v) if v is not None else 0.0
        except Exception:
            val = 0.0
        data[key] = val
    return data


def parse_financials_xlsx(xlsx_path: str) -> dict:
    wb = load_workbook(xlsx_path, data_only=True)

    if SHEET_BS not in wb.sheetnames or SHEET_IS not in wb.sheetnames:
        raise ValueError(f"Excel sheet adları {SHEET_BS} ve {SHEET_IS} olmalı.")

    bs = _sheet_to_dict(wb[SHEET_BS])
    inc = _sheet_to_dict(wb[SHEET_IS])

    return {"balance_sheet": bs, "income_statement": inc}


def analyze_financials(fin: dict, sector: str) -> dict:
    """
    Sector: defense / construction / electrical / energy
    Basit, explainable kural motoru: 10 madde üretir.
    """
    bs = fin["balance_sheet"]
    inc = fin["income_statement"]

    # ---- Beklenen kalemler (esnek arama: bazı alternatifler)
    def g(d, *keys):
        for k in keys:
            k = k.upper()
            if k in d:
                return d[k]
        return 0.0

    cash = g(bs, "NAKIT", "KASA", "KASA+BANKA", "KASA VE BANKA")
    ar = g(bs, "TICARI ALACAKLAR", "ALACAKLAR")
    inv = g(bs, "STOKLAR", "STOK")
    ca = g(bs, "DÖNEN VARLIKLAR", "DONEN VARLIKLAR")
    cl = g(bs, "KISA VADELI YUKUMLULUKLER", "KISA VADELİ YÜKÜMLÜLÜKLER", "KV BORCLAR")
    debt_st = g(bs, "KISA VADELI FINANSAL BORCLAR", "KV FINANSAL BORC")
    debt_lt = g(bs, "UZUN VADELI FINANSAL BORCLAR", "UV FINANSAL BORC")
    equity = g(bs, "OZKAYNAKLAR", "ÖZKAYNAKLAR")
    total_assets = g(bs, "TOPLAM VARLIKLAR", "AKTIF TOPLAM")

    revenue = g(inc, "HASILAT", "NET SATISLAR", "CIRO")
    cogs = g(inc, "SATISLARIN MALIYETI", "SATIŞLARIN MALİYETİ")
    opex = g(inc, "FAALIYET GIDERLERI", "FAALİYET GİDERLERİ")
    ebit = g(inc, "ESAS FAALIYET KARI", "FAALİYET KARI", "EBIT")
    fin_exp = g(inc, "FINANSMAN GIDERLERI", "FİNANSMAN GİDERLERİ")

    # ---- Oranlar
    current_ratio = (ca / cl) if cl else None
    quick_ratio = ((ca - inv) / cl) if cl else None
    net_debt = (debt_st + debt_lt) - cash
    debt_to_equity = ((debt_st + debt_lt) / equity) if equity else None
    interest_cover = (ebit / fin_exp) if fin_exp else None
    gross_margin = ((revenue - cogs) / revenue) if revenue else None

    # ---- Sektöre göre “hassasiyet” ağırlığı (yorum tonu)
    # (MVP: scoring değil, sadece çıkarım üretirken eşiklerle oynuyoruz)
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
    if total_assets:
        bullets.append(f"Net borç (finansal borç - nakit): {net_debt:,.0f} (yaklaşık).")
    else:
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

    # 7) İşletme sermayesi kırılganlığı (sektöre göre)
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

    # 8) Nakit pozisyonu
    if cash <= 0:
        bullets.append("Nakit kalemi düşük/0 görünüyor. Günlük nakit akışı takibi şart.")
    else:
        bullets.append("Nakit var; kritik soru: bu nakit, kısa vadeli borç ve faaliyet giderlerini kaç ay taşır?")

    # 9) Kalem kalitesi (basit sinyal)
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
        },
        "bullets": bullets[:10],
    }
