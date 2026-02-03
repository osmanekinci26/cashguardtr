def calculate_risk(
    sector: str,

    collection_days: int,
    payable_days: int,
    fx_debt_ratio: int,
    fx_revenue_ratio: int,
    cash_buffer_months: int,
    top_customer_share: int,

    top_customer_2m_gap_month: int,
    unplanned_deferral_12m: str,

    delay_issue: str,
    short_debt_ratio: int,
    limit_pressure: str,
    hedging: str,
):
    # ----------------------------
    # Sektör ağırlık profilleri
    # ----------------------------
    PROFILES = {
        "defense": {
            "gap": 1.00,
            "fx": 1.00,
            "cash": 1.00,
            "conc": 1.00,
            "delay": 1.00,
            "shortdebt": 1.00,
            "limit": 1.00,
            "hedge_penalty": 1.00,
            "hedge_bonus": 1.00,
            "top2m": 1.00,
            "deferral": 1.00,
        },
        "construction": {
            "gap": 0.80,          # vade uzunluğu sektör normu
            "fx": 1.00,
            "cash": 1.25,         # nakit kritik
            "conc": 1.10,
            "delay": 1.10,
            "shortdebt": 1.10,
            "limit": 1.10,
            "hedge_penalty": 1.00,
            "hedge_bonus": 1.00,
            "top2m": 1.20,        # 2 ay tahsilat yoksa kırılma sert
            "deferral": 1.25,     # plan dışı erteleme = alarm
        },
        "electrical": {
            "gap": 0.90,
            "fx": 1.10,           # ithal malzeme/ekipman etkisi
            "cash": 1.25,
            "conc": 1.05,
            "delay": 1.10,
            "shortdebt": 1.10,
            "limit": 1.05,
            "hedge_penalty": 1.05,
            "hedge_bonus": 1.00,
            "top2m": 1.20,
            "deferral": 1.20,
        },
        "energy": {
            "gap": 1.00,
            "fx": 1.20,           # FX borç/gelir uyumu kritik
            "cash": 1.00,
            "conc": 0.90,         # az sayıda offtaker normal olabilir
            "delay": 1.00,
            "shortdebt": 1.00,
            "limit": 0.95,
            "hedge_penalty": 1.20,  # hedge yoksa daha sert
            "hedge_bonus": 1.20,    # hedge güçlü ise bonus daha değerli
            "top2m": 1.05,
            "deferral": 1.10,
        },
    }

    sector = (sector or "defense").strip().lower()
    if sector not in PROFILES:
        sector = "defense"
    W = PROFILES[sector]

    score = 100
    messages = []

    def penalty(points: int, key: str):
        nonlocal score
        score -= int(round(points * W[key]))

    # 1) Vade makası (tahsilat - ödeme)
    gap = collection_days - payable_days
    if gap > 90:
        penalty(25, "gap")
        messages.append("Vade makası çok yüksek (tahsilat-ödeme farkı 90+ gün).")
    elif gap > 45:
        penalty(12, "gap")
        messages.append("Vade makası yüksek (45+ gün).")

    # 2) Kur riski: döviz borcu - döviz gelir dengesi
    fx_mismatch = fx_debt_ratio - fx_revenue_ratio
    if fx_mismatch > 30:
        penalty(25, "fx")
        messages.append("Döviz uyumsuzluğu yüksek (döviz borcu gelirden belirgin fazla).")
    elif fx_mismatch > 10:
        penalty(12, "fx")
        messages.append("Döviz uyumsuzluğu var (borç gelirden fazla).")

    # 3) Nakit tamponu
    if cash_buffer_months < 3:
        penalty(25, "cash")
        messages.append("Nakit tamponu yetersiz (3 aydan az).")
    elif cash_buffer_months < 6:
        penalty(12, "cash")
        messages.append("Nakit tamponu sınırlı (6 aydan az).")

    # 4) Müşteri yoğunlaşması
    if top_customer_share >= 70:
        penalty(18, "conc")
        messages.append("Müşteri yoğunlaşması çok yüksek (en büyük müşteri %70+).")
    elif top_customer_share >= 50:
        penalty(10, "conc")
        messages.append("Müşteri yoğunlaşması yüksek (en büyük müşteri %50+).")

    # 5) Top müşteri 2 ay ödeme yapmazsa hangi ay nakit açığı?
    # Daha erken açık = daha riskli
    # 1-2 ay: sert, 3-4 orta, 5-6 düşük, 99: ceza yok
    if top_customer_2m_gap_month in [1, 2]:
        penalty(14, "top2m")
        messages.append("En büyük müşteri 2 ay ödeme yapmazsa çok erken nakit açığı oluşuyor (1-2 ay).")
    elif top_customer_2m_gap_month in [3, 4]:
        penalty(8, "top2m")
        messages.append("En büyük müşteri 2 ay ödeme yapmazsa orta vadede nakit açığı oluşuyor (3-4 ay).")
    elif top_customer_2m_gap_month in [5, 6]:
        penalty(4, "top2m")

    # 6) Plan dışı ödeme ertelemesi (12 ay)
    if (unplanned_deferral_12m or "").upper() == "YES":
        penalty(10, "deferral")
        messages.append("Son 12 ayda plan dışı ödeme ertelemesi yapılmış (likidite stresi sinyali).")

    # 7) Gecikme
    if delay_issue == "yes":
        penalty(10, "delay")
        messages.append("Son 12 ayda gecikme / vade uzaması yaşanmış.")

    # 8) Kısa vadeli borç baskısı
    if short_debt_ratio >= 60:
        penalty(15, "shortdebt")
        messages.append("12 ay içinde vadesi dolacak borç oranı çok yüksek (%60+).")
    elif short_debt_ratio >= 35:
        penalty(8, "shortdebt")
        messages.append("12 ay içinde vadesi dolacak borç oranı yüksek (%35+).")

    # 9) Limit/teminat baskısı
    if limit_pressure == "yes":
        penalty(12, "limit")
        messages.append("Son 6 ayda limit daralması/teminat baskısı sinyali var.")

    # 10) Hedge
    if hedging == "none":
        score -= int(round(8 * W["hedge_penalty"]))
        messages.append("Kur riski için hedge mekanizması yok.")
    elif hedging == "strong":
        score += int(round(4 * W["hedge_bonus"]))

    score = max(0, min(100, score))

    if score >= 75:
        level = "GREEN"
    elif score >= 50:
        level = "YELLOW"
    else:
        level = "RED"

    if not messages:
        messages.append("Risk göstergeleri şu an kontrollü görünüyor.")

    messages = messages[:3]
    return score, level, messages
