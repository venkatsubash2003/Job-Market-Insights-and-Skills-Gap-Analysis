from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional, Tuple

# very light normalizer for "City, ST, Country" and common remote flags
@dataclass
class ParsedLocation:
    city: Optional[str]
    state: Optional[str]
    country: Optional[str]
    is_remote: bool
    confidence: float

_STATE_2 = r"(?i)\b[A-Z]{2}\b"  # crude US state code matcher
REMOTE_PAT = re.compile(r"(?i)\bremote\b")

def normalize_location(s: str) -> ParsedLocation:
    if not s:
        return ParsedLocation(None, None, None, False, 0.1)
    is_remote = bool(REMOTE_PAT.search(s))
    parts = [p.strip() for p in re.split(r"[,/|-]+", s) if p.strip()]
    city = state = country = None

    # Heuristics: many sources are "City, ST, Country" or "City, Country"
    if len(parts) >= 3:
        city, st, country = parts[0], parts[1], parts[2]
        state = st if re.fullmatch(_STATE_2, st) else st
    elif len(parts) == 2:
        city, st_or_country = parts
        if re.fullmatch(_STATE_2, st_or_country):
            state = st_or_country
            country = None
        else:
            country = st_or_country
    else:
        # single token like "USA" or "Cincinnati"
        token = parts[0]
        if len(token) == 2 and token.isalpha():
            state = token
        elif len(token) >= 3:
            # default assume it's a city or country
            city = token

    # normalize capitalization
    def cap(x): return x if x is None else x.strip().title()
    return ParsedLocation(cap(city), cap(state), cap(country), is_remote, 0.6 if (city or state or country) else 0.3)
