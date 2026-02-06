# app/fin_mapping.py
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional

# -------------------------------------------------
# 1) Normalizasyon: türkçe karakter, noktalama, boşluk
#    + BAŞTAKİ "I / II / A / 1" gibi prefixleri kırp
# -------------------------------------------------
def normalize_text(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip().lower()

    # Türkçe karakterleri sadeleştir
    s = s.replace("ı", "i").replace("İ", "i")
    s = s.replace("ş", "s").replace("ğ", "g").replace("ç", "c").replace("ö", "o").replace("ü", "u")

    # Unicode normalize + combine işaretlerini sil
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))

    # alfanumerik dışında temizle
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    # ✅ BAŞTAKİ "I / II / III / A / 1" gibi prefixleri kırp
    roman = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    tokens = s.split()
    while tokens:
        t = tokens[0]
        if t in roman:
            tokens.pop(0)
            continue
        if t.isdigit():
            tokens.pop(0)
            continue
        if len(t) == 1 and t.isalpha():  # a, b, c...
            tokens.pop(0)
            continue
        break
    s = " ".join(tokens).strip()

    return s


def best_fuzzy_match(
    needle: str,
    haystack: List[str],
    threshold: float = 0.86
) -> Optional[Tuple[str, float]]:
    """
    Basit fuzzy. threshold üstü ise eşleşme döndürür.
    """
    if not needle:
        return None
    best = None
    for cand in haystack:
        ratio = SequenceMatcher(None, needle, cand).ratio()
        if best is None or ratio > best[1]:
            best = (cand, ratio)
    if best and best[1] >= threshold:
        return best
    return None


# -------------------------------------------------
# 2) Kanonik (standart) kalem anahtarları
# -------------------------------------------------
CANONICAL_KEYS = {
    # -------------------------
    # Bilanço - Dönen Varlıklar
    # -------------------------
    "cash_and_equivalents": "Nakit ve Nakit Benzerleri",
    "trade_receivables": "Ticari Alacaklar",
    "other_receivables": "Diğer Alacaklar",
    "inventories": "Stoklar",
    "prepaid_expenses": "Peşin Ödenmiş Giderler",
    "other_current_assets": "Diğer Dönen Varlıklar",
    "current_assets_total": "Dönen Varlıklar Toplamı",

    # -------------------------
    # Bilanço - Duran Varlıklar
    # -------------------------
    "ppe": "Maddi Duran Varlıklar",
    "intangible_assets": "Maddi Olmayan Duran Varlıklar",
    "right_of_use_assets": "Kullanım Hakkı Varlıkları",
    "investment_properties": "Yatırım Amaçlı Gayrimenkuller",
    "financial_investments": "Finansal Yatırımlar",
    "other_noncurrent_assets": "Diğer Duran Varlıklar",
    "non_current_assets_total": "Duran Varlıklar Toplamı",

    # -------------------------
    # Toplam Varlık
    # -------------------------
    "total_assets": "Toplam Varlıklar / Aktif Toplamı",

    # -------------------------
    # Yükümlülükler
    # -------------------------
    "short_term_liabilities": "Kısa Vadeli Yükümlülükler",
    "long_term_liabilities": "Uzun Vadeli Yükümlülükler",
    "trade_payables": "Ticari Borçlar",
    "short_term_fin_debt": "Kısa Vadeli Finansal Borçlar",
    "long_term_fin_debt": "Uzun Vadeli Finansal Borçlar",
    "lease_liabilities_st": "Kısa Vadeli Kiralama Yükümlülüğü",
    "lease_liabilities_lt": "Uzun Vadeli Kiralama Yükümlülüğü",
    "tax_liabilities": "Vergi Yükümlülükleri",
    "provisions_st": "Kısa Vadeli Karşılıklar",
    "provisions_lt": "Uzun Vadeli Karşılıklar",
    "total_liabilities": "Toplam Yükümlülükler / Borçlar Toplamı",

    # -------------------------
    # Özkaynak
    # -------------------------
    "equity_total": "Özkaynaklar",
    "paid_in_capital": "Ödenmiş Sermaye",
    "retained_earnings": "Geçmiş Yıllar Kâr/Zararları",
    "net_profit": "Dönem Net Kâr/Zararı",
    "total_liabilities_and_equity": "Toplam Kaynaklar / Pasif Toplamı",

    # -------------------------
    # Gelir Tablosu
    # -------------------------
    "revenue": "Hasılat / Net Satışlar",
    "cogs": "Satışların Maliyeti",
    "gross_profit": "Brüt Kâr",
    "opex": "Faaliyet Giderleri",
    "ebitda": "FAVÖK",
    "ebit": "Faaliyet Kârı (EBIT)",
    "finance_income": "Finansman Gelirleri",
    "finance_expense": "Finansman Giderleri",
    "interest_expense": "Faiz Gideri",
    "fx_gain_loss": "Kur Farkı Gelir/Gider",
    "tax_expense": "Vergi Gideri",
    "net_profit_is": "Net Dönem Kârı/Zararı (Gelir Tablosu)",
}


# -------------------------------------------------
# 3) Maksimum eşanlam listeleri
# -------------------------------------------------
SYNONYMS: Dict[str, List[str]] = {
    "cash_and_equivalents": [
        "nakit", "kasa", "kasa ve banka", "kasa bankalar", "banka", "bankalar",
        "banka mevduatlari", "mevduat", "vadesiz mevduat", "vadeli mevduat",
        "hazir degerler", "hazir deger", "nakit ve nakit benzerleri",
        "cash", "cash equivalents", "cash and cash equivalents",
        "repo", "ters repo", "para piyasasi fonu", "likit fon",
        "serbest mevduat", "blokeli mevduat", "bloke mevduat",
    ],

    "trade_receivables": [
        "ticari alacaklar", "alacaklar", "musteri alacaklari", "alici hesaplari",
        "alacak senetleri", "senetli alacaklar", "ticari alacak senetleri",
        "cekler", "cekler ve senetler", "alici cekleri",
        "trade receivables", "accounts receivable", "account receivable", "ar",
        "sozlesme varligi", "contract assets", "ifr s 15 sozlesme varligi",
        "hak edis", "hak edis alacaklari", "hakedis alacagi", "hakediş alacağı",
        "progress billings receivable", "progress receivable",
        "faturalanmis alacak", "faturalandirilmamis alacak", "kontrat alacagi",
    ],
    "other_receivables": [
        "diger alacaklar", "personelden alacaklar", "ortaklardan alacaklar",
        "iliskili taraflardan alacaklar", "other receivables",
        "verilen depozito ve teminatlar", "depozitolar", "teminatlar",
        "kamu alacaklari", "kira alacaklari",
        "verilen avanslar", "avanslar (verilen)", "siparis avanslari", "is avanslari",
    ],

    "inventories": [
        "stoklar", "ham madde", "ilk madde malzeme", "yarimamul", "yari mamul", "mamul",
        "ticari mallar", "sarf malzemesi", "yedek parca",
        "inventories", "work in progress", "wip",
        "insaat maliyetleri", "proje maliyetleri", "taahhut maliyetleri",
        "devam eden insaatlar", "devam eden projeler",
    ],

    "prepaid_expenses": [
        "pesin odenmis giderler", "gelecek aylara ait giderler",
        "prepaid expenses", "advance payments",
        "sigorta pesin", "kira pesin", "abonelik pesin",
    ],
    "other_current_assets": [
        "diger donen varliklar", "diger cari varliklar", "donen varliklar diger",
        "other current assets", "other current asset",
        "devreden kdv", "indirilecek kdv", "kdv alacagi", "kdv",
        "gelir tahakkuklari", "tahakkuk", "accrued income",
    ],
    "current_assets_total": [
        "donen varliklar toplami", "toplam donen varliklar", "donen varliklar",
        "current assets", "current assets total",
    ],

    "ppe": [
        "maddi duran varliklar", "mdv", "ppe",
        "property plant equipment", "property, plant and equipment",
        "tesis makine cihazlar", "demirbaslar", "tasitlar", "binalar", "araziler", "arsalar",
        "makine", "cihaz", "demirbas", "demirbaş",
    ],
    "intangible_assets": [
        "maddi olmayan duran varliklar", "mogdv", "intangible assets",
        "haklar", "yazilim", "lisans", "patent",
        "goodwill", "serefiye",
    ],
    "right_of_use_assets": [
        "kullanim hakki varliklari", "kiralama varliklari",
        "right of use assets", "ro u assets", "ifr s 16 kullanim hakki",
    ],
    "investment_properties": [
        "yatirim amacli gayrimenkuller", "yatirim amacli gayrimenkul",
        "investment properties", "investment property",
    ],
    "financial_investments": [
        "finansal yatirimlar", "menkul kiymetler", "securities",
        "tahvil", "bono", "eurobond", "kira sertifikasi", "sukuk",
        "yatirim fonlari", "fonlar", "financial investments",
        "bagli ortaklik yatirimi", "istirakler", "is ortakliklari",
    ],
    "other_noncurrent_assets": [
        "diger duran varliklar", "diger uzun vadeli varliklar",
        "other non current assets", "other non-current assets",
        "uzun vadeli depozito", "uzun vadeli teminat",
    ],
    "non_current_assets_total": [
        "duran varliklar toplami", "toplam duran varliklar", "duran varliklar",
        "non current assets", "non-current assets", "non-current assets total",
    ],
    "total_assets": [
        "aktif toplami", "varliklar toplami", "toplam varliklar", "bilanco toplami",
        "total assets", "assets total",
    ],

    "short_term_liabilities": [
        "kisa vadeli yukumlulukler", "kv yukumlulukler", "kisa vadeli borclar",
        "kisa vadeli yabanci kaynaklar", "cari yukumlulukler",
        "current liabilities", "short term liabilities", "short-term liabilities",
    ],
    "long_term_liabilities": [
        "uzun vadeli yukumlulukler", "uv yukumlulukler", "uzun vadeli borclar",
        "uzun vadeli yabanci kaynaklar",
        "non current liabilities", "non-current liabilities", "long term liabilities", "long-term liabilities",
    ],
    "trade_payables": [
        "ticari borclar", "saticilar", "satıcılar",
        "borc senetleri", "senetli borclar",
        "accounts payable", "trade payables", "ap",
        "tedarikci borcu", "tedarikci borclari", "tedarikçi borçları",
    ],
    "short_term_fin_debt": [
        "kisa vadeli finansal borclar", "kisa vadeli finansal yukumlulukler",
        "kisa vadeli banka kredileri", "kv banka kredileri", "kv kredi",
        "short term borrowings", "short term loans", "short term debt", "short-term debt",
        "kisa vadeli tahvil", "kisa vadeli bono",
        "kredi karti borcu", "faktoring borcu", "leasing borcu (kisa)",
        # ✅ TDHP / excel varyantları
        "mali borclar", "kisa vadeli mali borclar",
    ],
    "long_term_fin_debt": [
        "uzun vadeli finansal borclar", "uzun vadeli finansal yukumlulukler",
        "uzun vadeli banka kredileri", "uv banka kredileri", "uv kredi",
        "long term borrowings", "long term loans", "long term debt", "long-term debt",
        "uzun vadeli tahvil", "uzun vadeli bono",
        "leasing borcu (uzun)",
        "uzun vadeli mali borclar",
    ],
    "lease_liabilities_st": [
        "kisa vadeli kiralama yukumlulugu", "kiralama yukumlulugu kisa vade",
        "lease liabilities short", "short term lease liabilities", "ifr s 16 kiralama borcu kisa",
    ],
    "lease_liabilities_lt": [
        "uzun vadeli kiralama yukumlulugu", "kiralama yukumlulugu uzun vade",
        "lease liabilities long", "long term lease liabilities", "ifr s 16 kiralama borcu uzun",
    ],
    "tax_liabilities": [
        "vergi yukumlulukleri", "vergi borclari", "odenek vergi ve fonlar", "odenek vergiler",
        "tax payable", "corporate tax payable", "income tax payable",
        "kdv borcu", "stopaj borcu", "muhtasar", "sgk borcu", "damga vergisi",
    ],
    "provisions_st": [
        "kisa vadeli karsiliklar", "karsiliklar kisa", "dava karsiligi kisa", "garanti karsiligi kisa",
        "short term provisions", "provisions short",
    ],
    "provisions_lt": [
        "uzun vadeli karsiliklar", "karsiliklar uzun", "kidem tazminati karsiligi",
        "employee benefits provision", "long term provisions", "provisions long",
    ],
    "total_liabilities": [
        "toplam yukumlulukler", "borclar toplami", "toplam borclar",
        "liabilities total", "total liabilities",
        "yabanci kaynaklar toplami", "toplam yabanci kaynaklar",
    ],

    "equity_total": [
        "ozkaynak", "ozkaynaklar", "oz sermaye", "ozsermaye",
        "equity", "total equity", "shareholders equity",
        "ana ortakliga ait ozkaynak", "toplam ozkaynak",
        # ✅ excel prefixleri normalize kırptığı için artık direkt tutar
        "ozkaynaklar toplami", "toplam ozkaynaklar",
    ],
    "paid_in_capital": [
        "odenmis sermaye", "sermaye", "paid in capital", "share capital", "capital",
    ],
    "retained_earnings": [
        "gecmis yillar kar zararlari", "gecmis yil kar", "gecmis yil zarar",
        "retained earnings", "birikmis karlar", "birikmis zararlar",
        "yedekler", "kardan ayrilan kisitlanmis yedekler", "diger yedekler",
    ],
    "net_profit": [
        "donem net kari", "donem net zarari", "net donem kari",
        "net kar", "net zarar",
        "profit for the period", "net income", "net profit", "net loss",
    ],
    "total_liabilities_and_equity": [
        "pasif toplami", "kaynaklar toplami", "toplam kaynaklar",
        "total liabilities and equity", "liabilities and equity total",
    ],

    "revenue": [
        "hasilat", "net satislar", "satis gelirleri", "ciro",
        "revenue", "net sales", "sales", "satışlar",
        "yurtici satislar", "yurtdisi satislar",
    ],
    "cogs": [
        "satislarin maliyeti", "satilan malin maliyeti", "satılan malın maliyeti",
        "cogs", "cost of sales", "cost of goods sold",
        "uretim maliyeti", "hizmet uretim maliyeti",
    ],
    "gross_profit": [
        "brut kar", "gross profit", "gross margin",
    ],
    "opex": [
        "faaliyet giderleri", "operating expenses", "opex",
        "genel yonetim giderleri", "pazarlama satis dagitim giderleri", "ar ge giderleri",
        "personel giderleri", "maas giderleri", "kira giderleri",
    ],
    "ebitda": [
        "favok", "favoz", "ebitda", "faiz amortisman vergi oncesi kar",
    ],
    "ebit": [
        "faaliyet kari", "ebit", "operating profit", "operating income",
        "esas faaliyet kari", "esas faaliyet kar zarari",
    ],
    "finance_income": [
        "finansman gelirleri", "faiz gelirleri", "financial income", "finance income",
        "kur farki gelirleri", "yatirim gelirleri",
    ],
    "finance_expense": [
        "finansman giderleri", "finansal giderler", "financial expenses",
        "finance expense", "financing costs", "borclanma giderleri",
        "kredi giderleri", "faiz giderleri (genel)",
        # ✅ bazı excel’ler “finansman giderleri (faiz + kur farkı)” yazar
        "faiz ve kur farki giderleri",
    ],
    "interest_expense": [
        "faiz gideri", "faiz giderleri", "kredi faiz gideri",
        "interest expense", "interest costs", "faiz maliyeti",
    ],
    "fx_gain_loss": [
        "kur farki", "kur farki gelir gider", "kambiyo kar zarari",
        "foreign exchange gain", "foreign exchange loss", "fx gain", "fx loss",
    ],
    "tax_expense": [
        "vergi gideri", "donem vergi gideri", "ertelenmis vergi gideri",
        "tax expense", "income tax expense",
    ],
    "net_profit_is": [
        "net donem kari", "net donem kar zarari", "net donem zarari",
        "donem net kari zarari", "net kar zarari",
        "profit for the period", "net profit", "net loss",
    ],
}


# -------------------------------------------------
# 4) Eşleştirme fonksiyonu
# -------------------------------------------------
# Önce: synonym + canonical label
# Sonra: contains
# Sonra: fuzzy
# -------------------------------------------------
def _build_normalized_synonyms() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for key, xs in SYNONYMS.items():
        vals = list(xs)

        # canonical label'ı da otomatik ekle
        if key in CANONICAL_KEYS:
            vals.append(CANONICAL_KEYS[key])

        # key kendisini de ekleyelim (bazı excel'ler direkt key yazar)
        vals.append(key)

        normed = [normalize_text(x) for x in vals if x is not None and str(x).strip()]

        # unique
        uniq = []
        seen = set()
        for t in normed:
            if t not in seen:
                uniq.append(t)
                seen.add(t)

        out[key] = uniq

    return out


_norm_syn: Dict[str, List[str]] = _build_normalized_synonyms()

_all_norm_terms: List[str] = []
_term_to_key: Dict[str, str] = {}
for key, terms in _norm_syn.items():
    for t in terms:
        _all_norm_terms.append(t)
        _term_to_key[t] = key


def map_item_to_key(item_name: str) -> Optional[str]:
    n = normalize_text(item_name)
    if not n:
        return None

    # 1) exact match
    if n in _term_to_key:
        return _term_to_key[n]

    # 2) contains match
    for term, key in _term_to_key.items():
        if len(term) >= 6 and term in n:
            return key

    # 3) fuzzy match
    m = best_fuzzy_match(n, _all_norm_terms, threshold=0.86)
    if m:
        matched_term, _score = m
        return _term_to_key.get(matched_term)

    return None


def explain_key(key: str) -> str:
    return CANONICAL_KEYS.get(key, key)
