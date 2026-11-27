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
    lang: str = "en",
    title: str = "Marigold Kitchen · Goan restaurant in Lisboa",
    description: str = "Family-run Goan restaurant in Bairro Alto, Lisbon. Fish curries, xacuti and bebinca. Open Tuesday to Sunday.",
    ld: str | None = None,
    path: str = "/",
    head_extra: str = "",
) -> str:
    ld = jsonld() if ld is None else ld
    return f"""<!doctype html>
<html lang="{lang}">
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


# ---------------------------------------------------------------- multi-language fixtures

I18N_BUSINESS = {**BUSINESS, "languages": ["pt", "en"]}
I18N_PAGES = ["", "contact/"]  # path under the language prefix


def i18n_page(code: str, tail: str, langs=("pt", "en"), *, tweaks=frozenset()) -> str:
    """One page of a bilingual site; `tweaks` introduce one specific defect."""
    base = "https://marigoldkitchen.pt"
    links = []
    for other in langs:
        if "one_way" in tweaks and code == "en" and other == "pt":
            continue  # the English page forgets to link back
        href = f"{base}/{other}/{tail}"
        if "wrong_target" in tweaks and code == "pt" and other == "en":
            href = f"{base}/en/"
        links.append(f'<link rel="alternate" hreflang="{other}" href="{href}">')
    if "no_xdefault" not in tweaks:
        links.append(f'<link rel="alternate" hreflang="x-default" href="{base}/{langs[0]}/{tail}">')
    og = "".join(f'<meta property="og:locale:alternate" content="{o}_XX">' for o in langs if o != code)
    if "no_og_alternate" in tweaks:
        og = ""
    head = "\n".join(links) + f'<meta property="og:locale" content="{code}_XX">' + og
    path = f"/{code}/{tail}"
    if "other_canonical" in tweaks and code == "en":
        path = f"/{langs[0]}/{tail}"
    switcher = (
        ""
        if "no_switcher" in tweaks
        else "".join(f'<a href="/{o}/{tail}" hreflang="{o}" lang="{o}">{o.upper()}</a>' for o in langs if o != code)
    )
    html_lang = "fr" if "wrong_lang" in tweaks and code == "en" else code
    other_link = "/contact/" if not tail else "/"
    title = "Marigold Kitchen" if not tail else "Contact · Marigold Kitchen"
    body = f'<main id="main"><h1>{title}</h1><nav aria-label="Language">{switcher}</nav><a href="/{code}{other_link}">link</a></main>'
    return page(body, lang=html_lang, title=title, path=path, head_extra=head)


def build_i18n_dist(root: Path, *, tweaks=frozenset(), langs=("pt", "en")) -> Path:
    dist = root / "dist"
    dist.mkdir(parents=True)
    for code in langs:
        for tail in I18N_PAGES:
            if "missing_page" in tweaks and code == "en" and tail == "contact/":
                continue
            out = dist / code / tail / "index.html"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(i18n_page(code, tail, langs, tweaks=tweaks), encoding="utf-8")
    if "no_redirect" not in tweaks:
        target = "/en/" if "bad_redirect" in tweaks else f"/{langs[0]}/"
        (dist / "index.html").write_text(
            f'<!doctype html><title>Redirecting</title><meta http-equiv="refresh" content="0;url={target}"><link rel="canonical" href="https://marigoldkitchen.pt{target}">',
            encoding="utf-8",
        )
    (dist / "404.html").write_text(
        page('<main><h1>Not found</h1><a href="/pt/">Home</a></main>', title="Not found · Marigold Kitchen"), encoding="utf-8"
    )
    (dist / "favicon.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    (dist / "og.png").write_bytes(b"\x89PNG\r\n")
    (dist / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nSitemap: https://marigoldkitchen.pt/sitemap-index.xml\n", encoding="utf-8"
    )
    (dist / "sitemap-index.xml").write_text("<sitemapindex/>", encoding="utf-8")
    alt = (
        ""
        if "no_sitemap_alternates" in tweaks
        else '<xhtml:link rel="alternate" hreflang="en" href="https://marigoldkitchen.pt/en/"/>'
    )
    (dist / "sitemap-0.xml").write_text(f"<urlset>{alt}</urlset>", encoding="utf-8")
    write_json(root / "business.json", I18N_BUSINESS)
    return dist
