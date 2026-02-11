# app/tdhp_rules.py
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Tuple, Optional
import re


@dataclass(frozen=True)
class TDHPRules:
    # 3 haneli kod -> sign (1 normal, -1 kontra)
    sign_by_3: Dict[int, int]

    # Bakiye kolonu: mizanda genelde borç(+)/alacak(-) karma gelir.
    # Biz sadece "raporlamada" gereken sign'ı uygularız.
    def apply_sign(self, code3: int, amount: float) -> float:
        s = self.sign_by_3.get(code3, 1)
        return float(amount) * float(s)


def first3(code: str) -> Optional[int]:
    if not code:
        return None
    m = re.match(r"^\s*(\d{3})", str(code).strip())
    if not m:
        return None
    return int(m.group(1))


# Minimum kritik kontra listesi (istersen genişletiriz)
# Not: 103 zaten "(-)" çalışan varlık kontra hesabı.
DEFAULT_SIGN_BY_3: Dict[int, int] = {
    103: -1,  # Verilen Çekler ve Ödeme Emirleri (-)
    119: -1,  # Menkul Kıymetler Değer Düşüklüğü Karşılığı (-)
    122: -1,  # Alacak Senetleri Reeskontu (-)
    129: -1,  # Şüpheli Ticari Alacaklar Karşılığı (-)
    137: -1,  # Diğer Alacak Senetleri Reeskontu (-)
    139: -1,  # Şüpheli Diğer Alacaklar Karş. (-)
    158: -1,  # Stok Değer Düşüklüğü Karşı (-)
    199: -1,  # Diğer Dönen Varlık. Karşılığı (-)

    222: -1,
    224: -1,
    229: -1,
    237: -1,
    239: -1,
    241: -1,
    243: -1,
    247: -1,
    249: -1,
    257: -1,
    268: -1,
    278: -1,
    298: -1,
    299: -1,

    302: -1,  # Ertelenmiş finansal kiralama borçlanma maliyetleri (-)
    308: -1,  # Menkul kıymetler ihraç farkları (-)

    402: -1,
    408: -1,

    501: -1,  # Ödenmemiş Sermaye (-)
    503: -1,
    580: -1,  # Geçmiş Yıllar Zararları (-)
    591: -1,  # Dönem Net Zararı (-)
}

DEFAULT_RULES = TDHPRules(sign_by_3=DEFAULT_SIGN_BY_3)


def is_contra_from_name(name: str) -> bool:
    # Ek güvenlik: satır adında "(-)" görürsen kontra say
    if not name:
        return False
    return "(-" in name or "(-)" in name or " -" in name
