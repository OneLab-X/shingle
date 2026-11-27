#!/usr/bin/env python3
"""Sync a Shingle site with its business.json without wiping manual edits.

Usage:
    python3 sync.py <site>                    # regenerate data files, print file status
    python3 sync.py <site> --record-all       # after first build: track every generated file
    python3 sync.py <site> --record a b ...   # after rewriting files: re-track just those
    python3 sync.py <site> --status           # print status only, write nothing
    python3 sync.py <site> --init-i18n        # languages has 2+ entries: add src/pages/[lang]/ (never overwrites edits)
    add --json for machine-readable output

Data files (always regenerated, never hand-edited):
    src/data/site.json, src/data/site.<lang>.json (extra languages), src/data/ui.json,
    src/styles/theme.css, src/styles/fonts.css, public/robots.txt,
    public/CNAME (only when a domain is set)
Generated files are tracked by SHA-256 in .shingle/manifest.json. A file whose current hash
differs from the recorded one was edited by hand and must not be overwritten (see
references/regeneration.md). Standard library only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, quote_plus

SCRIPTS = Path(__file__).resolve().parent
REFS = SCRIPTS.parent / "references"
sys.path.insert(0, str(SCRIPTS))

from validate_input import DAY_KEYS, REGISTRY, TWELVE_HOUR_COUNTRIES, normalize  # noqa: E402

VERSION = "0.1.0"
MANIFEST = ".shingle/manifest.json"
DATA_FILES = [
    "src/data/site.json",
    "src/styles/theme.css",
    "src/styles/fonts.css",
    "public/robots.txt",
    "public/CNAME",
]
UNTRACKED_PREFIXES = ("public/images/", "src/data/", "node_modules/", "dist/", ".astro/", ".shingle/", ".git/")
UNTRACKED_FILES = {"business.json", "package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
TRACK_ROOTS = ("src", "public")
TRACK_FILES = ("astro.config.mjs", "README.md")

PLACEHOLDER_URL = "https://example.com/"
SHINGLE_URL = "https://github.com/OneLab-X/shingle"
UI_STRINGS_DIR = REFS / "ui-strings"
TEMPLATE_DIR = SCRIPTS.parent.parent.parent / "templates" / "astro-tailwind"

# Which countries each language is the everyday language of; used to pick og:locale regions.
LANGUAGE_COUNTRIES = {
    "en": {"US", "GB", "CA", "AU", "NZ", "IE", "IN", "ZA", "SG"},
    "pt": {"PT", "BR"},
    "es": {"ES", "MX", "AR", "CO", "CL", "PE"},
    "fr": {"FR", "CA", "BE", "CH"},
    "de": {"DE", "AT", "CH"},
    "it": {"IT", "CH"},
}
DEFAULT_REGION = {"en": "US", "pt": "PT", "es": "ES", "fr": "FR", "de": "DE", "it": "IT"}
RTL_LANGUAGES = {"ar", "he", "fa", "ur"}

# Countries with a single time zone (or one that covers nearly all businesses). Others need
# an explicit "timezone" in business.json for the live open/closed status.
TIMEZONES = {
    "GB": "Europe/London",
    "IE": "Europe/Dublin",
    "FR": "Europe/Paris",
    "DE": "Europe/Berlin",
    "ES": "Europe/Madrid",
    "PT": "Europe/Lisbon",
    "IT": "Europe/Rome",
    "NL": "Europe/Amsterdam",
    "BE": "Europe/Brussels",
    "CH": "Europe/Zurich",
    "AT": "Europe/Vienna",
    "DK": "Europe/Copenhagen",
    "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo",
    "FI": "Europe/Helsinki",
    "PL": "Europe/Warsaw",
    "CZ": "Europe/Prague",
    "GR": "Europe/Athens",
    "TR": "Europe/Istanbul",
    "UA": "Europe/Kyiv",
    "RO": "Europe/Bucharest",
    "HU": "Europe/Budapest",
    "IN": "Asia/Kolkata",
    "PK": "Asia/Karachi",
    "BD": "Asia/Dhaka",
    "LK": "Asia/Colombo",
    "NP": "Asia/Kathmandu",
    "AE": "Asia/Dubai",
    "SA": "Asia/Riyadh",
    "IL": "Asia/Jerusalem",
    "EG": "Africa/Cairo",
    "ZA": "Africa/Johannesburg",
    "NG": "Africa/Lagos",
    "KE": "Africa/Nairobi",
    "GH": "Africa/Accra",
    "MA": "Africa/Casablanca",
    "SG": "Asia/Singapore",
    "MY": "Asia/Kuala_Lumpur",
    "PH": "Asia/Manila",
    "TH": "Asia/Bangkok",
    "VN": "Asia/Ho_Chi_Minh",
    "JP": "Asia/Tokyo",
    "KR": "Asia/Seoul",
    "CN": "Asia/Shanghai",
    "HK": "Asia/Hong_Kong",
    "TW": "Asia/Taipei",
    "NZ": "Pacific/Auckland",
    "CO": "America/Bogota",
    "PE": "America/Lima",
}
DEFAULT_PALETTE = "main-street"
DEFAULT_DIRECTION = "swiss-grid"

DAY_LABELS = {
    "mon": ("Monday", "Mon"),
    "tue": ("Tuesday", "Tue"),
    "wed": ("Wednesday", "Wed"),
    "thu": ("Thursday", "Thu"),
    "fri": ("Friday", "Fri"),
    "sat": ("Saturday", "Sat"),
    "sun": ("Sunday", "Sun"),
}

SCHEMA_TYPES = {cid: c["schema_type"] for cid, c in REGISTRY["categories"].items()}
CATEGORY_LABELS = {cid: c["label"] for cid, c in REGISTRY["categories"].items()}

SOCIAL_LABELS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "x": "X",
    "linkedin": "LinkedIn",
    "youtube": "YouTube",
    "pinterest": "Pinterest",
    "threads": "Threads",
    "yelp": "Yelp",
    "tripadvisor": "Tripadvisor",
    "google_maps": "Google Maps",
    "whatsapp_channel": "WhatsApp channel",
    "other": "Website",
}


# ---------------------------------------------------------------- derived data


def _fmt_time(t: str, twelve: bool) -> str:
    h, m = (int(x) for x in t.split(":"))
    if not twelve:
        return f"{h % 24:02d}:{m:02d}"
    suffix = "am" if h % 24 < 12 else "pm"
    h12 = h % 12 or 12
    return f"{h12}{'' if m == 0 else f':{m:02d}'} {suffix}"


def build_hours(hours: dict | None, twelve: bool, note: str | None) -> dict:
    hours = hours or {}
    days = []
    for key in DAY_KEYS:
        label, short = DAY_LABELS[key]
        ranges = hours.get(key)
        days.append(
            {
                "key": key,
                "label": label,
                "short": short,
                "unknown": ranges is None,
                "closed": ranges == [],
                "ranges": [
                    {"open": o, "close": c, "text": f"{_fmt_time(o, twelve)}–{_fmt_time(c, twelve)}"} for o, c in (ranges or [])
                ],
            }
        )
    groups: list[dict] = []
    for d in days:
        text = "Closed" if d["closed"] else ("Hours not set" if d["unknown"] else ", ".join(r["text"] for r in d["ranges"]))
        if groups and groups[-1]["text"] == text:
            groups[-1]["days"].append(d["short"])
            groups[-1]["keys"].append(d["key"])
        else:
            groups.append(
                {"days": [d["short"]], "keys": [d["key"]], "text": text, "closed": d["closed"], "unknown": d["unknown"]}
            )
    for g in groups:
        ds = g.pop("days")
        g["label"] = ds[0] if len(ds) == 1 else f"{ds[0]}–{ds[-1]}"
    return {
        "known": any(not d["unknown"] for d in days),
        "format": "12h" if twelve else "24h",
        "days": days,
        "groups": groups,
        "note": note,
    }


def opening_hours_spec(hours: dict | None) -> list[dict]:
    by_range: dict[tuple[str, str], list[str]] = {}
    for key in DAY_KEYS:
        for o, c in (hours or {}).get(key) or []:
            by_range.setdefault((o, c), []).append(DAY_LABELS[key][0])
    return [
        {"@type": "OpeningHoursSpecification", "dayOfWeek": days, "opens": o, "closes": c}
        for (o, c), days in sorted(by_range.items(), key=lambda kv: (DAY_KEYS.index(kv[1][0][:3].lower()), kv[0]))
    ]


def address_lines(addr: dict | None) -> list[str]:
    if not addr:
        return []
    lines = []
    if addr.get("street"):
        lines.append(addr["street"])
    city = " ".join(x for x in (addr.get("postal_code"), addr.get("locality")) if x)
    if addr.get("region") and addr.get("region") != addr.get("locality"):
        city = f"{city}, {addr['region']}" if city else addr["region"]
    if city:
        lines.append(city)
    return lines


def load_ui(code: str) -> dict:
    """UI strings for a language code (pt-BR falls back to pt, anything unknown to English)."""
    en = json.loads((UI_STRINGS_DIR / "en.json").read_text(encoding="utf-8"))
    base = code.split("-")[0]
    path = UI_STRINGS_DIR / f"{base}.json"
    own = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    merged = {**en, **{k: v for k, v in own.items() if v}}
    meta = merged.pop("_meta", {})
    merged["_native_name"] = meta.get("native_name") if path.exists() else None
    return merged


def og_locale(code: str, country: str | None) -> str:
    lang, *rest = code.split("-")
    lang = lang.lower()
    region = next((p.upper() for p in rest if len(p) == 2), None)
    if not region:
        if country and country in LANGUAGE_COUNTRIES.get(lang, set()):
            region = country
        else:
            region = DEFAULT_REGION.get(lang, lang.upper())
    return f"{lang}_{region}"


def build_i18n(b: dict) -> dict:
    """Language configuration shared by every page. `enabled` only when there are 2+ languages."""
    dec = b.get("decisions") or {}
    langs = b.get("languages") or dec.get("languages") or ["en"]
    country = (b.get("address") or {}).get("country")
    enabled = len(langs) > 1
    locales = []
    for code in langs:
        ui = load_ui(code)
        locales.append(
            {
                "code": code,
                "path": code.lower(),
                "hreflang": code,
                "og_locale": og_locale(code, country),
                "label": ui["_native_name"] or code,
                "dir": "rtl" if code.split("-")[0] in RTL_LANGUAGES else "ltr",
            }
        )
    return {"enabled": enabled, "default": langs[0], "locales": locales}


def merge_translation(base, overlay):
    """Deep-merge a translation overlay over the default-language data: objects merge, anything else replaces."""
    if isinstance(base, dict) and isinstance(overlay, dict):
        out = dict(base)
        for key, value in overlay.items():
            out[key] = merge_translation(base[key], value) if key in base else value
        return out
    return overlay


def translated_business(b: dict, lang: str) -> dict:
    """The business as seen in `lang`: top-level fields are the default language, overlay for the rest."""
    overlay = ((b.get("translations") or {}).get(lang)) or {}
    overlay = {k: v for k, v in overlay.items() if k not in ("review", "images")}
    merged = merge_translation({k: v for k, v in b.items() if k != "translations"}, overlay)
    rows = ((b.get("translations") or {}).get(lang) or {}).get("images")
    if isinstance(rows, list) and isinstance(merged.get("images"), list):
        # images merge by position and only the alt text is translated; slot names stay as written
        merged["images"] = [
            {**img, "alt": row["alt"]} if isinstance(row, dict) and row.get("alt") and isinstance(img, dict) else img
            for img, row in zip(merged["images"], rows + [None] * len(merged["images"]))
        ]
    return merged


def untranslated_paths(base, overlay, prefix: str = "") -> list[str]:
    """Prose keys that exist in the default language but have no counterpart in the overlay."""
    missing: list[str] = []
    if isinstance(base, dict):
        for key, value in base.items():
            path = f"{prefix}.{key}" if prefix else key
            if isinstance(value, str) and key in PROSE_KEYS:
                if not isinstance(overlay, dict) or key not in overlay:
                    missing.append(path)
            elif isinstance(value, (dict, list)):
                missing += untranslated_paths(value, (overlay or {}).get(key) if isinstance(overlay, dict) else None, path)
    elif isinstance(base, list):
        for i, item in enumerate(base):
            sub = overlay[i] if isinstance(overlay, list) and i < len(overlay) else None
            missing += untranslated_paths(item, sub, f"{prefix}[{i}]")
    return missing


PROSE_KEYS = {
    "tagline",
    "description",
    "hours_note",
    "text",
    "summary",
    "story",
    "q",
    "a",
    "title",
    "note",
    "about",
    "process",
    "pricing",
    "first_step",
    "good_to_know",
    "emergency",
    "accessibility",
    "payment",
    "insurance_note",
}


def build_jsonld(b: dict, url: str, page_url: str | None = None, languages: list[str] | None = None) -> dict:
    cat = b.get("category", "generic-local-business")
    dec = b.get("decisions") or {}
    facts = b.get("facts") or {}
    ld: dict = {
        "@context": "https://schema.org",
        "@type": dec.get("schema_type") or SCHEMA_TYPES.get(cat, "LocalBusiness"),
        "@id": f"{url}#business",
        "name": b["name"],
        "url": page_url or url,
    }
    if cat == "photographer" and not dec.get("schema_type"):
        ld["additionalType"] = "https://www.wikidata.org/wiki/Q33231"
    desc = b.get("description") or b.get("tagline")
    if desc:
        ld["description"] = desc
    if b.get("phone"):
        ld["telephone"] = b["phone"]
    if b.get("email"):
        ld["email"] = b["email"]
    ld["image"] = f"{url}og.png"
    addr = b.get("address") or {}
    if addr.get("street") or addr.get("locality"):
        pa = {"@type": "PostalAddress"}
        for src, dst in (
            ("street", "streetAddress"),
            ("locality", "addressLocality"),
            ("region", "addressRegion"),
            ("postal_code", "postalCode"),
            ("country", "addressCountry"),
        ):
            if addr.get(src):
                pa[dst] = addr[src]
        ld["address"] = pa
    if b.get("geo"):
        ld["geo"] = {"@type": "GeoCoordinates", "latitude": b["geo"]["lat"], "longitude": b["geo"]["lng"]}
    spec = opening_hours_spec(b.get("hours"))
    if spec:
        ld["openingHoursSpecification"] = spec
    socials = [v for v in (b.get("socials") or {}).values()]
    if socials:
        ld["sameAs"] = socials
    if facts.get("price_range"):
        ld["priceRange"] = facts["price_range"]
    if cat in ("restaurant", "cafe") and facts.get("cuisine"):
        ld["servesCuisine"] = facts["cuisine"]
    if cat in ("restaurant", "cafe") and "menu" in (dec.get("features") or []):
        here = page_url or url
        ld["hasMenu"] = f"{here}menu/" if dec.get("pages") == "multi" else f"{here}#menu"
    if languages and len(languages) > 1:
        ld["knowsLanguage"] = languages
    if b.get("service_area"):
        ld["areaServed"] = [{"@type": "Place", "name": a} for a in b["service_area"]]
    for fact_key, ld_key in (
        ("founding_year", "foundingDate"),
        ("nonprofit_status", "nonprofitStatus"),
        ("knows_about", "knowsAbout"),
    ):
        if facts.get(fact_key):
            ld[ld_key] = str(facts[fact_key]) if fact_key == "founding_year" else facts[fact_key]
    return ld


def build_images(b: dict) -> list[dict]:
    """Photos the site may show: only those with confirmed alt text (or marked decorative). Never suggested_alt."""
    out = []
    for img in b.get("images") or []:
        if not isinstance(img, dict) or not img.get("src"):
            continue
        decorative = img.get("decorative") is True
        if not (img.get("alt") or decorative):
            continue
        out.append(
            {
                "file": Path(str(img["src"])).name,
                "subject": img.get("subject") or "",
                "alt": "" if decorative else img["alt"],
                "decorative": decorative,
                "width": img.get("width"),
                "height": img.get("height"),
            }
        )
    return out


def build_site_data(b: dict, palette: dict | None = None, lang: str | None = None, i18n: dict | None = None) -> dict:
    addr = b.get("address") or {}
    country = addr.get("country")
    dec = b.get("decisions") or {}
    design = dec.get("design") or {}
    domain = b.get("domain")
    url = f"https://{domain}/" if domain else PLACEHOLDER_URL
    lines = address_lines(addr)
    one_line = ", ".join(lines)
    query = ", ".join(x for x in (b.get("name"), one_line) if x)
    langs = b.get("languages") or dec.get("languages") or ["en"]
    i18n = i18n or build_i18n(b)
    current = lang or i18n["default"]
    current_locale = next(loc for loc in i18n["locales"] if loc["code"] == current)
    locale = current_locale["og_locale"]
    is_default = current == i18n["default"]
    page_url = f"{url}{current_locale['path']}/" if i18n["enabled"] else url
    label = b.get("category_label") or CATEGORY_LABELS.get(b.get("category", ""), "Local business")
    place = addr.get("locality") or addr.get("region")
    ui_strings = load_ui(current)
    what_where = ui_strings["seo.what_where"].replace("{what}", label).replace("{where}", place) if place else label

    contact = {}
    if b.get("phone"):
        contact["tel"] = {"href": f"tel:{b['phone']}", "label": b.get("phone_display") or b["phone"]}
    if b.get("whatsapp"):
        contact["whatsapp"] = {"href": f"https://wa.me/{b['whatsapp'].lstrip('+')}", "label": "WhatsApp"}
    if b.get("email"):
        contact["email"] = {"href": f"mailto:{b['email']}", "label": b["email"]}
    if dec.get("booking_url"):
        contact["booking"] = {"href": dec["booking_url"], "label": "Book online"}

    maps = None
    if lines:
        maps = {
            "search": (b.get("socials") or {}).get("google_maps")
            or f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}",
            "directions": f"https://www.google.com/maps/dir/?api=1&destination={quote_plus(query)}",
            "embed": f"https://www.google.com/maps?q={quote(query)}&output=embed",
        }

    return {
        "_generated": "GENERATED by shingle sync.py from business.json. Do not edit: change business.json and re-run sync.",
        "business": {
            "name": b.get("name"),
            "slug": b.get("slug"),
            "category": b.get("category"),
            "category_label": label,
            "tagline": b.get("tagline"),
            "description": b.get("description"),
            "domain": domain,
            "url": url,
            "url_is_placeholder": not domain,
            "address": addr or None,
            "address_lines": lines,
            "address_one_line": one_line or None,
            "geo": b.get("geo"),
            "phone": b.get("phone"),
            "phone_display": b.get("phone_display"),
            "whatsapp": b.get("whatsapp"),
            "email": b.get("email"),
            "socials": [
                {"key": k, "label": SOCIAL_LABELS.get(k, k.title()), "url": v} for k, v in (b.get("socials") or {}).items()
            ],
            "languages": langs,
            "service_area": b.get("service_area") or [],
            "facts": b.get("facts") or {},
        },
        "contact": contact,
        "maps": maps,
        "hours": {
            **build_hours(b.get("hours"), country in TWELVE_HOUR_COUNTRIES, b.get("hours_note")),
            "timezone": b.get("timezone") or TIMEZONES.get(country or ""),
        },
        "decisions": dec,
        "theme": {
            "direction": design.get("direction") or DEFAULT_DIRECTION,
            "palette": design.get("palette") if isinstance(design.get("palette"), str) else "custom",
            "dark": bool(palette and palette.get("dark")),
            "colors": {"light": (palette or {}).get("light"), "dark": (palette or {}).get("dark")},
        },
        "badge": dec.get("badge", True) is not False,
        "badge_url": SHINGLE_URL,
        "seo": {
            "title": f"{b.get('name')} · {b['tagline']}"
            if not is_default and b.get("tagline")
            else f"{b.get('name')} · {what_where}",
            "description": (
                b.get("description") or b.get("tagline") or f"{b.get('name')}: {what_where[0].lower()}{what_where[1:]}."
            )[:160],
            "locale": locale,
            "lang": current,
            "dir": current_locale["dir"],
            "og_image": f"{url}og.png",
        },
        "i18n": i18n,
        "lang": current,
        **({"images": images} if (images := build_images(b)) else {}),
        "jsonld": build_jsonld(b, url, page_url, langs),
        "shingle_version": VERSION,
    }


# ---------------------------------------------------------------- theme


def resolve_palette(b: dict, palettes: dict) -> dict:
    p = ((b.get("decisions") or {}).get("design") or {}).get("palette") or DEFAULT_PALETTE
    if isinstance(p, dict):
        return p
    for pal in palettes["palettes"]:
        if pal["id"] == p:
            return pal
    raise SystemExit(f"error: palette {p!r} not found in palettes.json")


def resolve_direction(b: dict, directions: dict) -> tuple[str, dict]:
    d = ((b.get("decisions") or {}).get("design") or {}).get("direction") or DEFAULT_DIRECTION
    if d not in directions["directions"]:
        raise SystemExit(f"error: direction {d!r} not found; known: {', '.join(directions['directions'])}")
    return d, directions["directions"][d]


def _vars(mode: dict) -> str:
    out = []
    for role, value in mode.items():
        out.append(f"  --sh-{role.replace('_', '-')}: {value};")
    if "on_accent" not in mode:
        out.append(f"  --sh-on-accent: {mode['text']};")
    if "border" not in mode:
        out.append(f"  --sh-border: color-mix(in srgb, {mode['text']} 15%, {mode['background']});")
    return "\n".join(out)


def build_theme_css(palette: dict, direction_id: str, direction: dict) -> str:
    f = direction["fonts"]
    tokens = "\n".join(f"  --sh-{k}: {v};" for k, v in direction["tokens"].items())
    light = palette["light"]
    dark = palette.get("dark")
    css = [
        "/* GENERATED by shingle sync.py. Do not edit: change business.json and re-run sync. */",
        f"/* direction: {direction_id} · palette: {palette.get('id', 'custom')} */",
        ":root {",
        f'  --sh-font-display: "{f["display"]["family"]}", {f["display"]["fallback"]};',
        f'  --sh-font-body: "{f["body"]["family"]}", {f["body"]["fallback"]};',
        tokens,
        _vars(light),
        f"  color-scheme: {'light dark' if dark else 'light'};",
        "}",
    ]
    if dark:
        css += [
            "@media (prefers-color-scheme: dark) {",
            '  :root:not([data-theme="light"]) {',
            "\n".join("  " + line for line in _vars(dark).splitlines()),
            "  }",
            "}",
            ':root[data-theme="dark"] {',
            _vars(dark),
            "}",
        ]
    return "\n".join(css) + "\n"


def build_fonts_css(direction: dict) -> str:
    imports = []
    for role in ("display", "body"):
        for imp in direction["fonts"][role]["imports"]:
            line = f'@import "{imp}";'
            if line not in imports:
                imports.append(line)
    return "/* GENERATED by shingle sync.py. Fonts for the chosen design direction. */\n" + "\n".join(imports) + "\n"


def font_packages(direction: dict) -> list[str]:
    return sorted({direction["fonts"][r]["package"] for r in ("display", "body")})


# ---------------------------------------------------------------- files + manifest


def sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(site: Path) -> dict:
    p = site / MANIFEST
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"version": 1, "files": {}, "font_packages": []}


def save_manifest(site: Path, manifest: dict) -> None:
    manifest["generated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest["shingle_version"] = VERSION
    manifest["files"] = dict(sorted(manifest["files"].items()))
    p = site / MANIFEST
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def is_trackable(rel: str) -> bool:
    return (
        rel not in DATA_FILES
        and rel not in UNTRACKED_FILES
        and not rel.startswith(UNTRACKED_PREFIXES)
        and not Path(rel).name.startswith(".")
    )


def candidate_files(site: Path) -> list[str]:
    out = []
    for root in TRACK_ROOTS:
        base = site / root
        if base.exists():
            out += [p.relative_to(site).as_posix() for p in base.rglob("*") if p.is_file()]
    out += [f for f in TRACK_FILES if (site / f).is_file()]
    return sorted(r for r in out if is_trackable(r))


def file_status(site: Path, manifest: dict) -> dict[str, list[str]]:
    status: dict[str, list[str]] = {"clean": [], "edited": [], "missing": [], "untracked": []}
    for rel, digest in manifest["files"].items():
        p = site / rel
        if not p.exists():
            status["missing"].append(rel)
        elif sha(p) == digest:
            status["clean"].append(rel)
        else:
            status["edited"].append(rel)
    status["untracked"] = [r for r in candidate_files(site) if r not in manifest["files"]]
    return status


def write_if_changed(path: Path, content: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def update_package_json(site: Path, wanted: list[str], previously_added: list[str]) -> list[str]:
    pj = site / "package.json"
    if not pj.exists():
        return []
    data = json.loads(pj.read_text(encoding="utf-8"))
    deps = data.setdefault("dependencies", {})
    changed = []
    for pkg in previously_added:
        if pkg not in wanted and pkg in deps:
            del deps[pkg]
            changed.append(f"-{pkg}")
    for pkg in wanted:
        if pkg not in deps:
            deps[pkg] = "^5.2.0"
            changed.append(f"+{pkg}")
    if changed:
        data["dependencies"] = dict(sorted(deps.items()))
        pj.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return changed


def sync(site: Path, palettes_path: Path, directions_path: Path, write: bool = True) -> dict:
    bpath = site / "business.json"
    if not bpath.exists():
        raise SystemExit(f"error: {bpath} not found")
    business, report = normalize(json.loads(bpath.read_text(encoding="utf-8")))
    if report.errors:
        raise SystemExit("error: business.json is invalid; run validate_input.py:\n  - " + "\n  - ".join(report.errors))
    if not business.get("name"):
        raise SystemExit("error: business.json needs a name")
    palettes = json.loads(palettes_path.read_text(encoding="utf-8"))
    directions = json.loads(directions_path.read_text(encoding="utf-8"))
    palette = resolve_palette(business, palettes)
    direction_id, direction = resolve_direction(business, directions)
    i18n = build_i18n(business)
    data = build_site_data(business, palette, i18n["default"], i18n)
    translations = business.get("translations") or {}
    ui = {}
    for loc in i18n["locales"]:
        strings = load_ui(loc["code"])
        strings.pop("_native_name", None)
        ui[loc["code"]] = strings

    outputs = {
        "src/data/site.json": json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        "src/data/ui.json": json.dumps(ui, indent=2, ensure_ascii=False) + "\n",
        "src/styles/theme.css": build_theme_css(palette, direction_id, direction),
        "src/styles/fonts.css": build_fonts_css(direction),
        "public/robots.txt": f"User-agent: *\nAllow: /\n\nSitemap: {data['business']['url']}sitemap-index.xml\n",
    }
    if business.get("domain"):
        outputs["public/CNAME"] = business["domain"] + "\n"
    i18n_report = {
        "languages": [loc["code"] for loc in i18n["locales"]],
        "default": i18n["default"],
        "untranslated": {},
        "draft": [],
    }
    if i18n["enabled"]:
        for loc in i18n["locales"][1:]:
            code = loc["code"]
            overlay = translations.get(code) or {}
            lang_data = build_site_data(translated_business(business, code), palette, code, i18n)
            lang_data["review"] = overlay.get("review", "draft")
            outputs[f"src/data/site.{code}.json"] = json.dumps(lang_data, indent=2, ensure_ascii=False) + "\n"
            base = {k: v for k, v in business.items() if k != "translations"}
            missing = untranslated_paths(base, overlay)
            if missing:
                i18n_report["untranslated"][code] = missing
            if lang_data["review"] != "reviewed":
                i18n_report["draft"].append(code)

    manifest = load_manifest(site)
    result = {"site": str(site), "written": [], "unchanged": [], "removed": [], "packages": []}
    if write:
        for rel, content in outputs.items():
            (result["written"] if write_if_changed(site / rel, content) else result["unchanged"]).append(rel)
        cname = site / "public/CNAME"
        if "public/CNAME" not in outputs and cname.exists():
            cname.unlink()
            result["removed"].append("public/CNAME")
        for stale in sorted((site / "src/data").glob("site.*.json")):
            rel = stale.relative_to(site).as_posix()
            if rel not in outputs:
                stale.unlink()
                result["removed"].append(rel)
        wanted = font_packages(direction)
        result["packages"] = update_package_json(site, wanted, manifest.get("font_packages", []))
        if manifest.get("font_packages") != wanted or not (site / MANIFEST).exists():
            manifest["font_packages"] = wanted
            save_manifest(site, manifest)
    result["status"] = file_status(site, manifest)
    result["warnings"] = report.warnings
    result["i18n"] = i18n_report
    return result


# (template file, site file, monolingual file it replaces)
I18N_OVERLAY = [
    ("i18n/src/pages/[lang]/index.astro", "src/pages/[lang]/index.astro", "src/pages/index.astro"),
    ("i18n/src/pages/404.astro", "src/pages/404.astro", "src/pages/404.astro"),
]


def _is_pristine(site: Path, rel: str, manifest: dict) -> bool:
    """True when the file is exactly what Shingle wrote (template copy or recorded hash)."""
    path = site / rel
    if not path.exists():
        return True
    if manifest["files"].get(rel) == sha(path):
        return True
    original = TEMPLATE_DIR / rel
    return original.exists() and original.read_bytes() == path.read_bytes()


def init_i18n(site: Path) -> dict:
    """Add the multi-language page scaffolding. Never overwrites a page the owner edited."""
    business, report = normalize(json.loads((site / "business.json").read_text(encoding="utf-8")))
    if report.errors:
        raise SystemExit("error: business.json is invalid; run validate_input.py")
    i18n = build_i18n(business)
    if not i18n["enabled"]:
        raise SystemExit("error: `languages` in business.json needs two or more entries for a multi-language site")
    manifest = load_manifest(site)
    result = {"created": [], "replaced": [], "kept": [], "warnings": []}
    for src_rel, dest_rel, replaces in I18N_OVERLAY:
        src, dest, old = TEMPLATE_DIR / src_rel, site / dest_rel, site / replaces
        if not src.exists():
            raise SystemExit(f"error: template overlay missing: {src}")
        if dest.exists() and dest_rel != replaces:
            result["kept"].append(dest_rel)
            continue
        if old.exists() and not _is_pristine(site, replaces, manifest):
            result["kept"].append(replaces)
            result["warnings"].append(
                f"{replaces} was edited by hand: move its content into the [lang] pages yourself "
                f"(the multi-language version was not written to avoid overwriting your edits)"
            )
            if dest_rel == replaces:
                continue
        if old.exists() and dest_rel != replaces and _is_pristine(site, replaces, manifest):
            old.unlink()
            result["replaced"].append(replaces)
        dest.parent.mkdir(parents=True, exist_ok=True)
        existed = dest.exists()
        dest.write_bytes(src.read_bytes())
        result["replaced" if existed else "created"].append(dest_rel)
    return result


def record(site: Path, paths: list[str] | None) -> dict:
    manifest = load_manifest(site)
    targets = candidate_files(site) if paths is None else [Path(p).as_posix() for p in paths]
    recorded, skipped = [], []
    for rel in targets:
        rel = rel.removeprefix("./")
        p = site / rel
        if not p.is_file() or not is_trackable(rel):
            skipped.append(rel)
            continue
        manifest["files"][rel] = sha(p)
        recorded.append(rel)
    for rel in list(manifest["files"]):
        if not (site / rel).exists():
            del manifest["files"][rel]
    save_manifest(site, manifest)
    return {"recorded": recorded, "skipped": skipped, "tracked": len(manifest["files"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Sync a Shingle site with business.json")
    ap.add_argument("site", type=Path)
    ap.add_argument("--record", nargs="+", metavar="PATH", help="record hashes for these generated files")
    ap.add_argument("--record-all", action="store_true", help="record hashes for all generated files")
    ap.add_argument("--status", action="store_true", help="report status only, write nothing")
    ap.add_argument("--init-i18n", action="store_true", help="add src/pages/[lang]/ for a multi-language site")
    ap.add_argument("--palettes", type=Path, default=REFS / "palettes.json")
    ap.add_argument("--directions", type=Path, default=REFS / "directions.json")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    site = args.site.resolve()

    if args.record or args.record_all:
        out = record(site, None if args.record_all else args.record)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"recorded {len(out['recorded'])} file(s); {out['tracked']} tracked")
            for s in out["skipped"]:
                print(f"  skipped (missing or a data file): {s}")
        return 0

    if args.init_i18n:
        out = init_i18n(site)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            for key in ("created", "replaced", "kept"):
                if out[key]:
                    print(f"{key}: {', '.join(out[key])}")
            for w in out["warnings"]:
                print(f"warning: {w}")
        return 0

    out = sync(site, args.palettes, args.directions, write=not args.status)
    if args.json:
        print(json.dumps(out, indent=2))
        return 0
    if not args.status:
        print(f"data files written: {', '.join(out['written']) or 'none (already up to date)'}")
        if out["removed"]:
            print(f"removed: {', '.join(out['removed'])}")
        if out["packages"]:
            print(f"package.json fonts: {' '.join(out['packages'])} (run npm install)")
    st = out["status"]
    print(
        f"generated files: {len(st['clean'])} clean, {len(st['edited'])} edited, "
        f"{len(st['missing'])} missing, {len(st['untracked'])} untracked"
    )
    for key, label in (
        ("edited", "EDITED by hand (do not overwrite; write to .shingle/pending/)"),
        ("missing", "missing"),
        ("untracked", "untracked (owned by user unless just generated)"),
    ):
        if st[key]:
            print(f"  {label}:")
            for rel in st[key]:
                print(f"    {rel}")
    for w in out["warnings"]:
        print(f"warning: {w}")
    i18n = out["i18n"]
    if len(i18n["languages"]) > 1:
        print(f"languages: {', '.join(i18n['languages'])} (default {i18n['default']})")
        for code, paths in i18n["untranslated"].items():
            print(
                f"  {code}: {len(paths)} text field(s) fall back to {i18n['default']}: {', '.join(paths[:6])}{' …' if len(paths) > 6 else ''}"
            )
        for code in i18n["draft"]:
            print(
                f'  {code}: translation still marked draft (set translations.{code}.review to "reviewed" after a native speaker checks it)'
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
