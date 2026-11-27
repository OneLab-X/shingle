"""Shared test helpers: import path setup and fixture builders."""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

BUSINESS = {
    "name": "Marigold Kitchen",
    "category": "restaurant",
    "domain": "marigoldkitchen.pt",
    "address": {"street": "Rua da Rosa 112", "locality": "Lisboa", "postal_code": "1200-389", "country": "PT"},
    "phone": "+351213000000",
    "email": "ola@marigoldkitchen.pt",
    "hours": {"mon": [], "tue": [["12:00", "15:00"], ["19:00", "23:00"]], "fri": [["19:00", "00:30"]]},
    "socials": {"instagram": "https://instagram.com/marigoldkitchen"},
    "facts": {"cuisine": ["Goan"], "price_range": "€€"},
    "decisions": {"features": ["menu"], "design": {"direction": "broadsheet", "palette": "saffron-ink"}},
}


def write_json(path: Path, data) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def jsonld(**overrides) -> str:
    data = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": "Marigold Kitchen",
        "telephone": "+351213000000",
        "address": {"@type": "PostalAddress", "streetAddress": "Rua da Rosa 112"},
        "openingHoursSpecification": [
            {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Tuesday"], "opens": "12:00", "closes": "15:00"}
        ],
    }
    data.update(overrides)
    return json.dumps(data)


def page(
    body: str,
    *,
    title: str = "Marigold Kitchen · Goan restaurant in Lisboa",
    description: str = "Family-run Goan restaurant in Bairro Alto, Lisbon. Fish curries, xacuti and bebinca. Open Tuesday to Sunday.",
    ld: str | None = None,
    path: str = "/",
    head_extra: str = "",
) -> str:
    ld = jsonld() if ld is None else ld
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<meta name="description" content="{description}">
<link rel="canonical" href="https://marigoldkitchen.pt{path}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="https://marigoldkitchen.pt/og.png">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<script type="application/ld+json">{ld}</script>
{head_extra}
</head>
<body>{body}</body>
</html>"""


GOOD_HOME = """
<a href="#main" class="skip">Skip to content</a>
<header><a href="/">Marigold Kitchen</a> <a href="/about/">About</a> <a href="/about/#story">Our story</a></header>
<main id="main">
<h1>Goan cooking in Bairro Alto</h1>
<img src="/images/room.svg" alt="Dining room with blue tiles" width="800" height="600">
<a href="tel:+351213000000">21 300 0000</a>
<a href="https://instagram.com/marigoldkitchen" target="_blank" rel="noopener noreferrer">Instagram</a>
<button type="button" aria-label="Show map"><svg aria-hidden="true"></svg></button>
<form><input type="checkbox" name="botcheck" style="display:none" tabindex="-1" aria-hidden="true"><label for="n">Name</label><input id="n" name="name"><label>Email <input name="email" type="email"></label><button>Send</button></form>
<iframe title="Map showing Marigold Kitchen" src="https://www.google.com/maps?q=x&output=embed"></iframe>
<p data-shingle-todo="Add 3 photos of signature dishes">Photo coming soon</p>
</main>
"""

GOOD_ABOUT = """<main><h1>About Marigold Kitchen</h1><h2 id="story">Our story</h2><p>Family-run since the owners say so.</p><a href="/">Home</a></main>"""


def build_good_dist(root: Path) -> Path:
    dist = root / "dist"
    (dist / "about").mkdir(parents=True)
    (dist / "images").mkdir()
    (dist / "index.html").write_text(page(GOOD_HOME), encoding="utf-8")
    (dist / "about" / "index.html").write_text(
        page(GOOD_ABOUT, title="About · Marigold Kitchen", path="/about/"), encoding="utf-8"
    )
    (dist / "404.html").write_text(
        page('<main><h1>Page not found</h1><a href="/">Go home</a></main>', title="Not found · Marigold Kitchen"),
        encoding="utf-8",
    )
    (dist / "images" / "room.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (dist / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (dist / "og.png").write_bytes(b"\x89PNG\r\n")
    (dist / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://marigoldkitchen.pt/sitemap-index.xml\n", encoding="utf-8"
    )
    (dist / "sitemap-index.xml").write_text("<sitemapindex/>", encoding="utf-8")
    (dist / "_astro").mkdir()
    (dist / "_astro" / "app.css").write_text("body{background:var(--sh-background)}", encoding="utf-8")
    write_json(root / "business.json", BUSINESS)
    return dist
