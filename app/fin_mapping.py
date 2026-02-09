# app/fin_mapping.py
from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Tuple, Optional


# -------------------------------------------------
# 1) Normalizasyon (TEK TANIM!)
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

    # baştaki "I / II / A / B / 1" gibi prefixleri kırp
    roman = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x"}
    tokens = s.split()
    while tokens:
        t = tokens[0]
        if t in roman:
            tokens.pop(0); continue
        if t.isdigit():
            tokens.pop(0); continue
        if len(t) == 1 and t.isalpha():  # a, b, c...
            tokens.pop(0); continue
        break

    return " ".join(tokens).strip()


def best_fuzzy_match(
    needle: str,
    haystack: List[str],
    threshold: float = 0.86
) -> Optional[Tuple[str, float]]:
    if not needle:
        return None
    best: Optional[Tuple[str, float]] = None
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
    # Dönen varlıklar
    "cash_and_equivalents": "Nakit ve Nakit Benzerleri",
    "trade_receivables": "Ticari Alacaklar",
    "other_receivables": "Diğer Alacaklar",
    "inventories": "Stoklar",
    "prepaid_expenses": "Peşin Ödenmiş Giderler",
    "other_current_assets": "Diğer Dönen Varlıklar",
    "current_assets_total": "Dönen Varlıklar Toplamı",

    # Duran varlıklar
    "ppe": "Maddi Duran Varlıklar",
    "intangible_assets": "Maddi Olmayan Duran Varlıklar",
    "right_of_use_assets": "Kullanım Hakkı Varlıkları",
    "investment_properties": "Yatırım Amaçlı Gayrimenkuller",
    "financial_investments": "Finansal Yatırımlar",
    "other_noncurrent_assets": "Diğer Duran Varlıklar",
    "non_current_assets_total": "Duran Varlıklar Toplamı",

    # Toplam varlık
    "total_assets": "Toplam Varlıklar / Aktif Toplamı",

    # Yükümlülükler
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

    # Özkaynak
    "equity_total": "Özkaynaklar",
    "paid_in_capital": "Ödenmiş Sermaye",
    "retained_earnings": "Geçmiş Yıllar Kâr/Zararları",
    "net_profit": "Dönem Net Kâr/Zararı",
    "total_liabilities_and_equity": "Toplam Kaynaklar / Pasif Toplamı",

    # Gelir tablosu
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
# 3) Eşanlam listeleri
# -------------------------------------------------
SYNONYMS: Dict[str, List[str]] = {
    "cash_and_equivalents": [
        "nakit", "kasa", "kasa ve banka", "kasa banka", "bankalar", "banka", "mevduat",
        "vadesiz mevduat", "vadeli mevduat", "hazir degerler",
        "cash", "cash equivalents", "cash and cash equivalents",
        "repo", "ters repo", "para piyasasi fonu", "likit fon",
        "kasa bankalar", "nakit ve nakit benzerleri",
    ],
    "trade_receivables": [
        "ticari alacaklar", "musteri alacaklari", "alici hesaplari",
        "cekler", "senetli alacaklar", "alacak senetleri",
        "accounts receivable", "trade receivables", "ar",
        "sozlesme varligi", "contract assets",
        "hak edis", "hak edis alacaklari", "hakedis alacagi", "hakediş alacağı",
        "alacaklar (ticari)", "ticari alacak senetleri",
    ],
    "other_receivables": [
        "diger alacaklar", "ortaklardan alacaklar", "iliskili taraflardan alacaklar",
        "verilen depozito ve teminatlar", "depozitolar", "teminatlar",
        "other receivables",
        "personelden alacaklar", "kamu alacaklari",
    ],
    "inventories": [
        "stoklar", "ham madde", "yari mamul", "yarimamul", "mamul", "ticari mallar",
        "inventories", "work in progress", "wip",
        "devam eden insaatlar", "devam eden projeler", "proje maliyetleri",
        "insaat maliyetleri", "taahhut maliyetleri",
    ],
    "prepaid_expenses": [
        "pesin odenmis giderler", "gelecek aylara ait giderler", "gelecek aylara ait gider",
        "prepaid expenses", "advance payments",
        "kira pesin", "sigorta pesin",
    ],
    "other_current_assets": [
        "diger donen varliklar", "diger cari varliklar",
        "devreden kdv", "indirilecek kdv", "kdv", "kdv alacagi",
        "gelir tahakkuklari", "tahakkuk", "other current assets",
    ],
    "current_assets_total": [
        "donen varliklar", "donen varliklar toplami", "toplam donen varliklar",
        "current assets", "current assets total",
        "donen varliklar toplam", "donen varliklar toplamı",
    ],

    "short_term_liabilities": [
        "kisa vadeli yukumlulukler", "kisa vadeli borclar", "kv yukumlulukler",
        "cari yukumlulukler", "current liabilities", "short term liabilities",
        "kisa vadeli yukumlulukler toplami", "toplam kisa vadeli yukumlulukler",
        "kisa vadeli yabanci kaynaklar", "toplam kisa vadeli yabanci kaynaklar",
    ],
    "long_term_liabilities": [
        "uzun vadeli yukumlulukler", "uzun vadeli borclar",
        "non current liabilities", "long term liabilities",
        "uzun vadeli yabanci kaynaklar", "toplam uzun vadeli yabanci kaynaklar",
    ],
    "trade_payables": [
        "ticari borclar", "saticilar", "satıcılar",
        "accounts payable", "trade payables", "ap",
        "tedarikci borclari", "tedarikçi borçları",
    ],
    "short_term_fin_debt": [
        "kisa vadeli finansal borclar", "kisa vadeli banka kredileri", "kv kredi",
        "short term debt", "short term loans",
        "kisa vadeli borclanma", "kv finansal borc", "kredi borclari (kisa)",
    ],
    "long_term_fin_debt": [
        "uzun vadeli finansal borclar", "uzun vadeli banka kredileri", "uv kredi",
        "long term debt", "long term loans",
        "uzun vadeli borclanma", "uv finansal borc", "kredi borclari (uzun)",
    ],
    "tax_liabilities": [
        "vergi yukumlulukleri", "vergi borclari", "tax payable",
        "kdv borcu", "stopaj borcu", "sgk borcu", "muhtasar",
    ],
    "total_liabilities": [
        "toplam yukumlulukler", "toplam borclar", "borclar toplami",
        "liabilities total", "total liabilities",
        "yabanci kaynaklar toplami", "toplam yabanci kaynaklar",
    ],

    "equity_total": [
        "ozkaynak", "ozkaynaklar", "oz sermaye", "ozsermaye",
        "equity", "total equity",
        "ozkaynaklar toplami", "toplam ozkaynaklar", "ozkaynak toplam",
        "toplam ozsermaye", "ana ortakliga ait ozkaynak",
        "ozkaynaklar toplamı", "toplam ozkaynaklar",  # unicode varyant
    ],
    "paid_in_capital": [
        "odenmis sermaye", "sermaye", "share capital", "paid in capital",
    ],
    "retained_earnings": [
        "gecmis yillar kar zararlari", "retained earnings", "yedekler",
        "birikmis karlar", "birikmis zararlar",
    ],
    "net_profit": [
        "donem net kari", "donem net zarari", "net kar", "net zarar",
        "profit for the period", "net profit",
    ],
    "total_liabilities_and_equity": [
        "toplam kaynaklar", "kaynaklar toplami", "pasif toplami",
        "total liabilities and equity", "liabilities and equity total",
        "pasif toplam", "toplam pasif",
    ],

    "revenue": [
        "hasilat", "net satislar", "ciro", "sales", "revenue",
    ],
    "cogs": [
        "satislarin maliyeti", "cost of sales", "cogs",
    ],
    "gross_profit": [
        "brut kar", "gross profit",
    ],
    "ebit": [
        "faaliyet kari", "esas faaliyet kari", "ebit", "operating profit",
    ],
    "finance_expense": [
        "finansman giderleri", "financial expenses", "finance expense",
        "finansal giderler", "borclanma giderleri",
    ],
    "interest_expense": [
        "faiz gideri", "interest expense", "faiz giderleri",
    ],
}


# -------------------------------------------------
# 4) Synonym tablolarını normalize edip index oluştur
# -------------------------------------------------
def _build_normalized_synonyms() -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = {}
    for key, xs in SYNONYMS.items():
        vals = list(xs)

        # canonical label’ı da ekle
        if key in CANONICAL_KEYS:
            vals.append(CANONICAL_KEYS[key])

        # key string’i de ekle (bazı Excel'ler direkt key yazar)
        vals.append(key)

        normed = [normalize_text(x) for x in vals if x is not None and str(x).strip()]

        # unique
        uniq: List[str] = []
        seen = set()
        for t in normed:
            if t and t not in seen:
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

# contains match için: en uzun terim önce (daha doğru yakalar)
_terms_by_len_desc = sorted(_term_to_key.items(), key=lambda kv: len(kv[0]), reverse=True)

# contains match'i bozan jenerik kelimeler (tek başına görünürse eşleme yapma)
_GENERIC_STOPWORDS = {
    "toplam", "diger", "genel", "varliklar", "borclar", "kaynaklar", "tutar", "tl", "try",
    "bilanco", "gelir", "tablosu", "kalem",
}


def _is_generic_term(term: str) -> bool:
    # term bir stopword ise veya sadece stopwordlerden oluşuyorsa generic say
    toks = term.split()
    if not toks:
        return True
    if len(toks) == 1 and toks[0] in _GENERIC_STOPWORDS:
        return True
    if all(t in _GENERIC_STOPWORDS for t in toks):
        return True
    return False


def map_item_to_key(item_name: str) -> Optional[str]:
    n = normalize_text(item_name)
    if not n:
        return None

    # 1) exact match
    if n in _term_to_key:
        return _term_to_key[n]

    # 2) contains match (GÜVENLİLEŞTİRİLDİ)
    #    - en uzun terim önce
    #    - çok jenerik termleri ignore
    #    - minimum uzunluk şartı
    for term, key in _terms_by_len_desc:
        if len(term) < 9:
            continue
        if _is_generic_term(term):
            continue
        if term in n:
            return key

    # 3) fuzzy match
    m = best_fuzzy_match(n, _all_norm_terms, threshold=0.86)
    if m:
        matched_term, _score = m
        return _term_to_key.get(matched_term)

    return None


def explain_key(key: str) -> str:
    return CANONICAL_KEYS.get(key, key)
