#!/usr/bin/env python3
"""Capture the screenshots used by the documentation section of the landing page.

Every image is made from real material, never mocked up:
  - terminal cards render the actual output of the Shingle scripts for the Marigold Kitchen
    example (validate_input, check_contrast, audit_site, sync) and real reference files;
  - site shots are screenshots of the built examples (examples/<name>/dist).

Usage:
    python3 .github/scripts/capture_guide.py [--chrome PATH] [--only NAME ...]

Needs the examples built first (cd examples/<name> && npm ci && npm run build) and a headless
Chrome. It looks for `chrome-headless-shell` in docs/demo-video/node_modules/.remotion, then for
Chrome / Chromium on PATH; pass --chrome to override. Output: docs/media/guide/*.png
"""

from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "shingle" / "scripts"
REFS = ROOT / "skills" / "shingle" / "references"
OUT = ROOT / "docs" / "media" / "guide"
MARIGOLD = ROOT / "examples" / "marigold-kitchen"
BARRO = ROOT / "examples" / "barro-e-luz"

TERMINAL_CSS = """
:root { color-scheme: dark; }
* { box-sizing: border-box; }
body { margin: 0; background: #0f1012; font: 15px/1.55 ui-monospace, SFMono-Regular, Menlo, monospace; color: #e7e6e2; }
.win { margin: 24px; border: 1px solid #2c2e33; border-radius: 12px; overflow: hidden; background: #17181b; }
.bar { display: flex; gap: 8px; align-items: center; padding: 10px 14px; background: #202226; border-bottom: 1px solid #2c2e33; color: #9a9ca2; font-size: 13px; }
.dot { width: 11px; height: 11px; border-radius: 50%; background: #3a3c42; }
.bar b { margin-left: 8px; font-weight: 500; }
pre { margin: 0; padding: 18px 20px 22px; white-space: pre-wrap; word-break: break-word; }
.p { color: #fb8a4c; } .ok { color: #7fd48b; } .warn { color: #e6c15a; } .dim { color: #8d8f96; }
"""

CARD_CSS = """
:root { color-scheme: light; --bg:#f7f6f3; --fg:#18181a; --muted:#55575b; --line:#dcd8d1; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--fg); font: 16px/1.5 system-ui, sans-serif; padding: 28px; }
h2 { font-size: 15px; margin: 0 0 12px; color: var(--muted); font-weight: 600; letter-spacing: .02em; text-transform: uppercase; }
.grid { display: grid; gap: 16px; }
.card { background: #fff; border: 1px solid var(--line); border-radius: 12px; padding: 18px 20px; }
.row { display: flex; justify-content: space-between; gap: 16px; padding: 8px 0; border-bottom: 1px solid var(--line); }
.row:last-child { border-bottom: 0; }
.row span:first-child { color: var(--muted); }
.row span:last-child { font-weight: 600; text-align: right; }
.sw { display: flex; border-radius: 8px; overflow: hidden; border: 1px solid var(--line); height: 54px; margin: 10px 0; }
.sw i { flex: 1; }
.tag { display: inline-block; font-size: 12px; font-weight: 700; padding: 2px 8px; border-radius: 99px; background: #e8f5e9; color: #1b5e20; }
.tag.pick { background: #fff1e6; color: #8a2f00; }
h3 { margin: 0 0 2px; font-size: 18px; } p { margin: 0; color: var(--muted); font-size: 14px; }
"""


def find_chrome(explicit: str | None) -> str:
    if explicit:
        return explicit
    found = sorted(
        f for f in (ROOT / "docs" / "demo-video" / "node_modules" / ".remotion").glob("**/chrome-headless-shell") if f.is_file()
    )
    if found:
        return str(found[0])
    for name in ("chrome-headless-shell", "chromium", "google-chrome", "chrome"):
        if path := shutil.which(name):
            return path
    mac = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if Path(mac).exists():
        return mac
    sys.exit("No headless Chrome found. Pass --chrome PATH.")


def run(cmd: list[str], cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return (proc.stdout + proc.stderr).rstrip()


def colour(line: str) -> str:
    esc = html.escape(line)
    esc = re.sub(r"^(OK:|PASS:?)", r'<span class="ok">\1</span>', esc)
    esc = re.sub(r"^(WARN\w*:?|missing:)", r'<span class="warn">\1</span>', esc)
    return esc


def terminal(title: str, blocks: list[tuple[str, str]]) -> str:
    """blocks: (command, output) pairs."""
    body = []
    for cmd, out in blocks:
        body.append(f'<span class="p">$</span> {html.escape(cmd)}')
        body.extend(colour(line) for line in out.splitlines())
        body.append("")
    return (
        f"<!doctype html><meta charset=utf-8><style>{TERMINAL_CSS}</style>"
        f'<div class="win"><div class="bar"><span class="dot"></span><span class="dot"></span>'
        f'<span class="dot"></span><b>{html.escape(title)}</b></div><pre>{chr(10).join(body).rstrip()}</pre></div>'
    )


def cards(inner: str) -> str:
    return f"<!doctype html><meta charset=utf-8><style>{CARD_CSS}</style><div class=grid>{inner}</div>"


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args: object) -> None:
        pass


def serve(directory: Path) -> tuple[http.server.ThreadingHTTPServer, int]:
    handler = functools.partial(Quiet, directory=str(directory))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, server.server_address[1]


def shot(chrome: str, url: str, out: Path, width: int, height: int, scale: int = 1, dark: bool = False) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    helper = Path(__file__).with_name("shot.mjs")
    cmd = ["node", str(helper), chrome, url, str(out), str(width), str(height), str(scale), "1" if dark else "0"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
    if not out.exists():
        sys.exit(f"screenshot failed for {url}\n{proc.stderr[-500:]}")
    print(f"  {out.relative_to(ROOT)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chrome")
    ap.add_argument("--only", nargs="*", help="capture only these names")
    args = ap.parse_args()
    chrome = find_chrome(args.chrome)
    for site in (MARIGOLD, BARRO):
        if not (site / "dist").is_dir():
            sys.exit(f"{site.name} is not built: cd {site.relative_to(ROOT)} && npm ci && npm run build")

    biz = json.loads((MARIGOLD / "business.json").read_text())
    decisions = biz["decisions"]
    palettes = {p["id"]: p for p in json.loads((REFS / "palettes.json").read_text())["palettes"]}
    directions = json.loads((REFS / "directions.json").read_text())["directions"]
    categories = json.loads((REFS / "categories.json").read_text())["categories"]

    tmp = Path(tempfile.mkdtemp(prefix="shingle-guide-"))
    todo: dict[str, tuple[str, int, int]] = {}  # name -> (page path or url, w, h)

    def page(name: str, content: str, w: int, h: int) -> None:
        (tmp / f"{name}.html").write_text(content, encoding="utf-8")
        todo[name] = (f"file://{tmp / (name + '.html')}", w, h)

    # 1. Read and normalize
    page("step-1-intake", terminal("1 · Read and normalize", [
        ("python3 validate_input.py business.json", run([sys.executable, str(SCRIPTS / "validate_input.py"), "business.json"], cwd=MARIGOLD)),
    ]), 980, 330)

    # 2. Category
    cat = categories[biz["category"]]
    playbook = (REFS / "categories" / f"{biz['category']}.md").read_text().splitlines()
    first = "\n".join(playbook[2:10]).replace("**", "").replace("`", "")
    page("step-2-category", terminal("2 · Pick the closest category", [
        (f"matched category: {cat['label']}  (schema.org/{cat['schema_type']})", ""),
        (f"head references/categories/{biz['category']}.md", first),
    ]), 1100, 520)

    # 3. Interview, as recorded in business.json
    rows = "".join(
        f'<div class="row"><span>{html.escape(k)}</span><span>{html.escape(v)}</span></div>'
        for k, v in [
            ("goal", decisions["goal"]),
            ("call to action", f'{decisions["cta"]["label"]} ({decisions["cta"]["action"]})'),
            ("pages", decisions["pages"]),
            ("tone", decisions["tone"]),
            ("imagery", decisions["imagery"]),
            ("contact methods", ", ".join(decisions["contact_method"])),
            ("features", ", ".join(decisions["features"])),
        ]
    )
    page("step-3-interview", cards(f'<div class="card"><h2>Interview answers recorded in business.json</h2>{rows}</div>'), 760, 440)

    # 4. Design: palettes and direction
    d = decisions["design"]
    pal = palettes[d["palette"]]
    others = [p for p in palettes.values() if biz["category"] in p.get("categories", [])][:3]
    if pal not in others:
        others = [pal, *others[:2]]
    blocks = []
    for p in others:
        chosen = p["id"] == d["palette"]
        light = p["light"]
        swatches = "".join(f'<i style="background:{v}" title="{html.escape(k)}"></i>' for k, v in list(light.items())[:6])
        verdict = run([sys.executable, str(SCRIPTS / "check_contrast.py"), "--palette", p["id"]]).splitlines()[0]
        blocks.append(
            f'<div class="card"><h3>{html.escape(p["name"])} <span class="tag{" pick" if chosen else ""}">{"chosen" if chosen else "option"}</span></h3>'
            f'<p>{html.escape(p["rationale"])}</p><div class="sw">{swatches}</div><p><span class="tag">{html.escape(verdict)}</span> WCAG AA contrast, light and dark</p></div>'
        )
    dname = directions[d["direction"]]["name"]
    page("step-4-design", cards(f'<h2>Palettes checked for contrast · direction: {html.escape(dname)}</h2>{"".join(blocks)}'), 860, 150 + 205 * len(blocks))

    # 5. Build: the finished site
    # 6. Audit
    audit = run([sys.executable, str(SCRIPTS / "audit_site.py"), "dist", "--strict"], cwd=MARIGOLD)
    page("step-6-audit", terminal("6 · Audit and fix", [("python3 audit_site.py dist --strict", audit)]), 1100, 160 + 26 * (len(audit.splitlines()) + 2))

    # 7. Hand over
    sync = run([sys.executable, str(SCRIPTS / "sync.py"), ".", "--status"], cwd=MARIGOLD)
    page("step-7-handover", terminal("7 · Hand over", [("python3 sync.py . --status", sync)]), 980, 240)

    # Usage: install and deploy commands (literal commands from the README and deploy.md)
    page("use-install", terminal("In Claude Code", [
        ("/plugin marketplace add OneLab-X/shingle", ""),
        ("/plugin install shingle@shingle", ""),
        ("/shingle Marigold Kitchen, Goan restaurant, 27 Fenwick Lane London E8 4QT, 020 7946 0321", ""),
    ]), 1100, 250)
    page("use-deploy", terminal("Deploy: pick one host", [
        ("git init && git add -A && git commit -m Site && gh repo create --source . --push --public   # GitHub Pages", ""),
        ("npx netlify-cli deploy --prod --dir=dist                                                   # Netlify", ""),
        ("npx wrangler pages deploy dist                                                             # Cloudflare Pages", ""),
    ]), 1300, 250)

    # Usage: photos, imported into a scratch copy so the example is not modified
    scratch = Path(tempfile.mkdtemp(prefix="shingle-scratch-"))
    photos = ROOT / "examples" / "harbour-loaf-bakery" / "public" / "images"
    site = scratch / "site"
    (site / "public").mkdir(parents=True)
    shutil.copy(MARIGOLD / "business.json", site / "business.json")
    shutil.copytree(photos, scratch / "photos", ignore=shutil.ignore_patterns(".gitkeep"))
    imp = run([sys.executable, str(SCRIPTS / "import_images.py"), "photos", "--site", "site", "--dry-run"], cwd=scratch)
    page("use-photos", terminal("Add your photos", [("python3 import_images.py ./photos --site . --dry-run", imp)]), 1200, 160 + 26 * (len(imp.splitlines()) + 2))

    # Usage: update after editing business.json, on a scratch copy
    upd = scratch / "update"
    upd.mkdir()
    for name in ("business.json", "src", "public", "astro.config.mjs", "package.json", ".shingle", "README.md"):
        src = MARIGOLD / name
        shutil.copytree(src, upd / name) if src.is_dir() else shutil.copy(src, upd / name)
    edited = json.loads((upd / "business.json").read_text())
    old_phone = edited["phone_display"]
    edited["phone_display"] = "020 7946 0999"
    edited["phone"] = "+442079460999"
    (upd / "business.json").write_text(json.dumps(edited, indent=2, ensure_ascii=False) + "\n")
    sync_out = run([sys.executable, str(SCRIPTS / "sync.py"), "."], cwd=upd)
    page("use-update", terminal("Update later", [
        (f"# edit business.json: phone_display  {old_phone} -> 020 7946 0999", ""),
        ("python3 sync.py .", sync_out),
        ("grep -n 7946 src/data/site.json", run(["grep", "-n", "7946", "src/data/site.json"], cwd=upd)),
    ]), 1100, 420)

    # Features: structured data from the real built page
    index = (MARIGOLD / "dist" / "index.html").read_text()
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', index, re.S)
    ld = json.loads(m.group(1)) if m else {}
    ld_text = json.dumps(ld, indent=2, ensure_ascii=False).splitlines()
    page("feature-seo", terminal("LocalBusiness JSON-LD, built into every page", [
        ("grep -A40 'ld+json' dist/index.html", "\n".join(ld_text[:34] + (["  …"] if len(ld_text) > 34 else []))),
    ]), 980, 160 + 24 * min(len(ld_text), 35))

    # Site shots
    m_server, m_port = serve(MARIGOLD / "dist")
    b_server, b_port = serve(BARRO / "dist")
    m_url, b_url = f"http://127.0.0.1:{m_port}/", f"http://127.0.0.1:{b_port}/"
    todo["step-5-build"] = (m_url, 1280, 800)
    todo["feature-mobile"] = (m_url, 390, 844)
    todo["feature-dark"] = (m_url, 1280, 800)
    todo["feature-hours"] = (m_url + "#visit", 1280, 800)
    todo["feature-languages"] = (b_url + "pt/" if (BARRO / "dist" / "pt").is_dir() else b_url, 1280, 800)
    todo["feature-og"] = (m_url + "og.png", 1200, 630)

    scales = {"feature-mobile": 2}
    for name, (url, w, h) in todo.items():
        if args.only and name not in args.only:
            continue
        shot(chrome, url, OUT / f"{name}.png", w, h, scales.get(name, 1), dark=name == "feature-dark")
    m_server.shutdown()
    b_server.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(scratch, ignore_errors=True)


if __name__ == "__main__":
    main()
