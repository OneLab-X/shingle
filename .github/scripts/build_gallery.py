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

# (screenshot, title, what to do, command shown under the text or "")
STEPS = [
    ("use-install", "Install and run", "Add the plugin from the marketplace in Claude Code, then run /shingle with whatever you know. A name and a phone number is enough to start. You can also pass a business.json file, a Google Business Profile export (.csv, .tsv, .xlsx), or the folder of a site Shingle already built.", "/plugin marketplace add OneLab-X/shingle\n/plugin install shingle@shingle\n/shingle ./business.json"),
    ("step-1-intake", "Check what it understood", "Shingle normalizes phones, hours and addresses, then tells you what is missing. Fix anything wrong in business.json, or just tell Claude.", ""),
    ("step-2-category", "Confirm the category", "It picks the closest of 13 categories and loads that playbook (audience, tone, required sections, things never to invent). Say so if the category is wrong.", ""),
    ("step-3-interview", "Answer the interview", "Up to four multiple-choice questions per round, each with a recommended answer first. Accept the recommendation or pick another. Your answers are saved in business.json, so re-running never asks twice.", ""),
    ("step-4-design", "Pick a palette and design direction", "Choose from two or three palettes and a direction. Every palette is checked for WCAG AA contrast in light and dark mode before you see it.", ""),
    ("step-5-build", "Preview the site", "Shingle builds an Astro site in your folder and starts a preview. Look at it on desktop and phone, and ask for changes in plain words.", "cd my-site\nnpm install\nnpm run dev"),
    ("use-photos", "Add your photos", "Point Shingle at a folder of photos. It strips location, camera and date data from the copies, suggests alt text for you to confirm in one table, and swaps the placeholders for real images. Shingle never invents or hotlinks photos.", "/shingle import the photos in ./photos"),
    ("step-6-audit", "Review the audit and fill placeholders", "The audit checks links, alt text, meta tags, JSON-LD, phone and address consistency, fake reviews and filler copy. Anything the site needs from you appears as a visible TODO(shingle) placeholder, listed with its file and line.", "python3 audit_site.py dist --strict"),
    ("use-deploy", "Deploy", "Pick one host. All three are free for sites like these. Then point your domain at it and submit the sitemap to Google Search Console.", ""),
    ("use-update", "Update it later", "Edit business.json (new hours, a new phone number) and run /shingle on the site folder. Facts update everywhere, and your own edits to pages are never overwritten: Shingle saves its proposed version next to yours instead.", "/shingle ./my-site"),
]

FEATURES = [
    ("feature-mobile", "Phone first", "Laid out for a 390 px screen first: tap-to-call, large targets, nothing behind hover."),
    ("feature-dark", "Light and dark modes", "Both use the same checked palette and follow the visitor's system setting."),
    ("feature-hours", "Real opening hours", "Today is highlighted and the header shows whether you are open right now."),
    ("feature-languages", "More than one language", "List several languages in business.json and each gets its own pages, a switcher and hreflang."),
    ("feature-seo", "Local SEO built in", "schema.org markup for your business type, with name, address, phone and hours checked on every page."),
    ("feature-og", "Social cards", "A branded Open Graph image is rendered at build time so shared links look right."),
]


def guide_section(out: Path, base: str) -> str:
    """How-to-use section: one screenshot per usage step and per feature."""
    if not GUIDE.is_dir():
        return ""
    (out / "guide").mkdir(exist_ok=True)

    def img(slug: str, alt: str) -> str:
        shot = GUIDE / f"{slug}.png"
        if not shot.exists():
            return ""
        shutil.copy(shot, out / "guide" / shot.name)
        return f'<figure><img src="{base}/guide/{shot.name}" alt="{html.escape(alt)}: screenshot" loading="lazy"></figure>'

    steps = []
    for i, (slug, title, text, cmd) in enumerate(STEPS, 1):
        code = f"<pre><code>{html.escape(cmd)}</code></pre>" if cmd else ""
        steps.append(
            f'<li class="step" id="step-{i}">{img(slug, title)}<div><span class="num">{i}</span>'
            f"<h3>{html.escape(title)}</h3><p>{html.escape(text)}</p>{code}</div></li>"
        )
    feats = "".join(
        f'<li class="feat">{img(slug, title)}<h3>{html.escape(title)}</h3><p>{html.escape(text)}</p></li>'
        for slug, title, text in FEATURES
    )
    return f"""<section id="how" aria-labelledby="how-h">
<h2 id="how-h" class="sec">How to use Shingle</h2>
<p class="lead">You need <a href="https://claude.com/claude-code">Claude Code</a>, Node 22.23.4+ and Python 3.9+. From install to a live site takes ten steps; the pictures show real output for the Marigold Kitchen example.</p>
<ol class="steps">{"".join(steps)}</ol>
<h2 id="features" class="sec">What your site includes</h2>
<ul class="feats">{feats}</ul>
</section>
<h2 id="examples" class="sec">Examples to look at</h2>"""


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
<title>How to use Shingle</title><meta name="description" content="Sites generated by Shingle, a Claude Code plugin that turns a business's details into a finished website.">
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
pre {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:.75rem 1rem; overflow-x:auto; font-size:.875rem; margin:.75rem 0 0; }}
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
<p class="lead">Business details in, website out. A Claude Code plugin that interviews you about a local business and builds an accessible, production-ready site. <a href="#how">How to use it</a> · <a href="#examples">Examples</a></p>
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
