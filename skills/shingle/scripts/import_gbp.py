#!/usr/bin/env python3
"""Import a Google Business Profile export into a Shingle business.json.

Usage:
    python3 import_gbp.py export.csv                       # dry run: show what would be imported
    python3 import_gbp.py export.xlsx --location 2 --write # pick the 2nd location, write business.json
    python3 import_gbp.py location.json --into business.json --prefer-google --write

Reads (standard library only):
  * the spreadsheet downloaded from Business Profile Manager (Actions > Download > Businesses):
    .csv, .tsv (comma, semicolon or tab separated; UTF-8, UTF-16 or Windows-1252) and .xlsx
  * the Business Information API `Location` JSON: one location, a list, or {"locations": [...]}

Rules:
  * Existing values are never overwritten: only empty fields are filled. Where Google differs, the
    difference is reported as a conflict (use --prefer-google to take Google's value).
  * Never imported: reviews, ratings, photos (URLs are counted, nothing is downloaded or hotlinked),
    special hours, labels, store codes.
  * Nothing is written without --write, and nothing is written when the result is invalid.

Exit code: 0 ok, 1 result invalid, 2 bad usage (including: several locations and none chosen).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from validate_input import DAY_KEYS, SOCIAL_HOSTS, Report, normalize, normalize_domain  # noqa: E402

CATEGORY_RULES_PATH = SCRIPTS.parent / "references" / "google-categories.json"
DAY_NAMES = {
    "monday": "mon",
    "tuesday": "tue",
    "wednesday": "wed",
    "thursday": "thu",
    "friday": "fri",
    "saturday": "sat",
    "sunday": "sun",
}

# Canonical field -> header spellings (already canonicalized: lower case, single spaces).
FIELD_ALIASES: dict[str, set[str]] = {
    "code": {"business code", "store code", "store id", "location id", "id"},
    "name": {"business name", "title", "name", "location name"},
    "address_all": {"address", "street address", "address lines"},
    "sublocality": {"sub-locality", "sublocality", "district", "neighborhood", "neighbourhood"},
    "locality": {"locality", "city", "town"},
    "region": {"administrative area", "state", "province", "county", "state/province"},
    "postal_code": {"postal code", "postcode", "zip", "zip code"},
    "country": {"country/region", "country", "country region", "country code"},
    "phone": {"primary phone", "phone", "main phone", "phone number"},
    "extra_phones": {"additional phones", "additional phone", "additional phone numbers"},
    "website": {"website", "url", "website url"},
    "primary_category": {"primary category", "category"},
    "additional_categories": {"additional categories"},
    "description": {"from the business", "business description", "description"},
    "opening_date": {"opening date"},
    "latitude": {"latitude", "lat"},
    "longitude": {"longitude", "lng", "lon"},
    "special_hours": {"special hours"},
    "labels": {"labels"},
    "photos": {"logo", "cover", "other photos", "logo photo", "cover photo", "profile photo", "photos", "preferred photo"},
    "ads_phone": {"adwords location extensions phone", "google ads phone number", "adwords phone", "google ads phone"},
    "errors": {"errors"},
    "google_updates": {"google updates"},
}
ALIAS_TO_FIELD = {alias: field for field, aliases in FIELD_ALIASES.items() for alias in aliases}
for _day in DAY_NAMES:
    ALIAS_TO_FIELD[f"{_day} hours"] = f"hours_{DAY_NAMES[_day]}"
ADDRESS_LINE_RE = re.compile(r"^address line ?([1-5])$")
NEVER_IMPORTED_RE = re.compile(r"review|rating|stars", re.I)


class ImportReport:
    def __init__(self) -> None:
        self.filled: list[str] = []
        self.replaced: list[str] = []
        self.conflicts: list[dict] = []
        self.ignored_columns: list[str] = []
        self.not_imported: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def as_dict(self) -> dict:
        return {
            "filled": self.filled,
            "replaced": self.replaced,
            "conflicts": self.conflicts,
            "ignored_columns": self.ignored_columns,
            "not_imported": self.not_imported,
            "warnings": self.warnings,
            "notes": self.notes,
        }


class Ambiguous(Exception):
    """Several locations in the file and none (or an unclear one) selected."""


# ---------------------------------------------------------------- reading tables


def canon(header: str) -> str:
    h = re.sub(r"\s+", " ", str(header).replace(" ", " ")).strip().lower()
    h = re.sub(r"\s*\*+$", "", h)
    return re.sub(r"\s*\((required|optional)\)$", "", h).strip()


def field_of(header: str) -> str | None:
    c = canon(header)
    if c in ALIAS_TO_FIELD:
        return ALIAS_TO_FIELD[c]
    m = ADDRESS_LINE_RE.match(c)
    return f"address_{m.group(1)}" if m else None


def decode_text(raw: bytes) -> str:
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def read_delimited(path: Path) -> list[list[str]]:
    text = decode_text(path.read_bytes())
    first = next((line for line in text.splitlines() if line.strip()), "")
    counts = {d: first.count(d) for d in (",", ";", "\t")}
    delimiter = max(counts, key=lambda d: counts[d])
    if counts[delimiter] == 0 or (path.suffix.lower() == ".tsv" and counts["\t"] > 0):
        delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    return [row for row in csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)]


_MAIN_URI = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_NS = {"m": _MAIN_URI}
_T, _ROW = f"{{{_MAIN_URI}}}t", f"{{{_MAIN_URI}}}row"
_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"


def _col_index(ref: str) -> int:
    letters = re.match(r"[A-Za-z]+", ref).group(0).upper()  # type: ignore[union-attr]
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _cell_text(c: ET.Element, shared: list[str]) -> str:
    kind = c.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in c.iter(_T))
    v = c.find("m:v", _NS)
    if v is None or v.text is None:
        return ""
    if kind == "s":
        return shared[int(v.text)]
    text = v.text
    return str(int(float(text))) if re.fullmatch(r"-?\d+(\.0+)?", text) else text


def read_xlsx(path: Path) -> list[list[str]]:
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(_T)) for si in root.findall("m:si", _NS)]
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        rels = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target", "") for r in rels}
        matrices: list[list[list[str]]] = []
        for sheet in wb.findall("m:sheets/m:sheet", _NS):
            target = targets.get(sheet.get(_REL), "")
            member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            if member not in z.namelist():
                continue
            rows: list[list[str]] = []
            for row in ET.fromstring(z.read(member)).iter(_ROW):
                cells: dict[int, str] = {}
                for c in row.findall("m:c", _NS):
                    cells[_col_index(c.get("r", "A1"))] = _cell_text(c, shared)
                width = max(cells) + 1 if cells else 0
                rows.append([cells.get(i, "") for i in range(width)])
            matrices.append(rows)
    if not matrices:
        raise ValueError(f"{path.name}: no worksheets found")
    for rows in matrices:  # prefer the sheet that has Google's column headers
        if any(sum(1 for h in r if field_of(h)) >= 2 for r in rows[:10]):
            return rows
    return matrices[0]


def matrix_to_rows(matrix: list[list[str]]) -> tuple[list[str], list[dict[str, str]]]:
    """Find the header row (the first with 2+ recognised columns) and return (headers, row dicts)."""
    head = next((i for i, r in enumerate(matrix) if sum(1 for h in r if field_of(h)) >= 2), None)
    if head is None:
        head = next((i for i, r in enumerate(matrix) if any(c.strip() for c in r)), None)
    if head is None:
        raise ValueError("the file has no rows")
    headers = [str(h).strip() for h in matrix[head]]
    rows = []
    for r in matrix[head + 1 :]:
        if not any(str(c).strip() for c in r):
            continue
        rows.append({h: (str(r[i]).strip() if i < len(r) else "") for i, h in enumerate(headers) if h})
    return headers, rows


def read_export(path: Path) -> tuple[str, list]:
    """Return ("table", [row dicts]) or ("api", [Location dicts]); headers are kept on the rows' keys."""
    raw = path.read_bytes()
    suffix = path.suffix.lower()
    if suffix == ".json" or raw.lstrip()[:1] in (b"{", b"["):
        data = json.loads(decode_text(raw))
        if isinstance(data, dict) and isinstance(data.get("locations"), list):
            data = data["locations"]
        if isinstance(data, dict):
            data = [data]
        if not isinstance(data, list) or not all(isinstance(x, dict) for x in data):
            raise ValueError('expected a Location object, a list of them, or {"locations": [...]}')
        if data and not any("title" in x or "storefrontAddress" in x or "regularHours" in x for x in data):
            raise ValueError(
                "this JSON does not look like a Business Profile Location (no title, storefrontAddress or regularHours)"
            )
        return "api", data
    matrix = read_xlsx(path) if suffix == ".xlsx" or raw[:2] == b"PK" else read_delimited(path)
    _, rows = matrix_to_rows(matrix)
    return "table", rows


# ---------------------------------------------------------------- hours


_TIME = re.compile(r"^(\d{1,2})(?::(\d{2}))?\s*([AaPp])?\.?[Mm]?\.?$")


def _minutes(text: str) -> int:
    m = _TIME.match(text.strip())
    if not m:
        raise ValueError(f"cannot read time {text!r}")
    h, mnt, suffix = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if suffix:
        pm = suffix.lower() == "p"
        h = (12 if pm else 0) if h == 12 else (h + 12 if pm else h)
    if not (0 <= h <= 24 and 0 <= mnt <= 59) or (h == 24 and mnt):
        raise ValueError(f"time out of range: {text!r}")
    return h * 60 + mnt


def _hhmm(minutes: int) -> str:
    minutes %= 1440
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def parse_day_cell(cell: str) -> list[list[str]]:
    """One hours cell in Google's grammar -> [[open, close], ...]. `X` or empty = closed ([])."""
    text = (cell or "").strip()
    if not text or text.upper() == "X":
        return []
    out: list[list[str]] = []
    for part in re.split(r"\s*,\s*", text):
        pieces = re.split(r"\s*[-–—]\s*", part)
        if len(pieces) != 2:
            raise ValueError(f"cannot read hours {part!r}")
        o, c = _minutes(pieces[0]), _minutes(pieces[1])
        if o == c == 0 or (o == 0 and c == 1440):
            out.append(["00:00", "23:59"])  # open 24 hours
            continue
        if o == c:
            raise ValueError(f"opening and closing time are the same in {part!r}")
        out.append([_hhmm(o), _hhmm(c)])
    return out


def hours_from_cells(cells: dict[str, str], report: ImportReport) -> dict | None:
    """cells: {"mon": "...", ...}. All seven empty means Google gave no hours, not 'closed all week'."""
    if not any(str(v).strip() for v in cells.values()):
        return None
    hours: dict[str, list[list[str]]] = {}
    for day in DAY_KEYS:
        try:
            hours[day] = parse_day_cell(cells.get(day, ""))
        except ValueError as e:
            report.warnings.append(f"{day} hours skipped: {e}")
    return hours


def _tod(value: dict | None) -> int:
    value = value or {}
    return int(value.get("hours", 0)) * 60 + int(value.get("minutes", 0))


def hours_from_periods(periods: list[dict], report: ImportReport) -> dict:
    hours: dict[str, list[list[str]]] = {d: [] for d in DAY_KEYS}
    order = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
    for p in periods:
        day = DAY_NAMES.get(str(p.get("openDay", "")).lower())
        if not day:
            report.warnings.append(f"hours period with unknown day {p.get('openDay')!r} skipped")
            continue
        o, c = _tod(p.get("openTime")), _tod(p.get("closeTime"))
        close_day = str(p.get("closeDay", p["openDay"])).upper()
        spans = (order.index(close_day) - order.index(str(p["openDay"]).upper())) % 7 if close_day in order else 0
        if o == 0 and ((spans == 0 and c in (0, 1440)) or (spans == 1 and c == 0)):
            hours[day].append(["00:00", "23:59"])  # open 24 hours
        elif spans == 0 and o == c:
            report.warnings.append(f"{day}: hours period opens and closes at the same time, skipped")
        else:
            hours[day].append([_hhmm(o), _hhmm(c)])
    for day in DAY_KEYS:
        hours[day].sort()
    return hours


# ---------------------------------------------------------------- categories


def load_rules() -> dict:
    return json.loads(CATEGORY_RULES_PATH.read_text(encoding="utf-8"))


def map_category(name: str, rules: dict) -> tuple[str, str | None, bool]:
    """Google category name -> (shingle category, schema_type or None, matched)."""
    words = re.sub(r"[^\w&+-]+", " ", name.lower())
    text = f" {words} "
    for rule in rules["rules"]:
        for keyword in rule["keywords"]:
            if f" {keyword.lower()} " in text:
                return rule["category"], rule.get("schema_type"), True
    return rules["fallback"], None, False


def category_label_from_id(name: str) -> str:
    tail = name.split(":", 1)[-1].replace("_", " ").strip()
    return tail.capitalize() if tail else name


# ---------------------------------------------------------------- mapping: spreadsheet row


def _split_list(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


def row_to_business(row: dict[str, str], report: ImportReport, rules: dict) -> tuple[dict, dict]:
    """One spreadsheet row -> (business dict, meta). Reports columns it does not use."""
    fields: dict[str, str] = {}
    extras: dict[str, str] = {}
    updated = 0
    for header, value in row.items():
        c = canon(header)
        if c.startswith("[updated]"):
            if value.strip():
                updated += 1
            continue
        field = field_of(header)
        if field:
            fields[field] = value.strip()
        else:
            extras[header] = value.strip()
    b: dict = {}
    meta = {"code": fields.get("code", ""), "name": fields.get("name", "")}
    if fields.get("name"):
        b["name"] = fields["name"]

    lines = [fields[f"address_{i}"] for i in range(1, 6) if fields.get(f"address_{i}")] or (
        [fields["address_all"]] if fields.get("address_all") else []
    )
    address = {
        "street": ", ".join(lines),
        "locality": fields.get("locality") or fields.get("sublocality", ""),
        "region": fields.get("region", ""),
        "postal_code": fields.get("postal_code", ""),
        "country": fields.get("country", ""),
    }
    address = {k: v for k, v in address.items() if v}
    if address:
        b["address"] = address
    if fields.get("phone"):
        b["phone"] = fields["phone"]
    if fields.get("description"):
        b["description"] = fields["description"]
    if fields.get("latitude") and fields.get("longitude"):
        try:
            b["geo"] = {"lat": float(fields["latitude"]), "lng": float(fields["longitude"])}
        except ValueError:
            report.warnings.append("latitude/longitude are not numbers: skipped")

    socials: list[str] = []
    website = fields.get("website", "")
    if website:
        host_part = website if "://" in website else f"https://{website}"
        domain, err = normalize_domain(host_part)
        if domain:
            b["domain"] = domain
            report.notes.append(f"domain {domain} is the website Google lists: confirm it is the domain of the new site")
        elif urlparse(host_part).netloc and any(
            urlparse(host_part).netloc.lower().removeprefix("www.").endswith(h) for h in SOCIAL_HOSTS
        ):
            socials.append(host_part)
            report.notes.append(
                f"Google's website field points at a social profile ({website}); stored under socials, no domain imported"
            )
        else:
            report.warnings.append(f"website {website!r} not imported: {err}")

    primary = fields.get("primary_category", "")
    if primary:
        category, schema_type, matched = map_category(primary, rules)
        b["category"] = category
        b["category_label"] = primary
        if schema_type:
            b.setdefault("decisions", {})["schema_type"] = schema_type
        if not matched:
            report.warnings.append(
                f"Google category {primary!r} has no matching Shingle category: using {category} (add a rule to references/google-categories.json)"
            )
    facts: dict = {}
    extra_cats = _split_list(fields.get("additional_categories", ""))
    if primary or extra_cats:
        facts["google_categories"] = [c for c in [primary, *extra_cats] if c]
    if fields.get("opening_date"):
        facts["opening_date"] = fields["opening_date"]

    cells = {d: fields.get(f"hours_{d}", "") for d in DAY_KEYS}
    hours = hours_from_cells(cells, report)
    if hours is not None:
        b["hours"] = hours
    if fields.get("special_hours"):
        report.not_imported.append("special hours (add holiday changes to `hours_note` by hand)")

    attributes: list[str] = []
    for header, value in extras.items():
        if NEVER_IMPORTED_RE.search(header):
            report.not_imported.append(f"column {header!r} (reviews and ratings are never imported)")
        elif re.match(r"^(https?://)?(www\.)?[\w.-]+\.[a-z]{2,}(/|$)", value, re.I) and any(
            h in value.lower() for h in SOCIAL_HOSTS
        ):
            socials.append(value)
        elif value.lower() in ("yes", "no", "[not applicable]") and value:
            if value.lower() == "yes":
                attributes.append(header)
        else:
            report.ignored_columns.append(header)
    if attributes:
        facts["attributes"] = attributes
    if facts:
        b["facts"] = facts
    if socials:
        b["socials"] = socials

    photo_urls = sum(
        len([u for u in _split_list(v) if u.lower().startswith("http")]) for h, v in row.items() if field_of(h) == "photos"
    )
    if photo_urls:
        report.not_imported.append(
            f"{photo_urls} photo link(s): add your own photos to public/images/ (nothing is downloaded or hotlinked)"
        )
    for key, label in (
        ("labels", "labels"),
        ("code", "store/business code"),
        ("ads_phone", "Google Ads phone"),
        ("extra_phones", "additional phone numbers"),
        ("errors", "Errors column"),
    ):
        if fields.get(key):
            report.not_imported.append(label)
    if updated:
        report.warnings.append(
            f"Google suggests updates to {updated} field(s) ([UPDATED] columns): review them in Business Profile; they were not imported"
        )
    return b, meta


# ---------------------------------------------------------------- mapping: API location


def location_to_business(loc: dict, report: ImportReport, rules: dict) -> tuple[dict, dict]:
    b: dict = {}
    meta = {"code": loc.get("storeCode", ""), "name": loc.get("title", "")}
    if loc.get("title"):
        b["name"] = loc["title"]
    status = (loc.get("openInfo") or {}).get("status", "")
    if status == "CLOSED_PERMANENTLY":
        report.warnings.append("Google marks this business PERMANENTLY CLOSED: is a website still wanted?")
    elif status == "CLOSED_TEMPORARILY":
        report.warnings.append("Google marks this business as temporarily closed")

    area = loc.get("serviceArea") or {}
    customer_only = area.get("businessType") == "CUSTOMER_LOCATION_ONLY"
    sf = loc.get("storefrontAddress") or {}
    if sf and not customer_only:
        address = {
            "street": ", ".join(x for x in sf.get("addressLines", []) if x),
            "locality": sf.get("locality") or sf.get("sublocality", ""),
            "region": sf.get("administrativeArea", ""),
            "postal_code": sf.get("postalCode", ""),
            "country": sf.get("regionCode", ""),
        }
        address = {k: v for k, v in address.items() if v}
        if address:
            b["address"] = address
    places = ((area.get("places") or {}).get("placeInfos")) or []
    names = [p.get("placeName") for p in places if p.get("placeName")]
    if names:
        b["service_area"] = names
    if (loc.get("phoneNumbers") or {}).get("primaryPhone"):
        b["phone"] = loc["phoneNumbers"]["primaryPhone"]
        if loc["phoneNumbers"].get("additionalPhones"):
            report.not_imported.append("additional phone numbers")
    if (loc.get("profile") or {}).get("description"):
        b["description"] = loc["profile"]["description"]
    ll = loc.get("latlng") or {}
    if "latitude" in ll and "longitude" in ll:
        b["geo"] = {"lat": float(ll["latitude"]), "lng": float(ll["longitude"])}
    if loc.get("languageCode"):
        b["languages"] = [str(loc["languageCode"])]

    socials: list[str] = []
    website = loc.get("websiteUri", "")
    if website:
        domain, err = normalize_domain(website)
        if domain:
            b["domain"] = domain
            report.notes.append(f"domain {domain} is the website Google lists: confirm it is the domain of the new site")
        elif any(urlparse(website).netloc.lower().removeprefix("www.").endswith(h) for h in SOCIAL_HOSTS):
            socials.append(website)
            report.notes.append(
                f"Google's website field points at a social profile ({website}); stored under socials, no domain imported"
            )
        else:
            report.warnings.append(f"website {website!r} not imported: {err}")
    maps_uri = (loc.get("metadata") or {}).get("mapsUri")
    if maps_uri:
        socials.append(maps_uri)
    if socials:
        b["socials"] = socials

    cats = loc.get("categories") or {}
    primary = cats.get("primaryCategory") or {}
    label = primary.get("displayName") or (category_label_from_id(primary["name"]) if primary.get("name") else "")
    facts: dict = {}
    if label:
        category, schema_type, matched = map_category(label, rules)
        b["category"] = category
        b["category_label"] = label
        if schema_type:
            b.setdefault("decisions", {})["schema_type"] = schema_type
        if not matched:
            report.warnings.append(
                f"Google category {label!r} has no matching Shingle category: using {category} (add a rule to references/google-categories.json)"
            )
        extra = [c.get("displayName") or category_label_from_id(c.get("name", "")) for c in cats.get("additionalCategories", [])]
        facts["google_categories"] = [label, *[e for e in extra if e]]
    od = (loc.get("openInfo") or {}).get("openingDate") or {}
    if od.get("year"):
        facts["opening_date"] = "-".join(
            f"{int(od[k]):02d}" if k != "year" else str(od[k]) for k in ("year", "month", "day") if od.get(k)
        )
    if facts:
        b["facts"] = facts

    if (loc.get("regularHours") or {}).get("periods"):
        b["hours"] = hours_from_periods(loc["regularHours"]["periods"], report)
    elif "regularHours" in loc:
        b["hours"] = {d: [] for d in DAY_KEYS}
    if (loc.get("specialHours") or {}).get("specialHourPeriods"):
        report.not_imported.append("special hours (add holiday changes to `hours_note` by hand)")
    if loc.get("labels"):
        report.not_imported.append("labels")
    if loc.get("serviceItems"):
        report.not_imported.append("service items (add services to the facts by hand)")
    return b, meta


# ---------------------------------------------------------------- selecting a location


def describe(items: list[tuple[dict, dict]]) -> str:
    lines = []
    for i, (b, meta) in enumerate(items, 1):
        addr = b.get("address") or {}
        where = ", ".join(x for x in (addr.get("street"), addr.get("locality")) if x)
        code = f" [{meta['code']}]" if meta.get("code") else ""
        lines.append(f"  {i}. {meta.get('name') or '(no name)'}{code}" + (f" ({where})" if where else ""))
    return "\n".join(lines)


def select_location(items: list[tuple[dict, dict]], selector: str | None) -> tuple[dict, dict]:
    if not items:
        raise ValueError("no locations found in the file")
    if selector is None:
        if len(items) == 1:
            return items[0]
        raise Ambiguous(
            f"the file has {len(items)} locations; choose one with --location (number, code or part of the name):\n{describe(items)}"
        )
    sel = selector.strip()
    if sel.isdigit() and 1 <= int(sel) <= len(items):
        return items[int(sel) - 1]
    by_code = [it for it in items if it[1].get("code") and it[1]["code"].lower() == sel.lower()]
    if len(by_code) == 1:
        return by_code[0]
    by_name = [it for it in items if sel.lower() in (it[1].get("name") or "").lower()]
    if len(by_name) == 1:
        return by_name[0]
    raise Ambiguous(f"--location {selector!r} matches {len(by_name) or 'no'} location(s); the file has:\n{describe(items)}")


# ---------------------------------------------------------------- merging


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def _leaves(path: str, value) -> list[str]:
    """Field paths to list in the report: nested objects are expanded, hours and geo stay one entry."""
    if isinstance(value, dict) and path.split(".")[-1] not in ("hours", "geo"):
        return [leaf for k, v in value.items() if not _empty(v) for leaf in _leaves(f"{path}.{k}", v)]
    return [path]


def merge_fill(existing, imported, report: ImportReport, prefer_google: bool = False, path: str = ""):
    """Fill empty fields of `existing` from `imported`; report differences as conflicts."""
    if isinstance(existing, dict) and isinstance(imported, dict):
        out = dict(existing)
        for key, value in imported.items():
            here = f"{path}.{key}" if path else key
            if key not in out or _empty(out[key]):
                if not _empty(value):
                    out[key] = value
                    report.filled.extend(_leaves(here, value))
            else:
                out[key] = merge_fill(out[key], value, report, prefer_google, here)
        return out
    if _empty(imported) or existing == imported:
        return existing
    if prefer_google:
        report.replaced.append(path)
        return imported
    report.conflicts.append({"path": path, "existing": existing, "google": imported})
    return existing


DERIVED_KEYS = ("slug", "phone_display", "schema_version")


def build_result(
    path: Path, selector: str | None, existing: dict | None, prefer_google: bool = False
) -> tuple[dict, ImportReport, Report, dict]:
    """Read the export and merge it into `existing`. Returns (business, import report, validation report, meta)."""
    report = ImportReport()
    kind, records = read_export(path)
    rules = load_rules()
    if kind == "table":
        if not any(field_of(h) == "name" for r in records for h in r):
            raise ValueError("no business name column found: is this the spreadsheet downloaded from Business Profile Manager?")
        rows = [(row, *row_to_business(row, ImportReport(), rules)) for row in records]
        rows = [r for r in rows if r[1].get("name")]
        items = [(b, meta) for _, b, meta in rows]
        _, chosen_meta = select_location(items, selector)
        row = rows[[meta for _, meta in items].index(chosen_meta)][0]
        chosen_b, chosen_meta = row_to_business(row, report, rules)  # again, so the report describes only this location
        report.ignored_columns = sorted(dict.fromkeys(report.ignored_columns))
    else:
        locs = [(loc, *location_to_business(loc, ImportReport(), rules)) for loc in records]
        items = [(b, meta) for _, b, meta in locs]
        _, chosen_meta = select_location(items, selector)
        loc = locs[[meta for _, meta in items].index(chosen_meta)][0]
        chosen_b, chosen_meta = location_to_business(loc, report, rules)

    imported, _ = normalize(chosen_b)
    for key in DERIVED_KEYS:
        imported.pop(key, None)
    base = {k: v for k, v in (existing or {}).items()}
    merged = merge_fill(base, imported, report, prefer_google)
    merged["imported_from"] = {
        "source": "google-business-profile",
        "file": path.name,
        "location": chosen_meta.get("name") or "",
        "imported_at": date.today().isoformat(),
    }
    final, validation = normalize(merged)
    return final, report, validation, chosen_meta


# ---------------------------------------------------------------- CLI


def render(report: ImportReport, validation: Report, final: dict, meta: dict, source: str, written: bool, dry: bool) -> str:
    out = [f"Google Business Profile import: {source} · {meta.get('name') or '(unnamed)'}"]
    out.append(f"\nfilled ({len(report.filled)}): " + (", ".join(report.filled) or "nothing new"))
    if report.replaced:
        out.append(f"replaced by Google ({len(report.replaced)}): " + ", ".join(report.replaced))
    if report.conflicts:
        out.append(f"\nkept your value, Google differs ({len(report.conflicts)}; --prefer-google takes Google's):")
        for c in report.conflicts:
            out.append(
                f"  {c['path']}: yours {json.dumps(c['existing'], ensure_ascii=False)} | Google {json.dumps(c['google'], ensure_ascii=False)}"
            )
    if report.not_imported:
        out.append("\nnot imported: " + "; ".join(dict.fromkeys(report.not_imported)))
    if report.ignored_columns:
        out.append("ignored columns: " + ", ".join(report.ignored_columns))
    for title, items in (
        ("notes", report.notes),
        ("warnings", [*report.warnings, *validation.warnings]),
        ("errors", validation.errors),
    ):
        if items:
            out.append(f"\n{title}:")
            out += [f"  - {i}" for i in dict.fromkeys(items)]
    missing = [m["field"] for m in validation.missing if m["essential"]] + [
        m["field"] for m in validation.missing if not m["essential"]
    ]
    if missing:
        out.append("\nstill missing: " + ", ".join(missing))
    out.append(
        "\n"
        + ("written." if written else "dry run: nothing written (add --write)." if dry else "not written (fix the errors first).")
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Import a Google Business Profile export into business.json")
    ap.add_argument("file", type=Path, help=".csv/.tsv/.xlsx download, or API Location .json")
    ap.add_argument("--location", help="which location when the file has several: number, store code or part of the name")
    ap.add_argument("--into", type=Path, help="existing business.json to fill (default: --out if it exists)")
    ap.add_argument("--out", type=Path, default=Path("business.json"), help="where to write (default: ./business.json)")
    ap.add_argument("--prefer-google", action="store_true", help="let Google's value replace a different existing one")
    ap.add_argument("--write", action="store_true", help="write the result (default is a dry run)")
    ap.add_argument("--json", action="store_true", help="print the report and result as JSON")
    args = ap.parse_args(argv)

    if not args.file.is_file():
        print(f"error: {args.file} not found", file=sys.stderr)
        return 2
    into = args.into or (args.out if args.out.exists() else None)
    existing = None
    if into:
        try:
            existing = json.loads(into.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"error: cannot read {into}: {e}", file=sys.stderr)
            return 2
    try:
        final, report, validation, meta = build_result(args.file, args.location, existing, args.prefer_google)
    except Ambiguous as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (ValueError, zipfile.BadZipFile, KeyError, ET.ParseError, json.JSONDecodeError) as e:
        print(f"error: cannot read {args.file.name}: {e}", file=sys.stderr)
        return 2

    written = False
    if args.write and not validation.errors:
        args.out.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written = True
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not validation.errors,
                    "written": written,
                    "location": meta,
                    "report": report.as_dict(),
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                    "missing": validation.missing,
                    "business": final,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        print(render(report, validation, final, meta, args.file.name, written, dry=not args.write))
    return 1 if validation.errors else 0


if __name__ == "__main__":
    sys.exit(main())
