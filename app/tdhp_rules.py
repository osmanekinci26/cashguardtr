# app/tdhp_rules.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

@dataclass(frozen=True)
class RangeRule:
    start: int
    end: int

    def contains(self, code: int) -> bool:
        return self.start <= code <= self.end

def code_to_int(code: str) -> int | None:
    if code is None:
        return None
    s = str(code).strip()
    if not s:
        return None
    # "102.01" gibi gelirse 102 al
    s = s.split()[0]
    s = s.replace(",", ".")
    head = s.split(".")[0]
    if not head.isdigit():
        return None
    return int(head)

# -------------------------
# TDHP Range Rules
# -------------------------
RULES: Dict[str, Tuple[RangeRule, ...]] = {
    # Dönen varlıklar: 10-19 (100-199)
    "cash_and_equivalents": (RangeRule(100, 108),),
    "trade_receivables": (RangeRule(120, 129),),
    "other_receivables": (RangeRule(131, 139),),
    "inventories": (RangeRule(150, 159),),
    "prepaid_expenses": (RangeRule(180, 181),),
    "other_current_assets": (RangeRule(190, 199),),
    "current_assets_total": (RangeRule(100, 199),),

    # Duran varlıklar: 22-29 (220-299)
    "financial_investments": (RangeRule(240, 249),),
    "ppe": (RangeRule(250, 259),),
    "intangible_assets": (RangeRule(260, 269),),
    "other_noncurrent_assets": (RangeRule(270, 299),),
    "non_current_assets_total": (RangeRule(220, 299),),

    # Kısa vadeli yabancı kaynaklar: 30-39 (300-399)
    "short_term_liabilities": (RangeRule(300, 399),),
    "short_term_fin_debt": (RangeRule(300, 309),),
    "trade_payables": (RangeRule(320, 329),),
    "tax_liabilities": (RangeRule(360, 369),),
    "provisions_st": (RangeRule(370, 379),),
    "other_short_term_liabilities": (RangeRule(330, 399),),

    # Uzun vadeli yabancı kaynaklar: 40-49 (400-499)
    "long_term_liabilities": (RangeRule(400, 499),),
    "long_term_fin_debt": (RangeRule(400, 409),),
    "provisions_lt": (RangeRule(470, 479),),

    # Özkaynak: 50-59 (500-599)
    "equity_total": (RangeRule(500, 599),),
    "paid_in_capital": (RangeRule(500, 503),),
    "retained_earnings": (RangeRule(570, 580),),
    "net_profit": (RangeRule(590, 591),),

    # Gelir tablosu: 60-69
    # Net satışlar = 60 - 61 (61 indirimler negatif etki)
    "revenue_gross": (RangeRule(600, 602),),       # 60 grubu (kaba)
    "sales_discounts": (RangeRule(610, 612),),     # 61 (-)
    "cogs": (RangeRule(620, 623),),                # 62 (-)
    "opex": (RangeRule(630, 632),),                # 63 (-)
    "other_operating_income": (RangeRule(640, 649),),
    "other_operating_expense": (RangeRule(653, 659),),
    "finance_expense": (RangeRule(660, 661),),     # 66 (-) (TDHP’de finansman giderleri)
    "interest_expense": (RangeRule(660, 661),),    # ayrıştırma istersen genişletiriz
}

def sum_by_rules(trial: Dict[int, float]) -> Dict[str, float]:
    """
    trial: {account_code_int: balance_signed}
    balance_signed = borç - alacak (pozitif = borç bakiyesi)
    """
    out: Dict[str, float] = {}
    for key, ranges in RULES.items():
        total = 0.0
        for code, bal in trial.items():
            for rr in ranges:
                if rr.contains(code):
                    total += float(bal)
                    break
        out[key] = total
    # Net satış: 60 (ALACAK) olduğu için trial’da negatif çıkabilir.
    # Biz raporlama için revenue’yi pozitif görmek isteriz:
    # revenue = -(gross) - (discounts?) değil; burada yaklaşım:
    gross = out.get("revenue_gross", 0.0)
    disc = out.get("sales_discounts", 0.0)
    # trial = borç - alacak → gelir alacak olduğu için negatif
    # Net satışları pozitif göstermek için eksiyle çevir:
    out["revenue"] = -(gross + disc)  # disc zaten indirim hesapları borç bakiyesi olur genelde (+), eklenir
    return out
