from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple

_CURRENCY_SIGNS = {
    "$": "USD",
    "£": "GBP",
    "€": "EUR",
    "₹": "INR",
}
_CURRENCY_WORDS = {
    "usd": "USD",
    "dollar": "USD",
    "dollars": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "euros": "EUR",
    "gbp": "GBP",
    "inr": "INR",
}

_PERIOD_KEYWORDS = {
    "year": "year",
    "yr": "year",
    "annum": "year",
    "month": "month",
    "mo": "month",
    "hour": "hour",
    "hr": "hour",
}

_K_MULT = re.compile(r"(?i)\b(\d+(\.\d+)?)\s*[kK]\b")
_NUM = re.compile(r"(?<![A-Za-z])(\d{1,3}(?:[,\s]\d{3})+|\d+(?:\.\d+)?)(?![A-Za-z])")
_CUR_SIGN = re.compile(r"[$£€₹]")
_CUR_WORD = re.compile(r"(?i)\b(usd|dollars?|eur|euros?|gbp|inr)\b")
_PERIOD = re.compile(r"(?i)\b(per|/)?\s*(year|yr|annum|month|mo|hour|hr)\b")
_RANGE_SEP = re.compile(r"[-–—to]+")  # -, en/em dash, 'to'

@dataclass
class ParsedSalary:
    min: Optional[float]
    max: Optional[float]
    currency: Optional[str]
    period: Optional[str]
    confidence: float

def _to_number(token: str) -> float:
    token = token.replace(",", "").strip()
    m = _K_MULT.fullmatch(token)
    if m:
        return float(m.group(1)) * 1000.0
    return float(token)

def _detect_currency(s: str) -> Optional[str]:
    m = _CUR_SIGN.search(s)
    if m:
        return _CURRENCY_SIGNS.get(m.group(), None)
    m2 = _CUR_WORD.search(s)
    if m2:
        return _CURRENCY_WORDS.get(m2.group(1).lower(), None)
    return None

def _detect_period(s: str) -> Optional[str]:
    m = _PERIOD.search(s)
    if not m:
        return None
    return _PERIOD_KEYWORDS.get(m.group(2).lower(), None)

def parse_salary(s: str) -> ParsedSalary:
    if not s:
        return ParsedSalary(None, None, None, None, 0.0)
    s_clean = s.strip()

    currency = _detect_currency(s_clean)
    period = _detect_period(s_clean)

    # split on range separators
    parts = _RANGE_SEP.split(s_clean)
    numbers = []
    for part in parts:
        # allow k-suffix like 130k; also catch plain numbers with separators
        tokens = [t for t in re.findall(r"\d+(?:\.\d+)?[kK]?|\d{1,3}(?:,\d{3})+", part)]
        for t in tokens:
            try:
                # normalize 130k, 55,000
                val = _to_number(t)
                numbers.append(val)
            except Exception:
                pass

    numbers = [n for n in numbers if n is not None]
    numbers = numbers[:2]  # at most min/max

    if not numbers:
        return ParsedSalary(None, None, currency, period, 0.2)

    if len(numbers) == 1:
        lo = hi = numbers[0]
        conf = 0.6
    else:
        lo, hi = sorted(numbers[:2])
        conf = 0.8

    # if k mentioned anywhere, likely annual unless stated otherwise
    # but we already attempted to parse explicit period
    if not period:
        # heuristic: common postings imply annual for k-ranges
        if re.search(r"(?i)\bk\b", s_clean) and not re.search(r"(?i)\bhour|hr|mo|month\b", s_clean):
            period = "year"
            conf = max(conf, 0.7)

    return ParsedSalary(lo, hi, currency, period, conf)
