#!/usr/bin/env python3
"""Validate and normalize a Shingle business.json.

Usage:
    python3 validate_input.py business.json            # report only
    python3 validate_input.py business.json --write    # normalize the file in place
    python3 validate_input.py business.json --json     # machine-readable report

Exit code 0 when there are no errors, 1 when there are errors, 2 on bad usage.
Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

SCHEMA_VERSION = 1

REGISTRY = json.loads((Path(__file__).resolve().parent.parent / "references" / "categories.json").read_text(encoding="utf-8"))
CATEGORIES = list(REGISTRY["categories"])
CATEGORY_ALIASES = {alias: cid for cid, c in REGISTRY["categories"].items() for alias in c.get("aliases", [])}

# ISO country -> (calling code, national trunk prefix, keep trunk after country code)
COUNTRIES: dict[str, tuple[str, str, bool]] = {
    "US": ("1", "1", False),
    "CA": ("1", "1", False),
    "GB": ("44", "0", False),
    "IE": ("353", "0", False),
    "FR": ("33", "0", False),
    "DE": ("49", "0", False),
    "ES": ("34", "", False),
    "PT": ("351", "", False),
    "IT": ("39", "", True),
    "NL": ("31", "0", False),
    "BE": ("32", "0", False),
    "CH": ("41", "0", False),
    "AT": ("43", "0", False),
    "DK": ("45", "", False),
    "SE": ("46", "0", False),
    "NO": ("47", "", False),
    "FI": ("358", "0", False),
    "PL": ("48", "", False),
    "CZ": ("420", "", False),
    "GR": ("30", "", False),
    "TR": ("90", "0", False),
    "IN": ("91", "0", False),
    "PK": ("92", "0", False),
    "BD": ("880", "0", False),
    "LK": ("94", "0", False),
    "NP": ("977", "0", False),
    "AE": ("971", "0", False),
    "SA": ("966", "0", False),
    "IL": ("972", "0", False),
    "EG": ("20", "0", False),
    "ZA": ("27", "0", False),
    "NG": ("234", "0", False),
    "KE": ("254", "0", False),
    "GH": ("233", "0", False),
    "AU": ("61", "0", False),
    "NZ": ("64", "0", False),
    "SG": ("65", "", False),
    "MY": ("60", "0", False),
    "ID": ("62", "0", False),
    "PH": ("63", "0", False),
    "TH": ("66", "0", False),
    "VN": ("84", "0", False),
    "JP": ("81", "0", False),
    "KR": ("82", "0", False),
    "CN": ("86", "0", False),
    "HK": ("852", "", False),
    "TW": ("886", "0", False),
    "BR": ("55", "0", False),
    "MX": ("52", "", False),
    "AR": ("54", "0", False),
    "CL": ("56", "", False),
    "CO": ("57", "", False),
    "PE": ("51", "0", False),
    "RU": ("7", "8", False),
    "UA": ("380", "0", False),
    "RO": ("40", "0", False),
    "HU": ("36", "06", False),
    "MA": ("212", "0", False),
}

COUNTRY_NAMES = {
    "usa": "US",
    "united states": "US",
    "united states of america": "US",
    "america": "US",
    "uk": "GB",
    "united kingdom": "GB",
    "england": "GB",
    "scotland": "GB",
    "wales": "GB",
    "great britain": "GB",
    "canada": "CA",
    "ireland": "IE",
    "france": "FR",
    "germany": "DE",
    "deutschland": "DE",
    "spain": "ES",
    "espana": "ES",
    "portugal": "PT",
    "italy": "IT",
    "italia": "IT",
    "netherlands": "NL",
    "the netherlands": "NL",
    "holland": "NL",
    "belgium": "BE",
    "switzerland": "CH",
    "austria": "AT",
    "denmark": "DK",
    "sweden": "SE",
    "norway": "NO",
    "finland": "FI",
    "poland": "PL",
    "czechia": "CZ",
    "czech republic": "CZ",
    "greece": "GR",
    "turkey": "TR",
    "turkiye": "TR",
    "india": "IN",
    "pakistan": "PK",
    "bangladesh": "BD",
    "sri lanka": "LK",
    "nepal": "NP",
    "uae": "AE",
    "united arab emirates": "AE",
    "saudi arabia": "SA",
    "israel": "IL",
    "egypt": "EG",
    "south africa": "ZA",
    "nigeria": "NG",
    "kenya": "KE",
    "ghana": "GH",
    "australia": "AU",
    "new zealand": "NZ",
    "singapore": "SG",
    "malaysia": "MY",
    "indonesia": "ID",
    "philippines": "PH",
    "thailand": "TH",
    "vietnam": "VN",
    "japan": "JP",
    "south korea": "KR",
    "korea": "KR",
    "china": "CN",
    "hong kong": "HK",
    "taiwan": "TW",
    "brazil": "BR",
    "brasil": "BR",
    "mexico": "MX",
    "argentina": "AR",
    "chile": "CL",
    "colombia": "CO",
    "peru": "PE",
    "russia": "RU",
    "ukraine": "UA",
    "romania": "RO",
    "hungary": "HU",
    "morocco": "MA",
}

UI_STRINGS_DIR = Path(__file__).resolve().parent.parent / "references" / "ui-strings"
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}
# Leaves a translation overlay must never change: they are facts, not prose.
LOCKED_KEYS = {"price", "phone", "whatsapp", "email", "url", "href", "booking_url", "domain", "slug", "category"}
PEOPLE_SEGMENTS = {"team", "people", "staff", "coaches", "stylists", "members"}
REVIEW_STATES = ("draft", "reviewed")

POSTAL_PATTERNS = {
    "US": r"\d{5}(-\d{4})?",
    "CA": r"[A-Za-z]\d[A-Za-z] ?\d[A-Za-z]\d",
    "GB": r"[A-Za-z]{1,2}\d[A-Za-z\d]? ?\d[A-Za-z]{2}",
    "IN": r"\d{6}",
    "DE": r"\d{5}",
    "FR": r"\d{5}",
    "ES": r"\d{5}",
    "IT": r"\d{5}",
    "PT": r"\d{4}-\d{3}",
    "NL": r"\d{4} ?[A-Za-z]{2}",
    "AU": r"\d{4}",
    "NZ": r"\d{4}",
    "JP": r"\d{3}-?\d{4}",
    "BR": r"\d{5}-?\d{3}",
    "SG": r"\d{6}",
    "IE": r"[A-Za-z]\d[\dWw] ?[A-Za-z\d]{4}",
}

TWELVE_HOUR_COUNTRIES = {"US", "CA", "AU", "NZ", "IN", "PH", "PK", "EG", "SA", "BD", "MY"}

SOCIAL_HOSTS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "tiktok.com": "tiktok",
    "x.com": "x",
    "twitter.com": "x",
    "linkedin.com": "linkedin",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "pinterest.com": "pinterest",
    "threads.net": "threads",
    "threads.com": "threads",
    "yelp.com": "yelp",
    "tripadvisor.com": "tripadvisor",
    "maps.app.goo.gl": "google_maps",
    "goo.gl": "google_maps",
    "g.page": "google_maps",
    "maps.google.com": "google_maps",
    "whatsapp.com": "whatsapp_channel",
}

HANDLE_URLS = {
    "instagram": "https://instagram.com/{h}",
    "facebook": "https://facebook.com/{h}",
    "tiktok": "https://www.tiktok.com/@{h}",
    "x": "https://x.com/{h}",
    "youtube": "https://www.youtube.com/@{h}",
    "pinterest": "https://pinterest.com/{h}",
    "threads": "https://www.threads.net/@{h}",
}

SOCIAL_KEYS = set(HANDLE_URLS) | {"linkedin", "yelp", "tripadvisor", "google_maps", "whatsapp_channel"}

DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

KEY_ORDER = [
    "schema_version",
    "name",
    "slug",
    "category",
    "category_label",
    "tagline",
    "description",
    "domain",
    "address",
    "geo",
    "timezone",
    "phone",
    "phone_display",
    "whatsapp",
    "email",
    "hours",
    "hours_note",
    "socials",
    "languages",
    "translations",
    "service_area",
    "images",
    "facts",
    "decisions",
]


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.changes: list[str] = []
        self.missing: list[dict] = []

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict:
        return {
            "ok": not self.errors,
            "errors": self.errors,
            "warnings": self.warnings,
            "changes": self.changes,
            "missing": self.missing,
        }


# ---------------------------------------------------------------- helpers


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return re.sub(r"-{2,}", "-", text) or "site"


def normalize_country(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip()
    if len(v) == 2 and v.isalpha():
        code = v.upper()
        return "GB" if code == "UK" else code
    return COUNTRY_NAMES.get(v.lower().strip("."))


def normalize_phone(raw: str, country: str | None) -> tuple[str | None, str | None]:
    """Return (e164, problem). problem is None when the number looks valid."""
    if not isinstance(raw, str) or not raw.strip():
        return None, "empty phone number"
    s = raw.strip()
    s = re.split(r"(?i)\s*(?:ext\.?|x|#)\s*\d+$", s)[0]
    has_plus = s.startswith("+")
    digits = re.sub(r"\D", "", s)
    if not digits:
        return None, f"no digits in phone number {raw!r}"
    if has_plus:
        e164 = "+" + digits
    elif digits.startswith("00"):
        e164 = "+" + digits[2:]
    elif country in ("US", "CA"):
        if len(digits) == 10:
            e164 = "+1" + digits
        elif len(digits) == 11 and digits.startswith("1"):
            e164 = "+" + digits
        else:
            return None, f"US/CA numbers need 10 digits, got {len(digits)} in {raw!r}"
    elif country in COUNTRIES:
        code, trunk, keep = COUNTRIES[country]
        national = digits
        if digits.startswith(code) and len(digits) > len(code) + 6:
            national = digits[len(code) :]
        elif trunk and not keep and national.startswith(trunk):
            national = national[len(trunk) :]
        e164 = "+" + code + national
    else:
        return None, (
            f"cannot normalize {raw!r} without a country: add address.country or write the number with its +country code"
        )
    n = len(e164) - 1
    if n < 8 or n > 15:
        return None, f"phone number {raw!r} has {n} digits after normalizing; E.164 allows 8-15"
    if country in COUNTRIES:
        code = COUNTRIES[country][0]
        if not e164[1:].startswith(code):
            return e164, f"phone {e164} does not start with +{code}, the code for {country}"
    return e164, None


def display_phone(e164: str, country: str | None) -> str:
    """Readable national format for the business's own country, else grouped international."""
    if country in COUNTRIES:
        code, trunk, keep = COUNTRIES[country]
        if e164.startswith("+" + code):
            national = e164[1 + len(code) :]
            if country in ("US", "CA") and len(national) == 10:
                return f"({national[:3]}) {national[3:6]}-{national[6:]}"
            prefix = "" if keep else trunk
            return _group(prefix + national)
    digits = e164.lstrip("+")
    for code in sorted({c for c, _, _ in COUNTRIES.values()}, key=len, reverse=True):
        if digits.startswith(code):
            return f"+{code} {_group(digits[len(code) :])}"
    return e164


def _group(digits: str) -> str:
    """Group from the right in fours (02079460958 -> 020 7946 0958); 9 digits as 3-3-3."""
    if len(digits) == 9:
        return f"{digits[:3]} {digits[3:6]} {digits[6:]}"
    parts = []
    while len(digits) > 4:
        parts.insert(0, digits[-4:])
        digits = digits[:-4]
    if digits:
        parts.insert(0, digits)
    return " ".join(parts)


def keep_original_display(raw: str, e164: str) -> bool:
    """True when the owner typed a formatted number we can show as-is."""
    cleaned = re.sub(r"\s+", " ", raw.strip())
    if not re.search(r"[\s().-]", cleaned) or re.search(r"[^\d\s().+-]", cleaned):
        return False
    digits = re.sub(r"\D", "", cleaned)
    return digits and (e164.endswith(digits.lstrip("0")) or digits.endswith(e164[-7:]))


def normalize_domain(raw: str) -> tuple[str | None, str | None]:
    d = raw.strip().lower()
    d = re.sub(r"^[a-z]+://", "", d)
    d = d.split("/")[0].split("?")[0].split("#")[0]
    d = d.split("@")[-1].split(":")[0].rstrip(".")
    if not re.fullmatch(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}", d):
        return None, f"domain {raw!r} is not a valid host name"
    if any(d == h or d.endswith("." + h) for h in SOCIAL_HOSTS):
        return None, f"domain {raw!r} is a social profile, not the business's own domain"
    return d, None


EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$")


def normalize_email(raw: str) -> tuple[str | None, str | None]:
    e = raw.strip().removeprefix("mailto:")
    if not EMAIL_RE.match(e):
        return None, f"email {raw!r} does not look valid"
    local, _, host = e.rpartition("@")
    return f"{local}@{host.lower()}", None


# ---------------------------------------------------------------- hours

_DAY_WORD = (
    r"mon(?:day)?|tue(?:s(?:day)?)?|wed(?:nesday)?|thu(?:r(?:s(?:day)?)?)?|fri(?:day)?"
    r"|sat(?:urday)?|sun(?:day)?|mo|tu|we|th|fr|sa|su"
)
_DAY_SPEC = re.compile(
    rf"\b(?:(?P<a>{_DAY_WORD})\.?\s*(?:-|–|—|to|through|thru)\s*(?P<b>{_DAY_WORD})\.?"
    rf"|(?P<one>{_DAY_WORD})\.?"
    r"|(?P<word>daily|every\s*day|7\s*days(?:\s*a\s*week)?|weekdays|weekends?))\b",
    re.I,
)
_TIME = r"(\d{1,2})(?:[:.h](\d{2}))?\s*(a\.?m\.?|p\.?m\.?|a|p)?"
_RANGE = re.compile(rf"{_TIME}\s*(?:-|–|—|to|until|till)\s*{_TIME}", re.I)


def _day_index(word: str) -> int:
    w = word.lower()[:2]
    return ["mo", "tu", "we", "th", "fr", "sa", "su"].index(w)


def _expand(m: re.Match) -> list[str]:
    if m.group("word"):
        w = m.group("word").lower()
        if w.startswith("weekday"):
            return DAY_KEYS[:5]
        if w.startswith("weekend"):
            return DAY_KEYS[5:]
        return list(DAY_KEYS)
    if m.group("one"):
        return [DAY_KEYS[_day_index(m.group("one"))]]
    a, b = _day_index(m.group("a")), _day_index(m.group("b"))
    if b >= a:
        return DAY_KEYS[a : b + 1]
    return DAY_KEYS[a:] + DAY_KEYS[: b + 1]


def _to24(h: int, mnt: int, suffix: str | None) -> tuple[int, int]:
    if suffix:
        pm = suffix.lower().startswith("p")
        if h == 12:
            h = 12 if pm else 0
        elif pm:
            h += 12
    return h, mnt


def parse_time_ranges(text: str, warnings: list[str]) -> list[list[str]]:
    t = re.sub(r"(?i)\bnoon\b", "12pm", text)
    t = re.sub(r"(?i)\bmidnight\b", "12am", t)
    if re.search(r"(?i)24\s*(?:/\s*7|h(?:ours|rs)?\b)", t):
        return [["00:00", "23:59"]]
    out = []
    for m in _RANGE.finditer(t):
        h1, m1, s1, h2, m2, s2 = m.groups()
        h1, h2 = int(h1), int(h2)
        m1, m2 = int(m1 or 0), int(m2 or 0)
        if s2 and not s1:
            pm2 = s2.lower().startswith("p")
            if pm2 and h1 == 12:
                s1 = "pm"
            elif pm2 and h2 == 12:
                s1 = "am"  # "8-12pm" ends at noon
            elif pm2 and h1 < h2:
                s1 = "pm"
            else:
                s1 = "am"
        if s1 and not s2:
            s2 = "pm" if s1.lower().startswith("a") and h2 <= h1 else s1
        if not s1 and not s2 and h1 <= 12 and h2 <= 12 and not m.group(0).startswith("0"):
            if h1 < 6:
                h1 += 12
                h2 += 12 if h2 < 12 else 0
                warnings.append(f"assumed afternoon for {m.group(0)!r}: {h1:02d}:{m1:02d}")
            elif h2 <= h1:
                h2 += 12
                warnings.append(f"assumed {m.group(0)!r} means {h1:02d}:{m1:02d}-{h2:02d}:{m2:02d}")
        H1, M1 = _to24(h1, m1, s1)
        H2, M2 = _to24(h2, m2, s2)
        if H1 > 23 or H2 > 24 or M1 > 59 or M2 > 59:
            warnings.append(f"could not read time range {m.group(0)!r}")
            continue
        out.append([f"{H1:02d}:{M1:02d}", f"{H2 % 24:02d}:{M2:02d}"])
    return out


def parse_hours_text(text: str, report: Report) -> dict[str, list[list[str]]]:
    hours: dict[str, list[list[str]]] = {}
    specs = list(_DAY_SPEC.finditer(text))
    if not specs:
        ranges = parse_time_ranges(text, report.warnings)
        if ranges:
            report.warnings.append("hours mention no days; assumed every day")
            return {d: ranges for d in DAY_KEYS}
        report.errors.append(f"could not read hours {text!r}; use the structured format")
        return {}
    pending: list[str] = []
    for i, m in enumerate(specs):
        end = specs[i + 1].start() if i + 1 < len(specs) else len(text)
        segment = text[m.end() : end]
        days = pending + _expand(m)
        if re.search(r"(?i)\bclosed\b", segment):
            for d in days:
                hours[d] = []
            pending = []
            continue
        ranges = parse_time_ranges(segment, report.warnings)
        if not ranges:
            pending = days
            continue
        for d in days:
            hours[d] = ranges
        pending = []
    if pending:
        report.warnings.append(f"no hours found for {', '.join(pending)}")
    return hours


TIME_RE = re.compile(r"^([01]\d|2[0-4]):([0-5]\d)$")


def _minutes(t: str) -> int:
    h, m = t.split(":")
    return int(h) * 60 + int(m)


def check_hours(hours: dict, report: Report) -> dict:
    clean: dict[str, list[list[str]]] = {}
    for key, ranges in hours.items():
        day = key.lower()[:3]
        if day not in DAY_KEYS:
            report.errors.append(f"hours: unknown day {key!r}; use mon..sun")
            continue
        if ranges in (None, "closed", False):
            ranges = []
        if not isinstance(ranges, list):
            report.errors.append(f"hours.{day}: expected a list of [open, close] pairs")
            continue
        fixed = []
        for pair in ranges:
            if isinstance(pair, str) and "-" in pair:
                pair = [p.strip() for p in pair.split("-", 1)]
            if not (isinstance(pair, list) and len(pair) == 2):
                report.errors.append(f"hours.{day}: {pair!r} is not an [open, close] pair")
                continue
            o, c = [p if len(p) == 5 else p.zfill(5) for p in map(str, pair)]
            if not TIME_RE.match(o) or not TIME_RE.match(c):
                report.errors.append(f"hours.{day}: {pair!r} must use 24h HH:MM")
                continue
            if o == c:
                report.errors.append(f"hours.{day}: open and close are both {o}")
                continue
            fixed.append([o, c])
        fixed.sort(key=lambda p: _minutes(p[0]))
        for a, b in zip(fixed, fixed[1:]):  # noqa: B905 (Python 3.9 support)
            a_end = _minutes(a[1]) if _minutes(a[1]) > _minutes(a[0]) else 24 * 60 + _minutes(a[1])
            if a_end > _minutes(b[0]):
                report.errors.append(f"hours.{day}: ranges {a} and {b} overlap")
        clean[day] = fixed
    unknown = [d for d in DAY_KEYS if d not in clean]
    if clean and unknown:
        report.warnings.append(f"hours unknown for {', '.join(unknown)}; confirm whether closed (use [] for closed)")
    return {d: clean[d] for d in DAY_KEYS if d in clean}


# ---------------------------------------------------------------- socials


def normalize_socials(value, report: Report) -> dict[str, str]:
    items: list[tuple[str | None, str]] = []
    if isinstance(value, dict):
        items = [(k, v) for k, v in value.items() if v]
    elif isinstance(value, list):
        items = [(None, v) for v in value if v]
    elif isinstance(value, str):
        items = [(None, v) for v in re.split(r"[\s,]+", value) if v]
    out: dict[str, str] = {}
    for key, raw in items:
        raw = str(raw).strip()
        k = (key or "").lower().replace("-", "_")
        k = {"twitter": "x", "googlemaps": "google_maps", "google": "google_maps", "gmb": "google_maps"}.get(k, k)
        if re.match(r"^(https?://)?([\w-]+\.)+[a-z]{2,}(/|$)", raw, re.I):
            url = raw if raw.lower().startswith("http") else "https://" + raw
            url = re.sub(r"^http://", "https://", url, flags=re.I)
            host = re.sub(r"^https://", "", url, flags=re.I).split("/")[0].lower().removeprefix("www.").removeprefix("m.")
            detected = next((v for h, v in SOCIAL_HOSTS.items() if host == h or host.endswith("." + h)), None)
            if detected and not k:
                k = detected
            if not k:
                report.warnings.append(f"socials: could not tell which platform {raw!r} is; stored as 'other'")
                k = "other"
            out[k] = url
        else:
            handle = raw.lstrip("@").strip("/")
            if not k:
                report.warnings.append(f"socials: handle {raw!r} has no platform; skipped")
                continue
            if k not in HANDLE_URLS:
                report.warnings.append(f"socials.{k}: needs a full URL, got {raw!r}")
                continue
            if not re.fullmatch(r"[\w.]+", handle):
                report.warnings.append(f"socials.{k}: {raw!r} is not a valid handle")
                continue
            out[k] = HANDLE_URLS[k].format(h=handle)
            report.changes.append(f"socials.{k}: {raw!r} -> {out[k]}")
        if k not in SOCIAL_KEYS and k != "other":
            report.warnings.append(f"socials.{k}: unknown platform key")
    return out


# ---------------------------------------------------------------- main normalize


def ui_languages() -> set[str]:
    return {p.stem for p in UI_STRINGS_DIR.glob("*.json")} if UI_STRINGS_DIR.is_dir() else {"en"}


def normalize_languages(value, report: Report) -> list[str]:
    """Return unique language codes like 'en' or 'pt-BR'; the first entry is the default language."""
    langs = value if isinstance(value, list) else [value]
    clean: list[str] = []
    for lang in langs:
        code = str(lang).strip().replace("_", "-")
        if not re.fullmatch(r"[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*", code):
            report.warnings.append(f"languages: {lang!r} is not a language code like 'en' or 'pt-BR'")
            continue
        parts = code.split("-")
        norm = "-".join([parts[0].lower()] + [p.upper() if len(p) == 2 else p for p in parts[1:]])
        if norm in clean:
            report.warnings.append(f"languages: {norm!r} is listed twice; keeping one")
            continue
        clean.append(norm)
    known = ui_languages()
    for code in clean:
        base = code.split("-")[0]
        if base in RTL_LANGUAGES:
            report.warnings.append(
                f"languages: {code!r} is written right-to-left; Shingle's templates are left-to-right only, so layout needs manual work"
            )
        elif base not in known and len(clean) > 1:
            report.warnings.append(
                f"languages: no interface dictionary for {base!r}; English interface text will be used "
                f"(add references/ui-strings/{base}.json, see docs/adding-a-language.md)"
            )
    return clean


def _locked(key: str, path: list[str]) -> bool:
    if key in LOCKED_KEYS:
        return True
    return key == "name" and (not path or any(seg in PEOPLE_SEGMENTS for seg in path))


def _compare_overlay(base, over, path: list[str], lang: str, report: Report) -> None:
    where = ".".join(["translations", lang, *path])
    if isinstance(over, dict):
        if not isinstance(base, dict):
            report.errors.append(f"{where}: expected {type(base).__name__} like the original, got an object")
            return
        for key, value in over.items():
            if not path and key == "review":
                continue
            if key not in base:
                report.warnings.append(f"{where}.{key}: not present in the default language, will be ignored")
                continue
            if _locked(key, path) and value != base[key]:
                report.errors.append(
                    f"{where}.{key}: {value!r} differs from {base[key]!r}; prices, numbers, contact details and names must not be translated"
                )
                continue
            _compare_overlay(base[key], value, [*path, key], lang, report)
    elif isinstance(over, list):
        if not isinstance(base, list):
            report.errors.append(f"{where}: expected {type(base).__name__} like the original, got a list")
            return
        if len(over) != len(base):
            report.warnings.append(
                f"{where}: {len(over)} items but the default language has {len(base)}; arrays replace the original whole"
            )
        for i, (b, o) in enumerate(zip(base, over)):  # noqa: B905 (Python 3.9 support)
            _compare_overlay(b, o, [*path, str(i)], lang, report)
    elif isinstance(base, (dict, list)):
        report.errors.append(f"{where}: expected {type(base).__name__} like the original, got {type(over).__name__}")


def check_translations(d: dict, report: Report) -> None:
    langs = d.get("languages") or []
    tr = d["translations"]
    if not isinstance(tr, dict):
        report.errors.append("translations must be an object keyed by language code")
        return
    if len(langs) < 2:
        report.warnings.append("translations are ignored: add more than one language to `languages`")
        return
    default = langs[0]
    for raw, overlay in list(tr.items()):
        code = str(raw).strip().replace("_", "-")
        if code == default:
            report.warnings.append(f"translations.{raw}: the default language is written at the top level of business.json")
            continue
        if code not in langs:
            report.errors.append(f"translations.{raw}: {code!r} is not in languages {langs}")
            continue
        if not isinstance(overlay, dict):
            report.errors.append(f"translations.{raw} must be an object")
            continue
        review = overlay.get("review", "draft")
        if review not in REVIEW_STATES:
            report.errors.append(f"translations.{raw}.review must be one of {', '.join(REVIEW_STATES)}")
        _compare_overlay(d, overlay, [], code, report)
    for code in langs[1:]:
        if code not in tr:
            report.warnings.append(f"no translations for {code!r}: its pages will show the default-language text")


def normalize(data: dict) -> tuple[dict, Report]:
    r = Report()
    d = json.loads(json.dumps(data))  # deep copy
    d.setdefault("schema_version", SCHEMA_VERSION)

    # name
    name = d.get("name")
    if isinstance(name, str) and name.strip():
        d["name"] = re.sub(r"\s+", " ", name.strip())
        slug = slugify(d["name"])
        if d.get("slug") != slug and not d.get("slug"):
            d["slug"] = slug
            r.changes.append(f"slug: set to {slug!r}")
    else:
        d.pop("name", None)

    # category
    cat = d.get("category")
    if isinstance(cat, str) and cat.strip():
        c = slugify(cat)
        c = CATEGORY_ALIASES.get(c, c)
        if c in CATEGORIES:
            if c != cat:
                r.changes.append(f"category: {cat!r} -> {c!r}")
            d["category"] = c
        else:
            r.errors.append(
                f"category {cat!r} is not known; use one of {', '.join(CATEGORIES)} (generic-local-business when nothing fits)"
            )

    # address / country
    addr = d.get("address")
    country = None
    if isinstance(addr, str):
        r.warnings.append("address is a single string; split it into street, locality, region, postal_code, country")
        d["address"] = addr = {"street": addr.strip()}
    if isinstance(addr, dict):
        addr = {k: (v.strip() if isinstance(v, str) else v) for k, v in addr.items() if v not in (None, "")}
        if "country" in addr:
            cc = normalize_country(str(addr["country"]))
            if cc:
                if cc != addr["country"]:
                    r.changes.append(f"address.country: {addr['country']!r} -> {cc!r}")
                addr["country"] = cc
                country = cc
            else:
                r.warnings.append(f"address.country {addr['country']!r}: use an ISO 3166-1 alpha-2 code like 'US'")
        else:
            r.warnings.append("address.country missing: needed for phone normalization and JSON-LD")
        for k in ("street", "locality"):
            if k not in addr:
                r.warnings.append(f"address.{k} missing")
        pc = addr.get("postal_code")
        if pc and country in POSTAL_PATTERNS and not re.fullmatch(POSTAL_PATTERNS[country], str(pc)):
            r.warnings.append(f"address.postal_code {pc!r} does not look like a {country} postal code")
        d["address"] = addr

    geo = d.get("geo")
    if isinstance(geo, dict):
        try:
            lat, lng = float(geo["lat"]), float(geo["lng"])
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise ValueError
            d["geo"] = {"lat": lat, "lng": lng}
        except (KeyError, TypeError, ValueError):
            r.errors.append('geo must be {"lat": -90..90, "lng": -180..180}')

    # timezone (IANA name, needed for the live open/closed status in multi-zone countries)
    tz = d.get("timezone")
    if tz and not re.fullmatch(r"[A-Za-z_]+(?:/[A-Za-z0-9_+-]+){1,2}|UTC", str(tz)):
        r.errors.append(f"timezone {tz!r} must be an IANA name like 'America/Chicago'")

    # domain
    if d.get("domain"):
        dom, err = normalize_domain(str(d["domain"]))
        if err:
            r.errors.append(err)
        elif dom != d["domain"]:
            r.changes.append(f"domain: {d['domain']!r} -> {dom!r}")
            d["domain"] = dom

    # email
    if d.get("email"):
        em, err = normalize_email(str(d["email"]))
        if err:
            r.errors.append(err)
        else:
            if em != d["email"]:
                r.changes.append(f"email: {d['email']!r} -> {em!r}")
            d["email"] = em
            dom = d.get("domain")
            host = em.split("@")[1]
            if (
                dom
                and host != dom
                and host.split(".", 1)[-1] != dom
                and host in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com")
            ):
                r.warnings.append(f"email uses {host}; an address at {dom} looks more professional (optional)")

    # phone + whatsapp
    for key in ("phone", "whatsapp"):
        val = d.get(key)
        if val is True and key == "whatsapp":
            val = d.get("phone")
        if not val:
            d.pop(key, None)
            continue
        e164, err = normalize_phone(str(val), country)
        if e164 is None:
            r.errors.append(f"{key}: {err}")
            continue
        if err:
            r.warnings.append(f"{key}: {err}")
        if e164 != val:
            r.changes.append(f"{key}: {val!r} -> {e164!r}")
        d[key] = e164
        if key == "phone" and not d.get("phone_display"):
            raw = str(val)
            d["phone_display"] = (
                re.sub(r"\s+", " ", raw.strip()) if keep_original_display(raw, e164) else display_phone(e164, country)
            )
            r.changes.append(f"phone_display: set to {d['phone_display']!r}")

    # hours
    hours = d.get("hours")
    if isinstance(hours, str):
        parsed = parse_hours_text(hours, r)
        if parsed:
            r.changes.append(f"hours: parsed {hours!r}")
            hours = parsed
        else:
            hours = None
    if isinstance(hours, dict):
        d["hours"] = check_hours(hours, r)
    elif hours is not None:
        r.errors.append("hours must be an object (mon..sun) or a text like 'Mon-Fri 9-5'")

    # socials
    if d.get("socials"):
        d["socials"] = normalize_socials(d["socials"], r)

    # languages + translations
    if d.get("languages"):
        d["languages"] = normalize_languages(d["languages"], r)
    if d.get("translations"):
        check_translations(d, r)

    # images
    for i, img in enumerate(d.get("images") or []):
        src = img.get("src", "") if isinstance(img, dict) else str(img)
        if re.match(r"^(https?:)?//", src):
            r.errors.append(
                f"images[{i}]: {src!r} is remote. Only use images the owner provides: download "
                "them with permission into public/images/ and reference the local path"
            )
        elif isinstance(img, dict) and not img.get("alt"):
            r.warnings.append(f"images[{i}]: missing alt text for {src!r}")

    # decisions
    dec = d.get("decisions")
    if isinstance(dec, dict) and "badge" in dec and not isinstance(dec["badge"], bool):
        r.errors.append("decisions.badge must be true or false")

    # missing
    if not d.get("name"):
        r.missing.append({"field": "name", "essential": True})
    if not d.get("category"):
        r.missing.append({"field": "category", "essential": True})
    if not (d.get("phone") or d.get("email") or (isinstance(d.get("address"), dict) and d["address"].get("street"))):
        r.missing.append({"field": "phone|email|address", "essential": True, "note": "at least one contact method"})
    for f in ("domain", "address", "phone", "email", "hours", "socials", "description"):
        if not d.get(f):
            r.missing.append({"field": f, "essential": False})
    if not d.get("domain"):
        r.warnings.append("domain unknown: canonical URLs and sitemap will use a TODO URL until it is set")

    ordered = {k: d[k] for k in KEY_ORDER if k in d}
    ordered.update({k: v for k, v in d.items() if k not in ordered})
    return ordered, r


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("path", type=Path)
    ap.add_argument("--write", action="store_true", help="write the normalized JSON back to the file")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    args = ap.parse_args(argv)
    try:
        data = json.loads(args.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.path}: {e}", file=sys.stderr)
        return 2
    if not isinstance(data, dict):
        print("error: business.json must contain a JSON object", file=sys.stderr)
        return 2
    normalized, report = normalize(data)
    if args.write and not report.errors:
        args.path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    out = report.as_dict()
    out["written"] = bool(args.write and not report.errors)
    if args.json:
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"{'OK' if report.ok else 'INVALID'}: {args.path}")
        for title, items in (("errors", report.errors), ("warnings", report.warnings), ("changes", report.changes)):
            if items:
                print(f"\n{title}:")
                for it in items:
                    print(f"  - {it}")
        if report.missing:
            print("\nmissing:")
            for m in report.missing:
                print(f"  - {m['field']}{' (essential)' if m['essential'] else ''}")
        if args.write:
            print("\nwritten" if out["written"] else "\nnot written (fix errors first)")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
