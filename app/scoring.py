def calculate_risk(
    collection_days: int,
    payable_days: int,
    fx_debt_ratio: int,
    fx_revenue_ratio: int,
    cash_buffer_months: int,
    top_customer_share: int,
    delay_issue: str,
    short_debt_ratio: int,
    limit_pressure: str,
    hedging: str
):
    score = 100
    messages = []

    # 1) Vade makası (tahsilat - ödeme)
    gap = collection_days - payable_days
    if gap > 90:
        score -= 25
        messages.append("Vade makası çok yüksek (tahsilat-ödeme farkı 90+ gün).")
    elif gap > 45:
        score -= 12
        messages.append("Vade makası yüksek (45+ gün).")

    # 2) Kur riski: döviz borcu - döviz gelir dengesi
    fx_mismatch = fx_debt_ratio - fx_revenue_ratio
    if fx_mismatch > 30:
        score -= 25
        messages.append("Döviz uyumsuzluğu yüksek (döviz borcu gelirden belirgin fazla).")
    elif fx_mismatch > 10:
        score -= 12
        messages.append("Döviz uyumsuzluğu var (borç gelirden fazla).")

    # 3) Nakit tamponu
    if cash_buffer_months < 3:
        score -= 25
        messages.append("Nakit tamponu yetersiz (3 aydan az).")
    elif cash_buffer_months < 6:
        score -= 12
        messages.append("Nakit tamponu sınırlı (6 aydan az).")

    # 4) Müşteri yoğunlaşması
    if top_customer_share >= 70:
        score -= 18
        messages.append("Müşteri yoğunlaşması çok yüksek (en büyük müşteri %70+).")
    elif top_customer_share >= 50:
        score -= 10
        messages.append("Müşteri yoğunlaşması yüksek (en büyük müşteri %50+).")

    # 5) Gecikme
    if delay_issue == "yes":
        score -= 10
        messages.append("Son 12 ayda gecikme / vade uzaması yaşanmış.")

    # 6) Kısa vadeli borç baskısı
    if short_debt_ratio >= 60:
        score -= 15
        messages.append("12 ay içinde vadesi dolacak borç oranı çok yüksek (%60+).")
    elif short_debt_ratio >= 35:
        score -= 8
        messages.append("12 ay içinde vadesi dolacak borç oranı yüksek (%35+).")

    # 7) Limit/teminat baskısı
    if limit_pressure == "yes":
        score -= 12
        messages.append("Son 6 ayda limit daralması/teminat baskısı sinyali var.")

    # 8) Hedge
    if hedging == "none":
        score -= 8
        messages.append("Kur riski için hedge mekanizması yok.")
    elif hedging == "strong":
        score += 4

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
