#!/usr/bin/env python3
"""Assemble the GitHub Pages gallery: copy each built example and write an index page.

Usage: python3 .github/scripts/build_gallery.py --out _site --base /repo-name
Expects examples/<name>/dist to exist (built with SHINGLE_BASE=<base>/examples/<name>/).
"""

from __future__ import annotations

import argparse
import html
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REFS = ROOT / "skills" / "shingle" / "references"

GUIDE = ROOT / "docs" / "media" / "guide"

STEPS = [
    ("step-1-intake", "Read and normalize", "Give it a name and a phone number, a file, or a Google Business Profile export. Shingle normalizes phones to E.164, turns free-text hours into a schedule, and lists what is missing instead of guessing."),
    ("step-2-category", "Pick the closest category", "One of 13 categories (restaurant, dental clinic, plumber…) is loaded as a short playbook: audience, tone, required sections, schema.org type and the things never to invent."),
    ("step-3-interview", "Interview in a few questions", "At most four multiple-choice questions per round, each with a recommended answer: goal, pages, tone, photos, booking, features. Answers are saved to business.json so reruns never ask twice."),
    ("step-4-design", "Choose palette and direction", "Two or three palettes plus one of ten design directions, all checked for WCAG AA contrast in light and dark mode by script, not by eye."),
    ("step-5-build", "Build the site", "An Astro + Tailwind project with real copy from your facts, LocalBusiness JSON-LD, Open Graph, sitemap, robots, favicon and contact links that work without a backend."),
    ("step-6-audit", "Audit and fix", "Broken links, alt text, meta tags, JSON-LD and NAP consistency, fake reviews, lorem ipsum, emoji icons. Every problem is fixed before you see the site; every placeholder is listed with its file and line."),
    ("step-7-handover", "Hand over, then stay in sync", "You get the decisions made, the placeholders to fill, and one-command deploys for GitHub Pages, Netlify or Cloudflare Pages. Edit business.json and re-run: hand edits are never overwritten."),
]

FEATURES = [
    ("feature-mobile", "Phone first", "Every site is laid out for a 390 px screen first: tap-to-call, large targets, nothing hidden behind hover."),
    ("feature-dark", "Light and dark modes", "Both modes use the same checked palette, follow the visitor's system setting and can be toggled."),
    ("feature-hours", "Real opening hours", "Hours come from a schedule, so the current day is highlighted and the header shows whether you are open right now."),
    ("feature-languages", "Multi-language sites", "List more than one language and each gets its own pages, a switcher and hreflang tags."),
    ("feature-seo", "Local SEO built in", "schema.org markup for the business type, with name, address, phone and hours checked for consistency on every page."),
    ("feature-og", "Social cards at build time", "A branded Open Graph image is rendered for every site, so links look right when shared."),
]


def guide_section(out: Path, base: str) -> str:
    """Documentation section: one screenshot per development step and per feature."""
    if not GUIDE.is_dir():
        return ""
    (out / "guide").mkdir(exist_ok=True)

    def figure(slug: str, title: str, text: str, n: int | None) -> str:
        shot = GUIDE / f"{slug}.png"
        if not shot.exists():
            return ""
        shutil.copy(shot, out / "guide" / shot.name)
        num = f'<span class="num">{n}</span>' if n else ""
        return (
            f'<li class="{"step" if n else "feat"}"><figure><img src="{base}/guide/{shot.name}" alt="{html.escape(title)}: screenshot" loading="lazy"></figure>'
            f"<div>{num}<h3>{html.escape(title)}</h3><p>{html.escape(text)}</p></div></li>"
        )

    steps = "".join(figure(slug, t, d, i) for i, (slug, t, d) in enumerate(STEPS, 1))
    feats = "".join(figure(slug, t, d, None) for slug, t, d in FEATURES)
    return f"""<section id="how" aria-labelledby="how-h">
<h2 id="how-h" class="sec">How it works</h2>
<p class="lead">Seven steps from a phone number to a deployed site. Every screenshot below is real output for the Marigold Kitchen example: the terminal cards are the actual scripts, the site shots are the built site.</p>
<ol class="steps">{steps}</ol>
<h2 id="features" class="sec">What you get</h2>
<ul class="feats">{feats}</ul>
</section>
<h2 id="examples" class="sec">Examples</h2>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("_site"))
    ap.add_argument("--base", default="")
    args = ap.parse_args()
    out: Path = args.out
    base = args.base.rstrip("/")
    if out.exists():
        shutil.rmtree(out)
    (out / "examples").mkdir(parents=True)
    directions = json.loads((REFS / "directions.json").read_text())["directions"]
    palettes = {p["id"]: p for p in json.loads((REFS / "palettes.json").read_text())["palettes"]}

    cards = []
    for ex in sorted((ROOT / "examples").iterdir()):
        dist, bpath = ex / "dist", ex / "business.json"
        if not (dist.is_dir() and bpath.exists()):
            continue
        shutil.copytree(dist, out / "examples" / ex.name)
        b = json.loads(bpath.read_text())
        design = b.get("decisions", {}).get("design", {})
        shot = ROOT / "docs" / "media" / "examples" / f"{ex.name}.png"
        img = ""
        if shot.exists():
            (out / "shots").mkdir(exist_ok=True)
            shutil.copy(shot, out / "shots" / shot.name)
            img = f'<img src="{base}/shots/{shot.name}" alt="Screenshot of the {html.escape(b["name"])} example" width="1280" height="800" loading="lazy">'
        languages = b.get("languages") or []
        langs = f" · {' + '.join(html.escape(code) for code in languages)}" if len(languages) > 1 else ""
        cards.append(
            f"""<li><a href="{base}/examples/{ex.name}/">{img}
<h2>{html.escape(b["name"])}</h2>
<p>{html.escape(b["category"])} · {html.escape(directions.get(design.get("direction", ""), {}).get("name", ""))} · {html.escape(palettes.get(design.get("palette", ""), {}).get("name", ""))}{langs}</p></a>
<p class="src"><a href="https://github.com/OneLab-X/shingle/tree/main/examples/{ex.name}">Source and business.json</a></p></li>"""
        )

    (out / "index.html").write_text(
        f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Shingle: how it works and examples</title><meta name="description" content="Sites generated by Shingle, a Claude Code plugin that turns a business's details into a finished website.">
<meta name="robots" content="noindex">
<style>
:root {{ color-scheme: light dark; --bg:#f7f6f3; --fg:#18181a; --muted:#55575b; --card:#fff; --line:#dcd8d1; --accent:#b83e00; }}
@media (prefers-color-scheme: dark) {{ :root {{ --bg:#121314; --fg:#edece8; --muted:#a9a9a6; --card:#1c1d1f; --line:#2f3033; --accent:#fb8a4c; }} }}
body {{ margin:0; font:16px/1.6 system-ui, sans-serif; background:var(--bg); color:var(--fg); }}
main {{ width:min(100% - 2rem, 72rem); margin:0 auto; padding:3rem 0; }}
h1 {{ font-size:clamp(2rem,5vw,3.5rem); line-height:1.05; margin:0 0 .5rem; }}
.lead {{ color:var(--muted); max-width:60ch; }}
ul.cards {{ list-style:none; padding:0; display:grid; gap:1.5rem; grid-template-columns:repeat(auto-fill,minmax(20rem,1fr)); margin-top:2.5rem; }}
ul.cards > li {{ background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden; }}
ul.cards li > a {{ color:inherit; text-decoration:none; display:block; }}
img {{ width:100%; height:auto; display:block; border-bottom:1px solid var(--line); }}
h2 {{ font-size:1.25rem; margin:1rem 1.25rem .25rem; }}
ul.cards li p {{ margin:0 1.25rem; color:var(--muted); font-size:.9375rem; }}
.src {{ padding:.5rem 0 1rem; }} .src a {{ color:var(--accent); }}
.sec {{ font-size:1.75rem; margin:3rem 0 .5rem; }}
.steps {{ list-style:none; padding:0; margin:2rem 0 0; display:grid; gap:2.5rem; }}
.steps > li {{ display:grid; gap:1rem 2rem; grid-template-columns:minmax(0,3fr) minmax(0,2fr); align-items:center; }}
.steps > li:nth-child(even) figure {{ order:2; }}
figure {{ margin:0; border:1px solid var(--line); border-radius:10px; overflow:hidden; background:var(--card); }}
figure img {{ border-bottom:0; }}
.num {{ display:inline-grid; place-items:center; width:2rem; height:2rem; border-radius:50%; background:var(--accent); color:var(--bg); font-weight:700; margin-bottom:.5rem; }}
.steps h3, .feats h3 {{ font-size:1.25rem; margin:.25rem 0; }}
.steps p, .feats p {{ margin:0; color:var(--muted); }}
.feats {{ list-style:none; padding:0; margin:1.5rem 0 0; display:grid; gap:1.5rem; grid-template-columns:repeat(auto-fill,minmax(19rem,1fr)); }}
.feats figure {{ margin-bottom:.75rem; }}
.feats figure {{ aspect-ratio:16/10; }}
.feats img {{ width:100%; height:100%; object-fit:cover; object-position:top; }}
.feats img[src*="mobile"] {{ object-fit:contain; background:var(--line); }}
@media (max-width:48rem) {{ .steps > li {{ grid-template-columns:1fr; }} .steps > li:nth-child(even) figure {{ order:0; }} }}
a:focus-visible {{ outline:3px solid var(--accent); outline-offset:3px; }}
</style></head>
<body><main>
<h1>Shingle</h1>
<p class="lead">Business details in, website out. A Claude Code plugin that interviews you about a local business and builds an accessible, production-ready site. <a href="#how">How it works</a> · <a href="#examples">Examples</a></p>
<p class="lead">Every example here was generated by <a href="https://github.com/OneLab-X/shingle">Shingle</a> from a short business.json.
All businesses are fictional. Each one uses a different design direction.</p>
{guide_section(out, base)}
<ul class="cards">{"".join(cards)}</ul>
</main></body></html>
""",
        encoding="utf-8",
    )
    print(f"gallery: {len(cards)} examples -> {out}")


if __name__ == "__main__":
    main()
