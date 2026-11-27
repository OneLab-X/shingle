#!/usr/bin/env python3
"""Post-build audit for a Shingle site (the built dist/ folder).

Usage:
    python3 audit_site.py <site>/dist [--business <site>/business.json] [--src <site>/src]
                          [--json] [--strict]

Checks every HTML page for: broken internal links and anchors, missing alt text, title and meta
description, canonical and Open Graph tags, html lang, viewport, h1 count, JSON-LD validity and
NAP consistency with business.json, fabricated-review markup, unlabeled form fields, links and
buttons without accessible names, duplicate ids, iframes without titles, mixed content,
hotlinked images, image dimensions (layout shift), page weight, lorem ipsum, emoji used as
icons, filler phrases, and default purple gradients. Site-wide: robots.txt, sitemap, favicon,
404 page. Collects every TODO(shingle) placeholder with file:line.

Exit code: 0 clean, 1 errors (or warnings with --strict), 2 bad usage. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlparse

NAMED_TAGS = {"a", "button"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
EMOJI_RE = re.compile(
    "[\U0001f300-\U0001faff\U00002600-\U000027bf\U00002b00-\U00002bff\U0000231a-\U000023ff\U0001f000-\U0001f02f\U0001f0a0-\U0001f0ff\U0001f100-\U0001f1ff]"
)
LOREM_RE = re.compile(r"\blorem\s+ipsum\b|\bdolor\s+sit\s+amet\b", re.I)
FILLER = [
    "welcome to our website",
    "passionate about excellence",
    "your trusted partner",
    "we are passionate",
    "second to none",
    "world-class service",
    "best in town",
    "look no further",
    "one-stop shop",
    "cutting-edge solutions",
]
SLOP_COLORS = ["#8b5cf6", "#a855f7", "#7c3aed", "#6366f1", "#9333ea", "#c084fc", "#ec4899", "#d946ef"]
FORBIDDEN_LD = {"aggregateRating": "ratings", "review": "reviews", "award": "awards"}
PAGE_WEIGHT_WARN = 1_500_000
IMAGE_WEIGHT_WARN = 500_000


class Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = None
        self._in_title = False
        self.meta: dict[str, str] = {}
        self.meta_list: list[tuple[str, str]] = []  # every <meta>, in order (og:locale:alternate repeats)
        self.links: list[dict] = []  # <link>
        self.anchors: list[dict] = []  # <a>
        self.imgs: list[dict] = []
        self.iframes: list[dict] = []
        self.scripts: list[dict] = []
        self.ids: list[str] = []
        self.h1 = 0
        self.inputs: list[dict] = []
        self.label_for: set[str] = set()
        self.todos: list[str] = []
        self.named: list[dict] = []  # a/button with collected text
        self.headings: list[str] = []
        self.text_chunks: list[str] = []
        self._stack: list[dict] = []  # open a/button/heading/label/script/style collectors
        self._label_depth = 0

    # -- tag handling
    def handle_starttag(self, tag, attrs):
        a = {k: (v if v is not None else "") for k, v in attrs}
        if a.get("id"):
            self.ids.append(a["id"])
        if a.get("data-shingle-todo"):
            self.todos.append(a["data-shingle-todo"])
        if tag == "html":
            self.lang = a.get("lang")
        elif tag == "title":
            self._in_title = True
            self.title = ""
        elif tag == "meta":
            key = a.get("name") or a.get("property") or a.get("http-equiv")
            if key:
                self.meta[key.lower()] = a.get("content", "")
                self.meta_list.append((key.lower(), a.get("content", "")))
        elif tag == "link":
            self.links.append(a)
        elif tag == "img":
            self.imgs.append(a)
            if self._stack:
                for s in self._stack:
                    if s["tag"] in NAMED_TAGS and a.get("alt"):
                        s["text"] += " " + a["alt"]
        elif tag == "iframe":
            self.iframes.append(a)
        elif tag == "h1":
            self.h1 += 1
        elif tag == "label":
            self._label_depth += 1
            if a.get("for"):
                self.label_for.add(a["for"])
        elif tag in ("input", "select", "textarea"):
            hidden_from_at = (
                a.get("aria-hidden") == "true" or "hidden" in a or "display:none" in a.get("style", "").replace(" ", "")
            )
            if a.get("type", "").lower() not in ("hidden", "submit", "button", "reset", "image") and not hidden_from_at:
                self.inputs.append({**a, "_tag": tag, "_in_label": self._label_depth > 0})
        if tag == "svg" and self._stack:
            for s in self._stack:
                if s["tag"] in NAMED_TAGS and a.get("aria-label"):
                    s["text"] += " " + a["aria-label"]
        if tag in NAMED_TAGS or tag in HEADINGS or tag in ("script", "style", "title"):
            entry = {"tag": tag, "attrs": a, "text": ""}
            if tag != "title":
                self._stack.append(entry)
            if tag == "a":
                self.anchors.append(a)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "label":
            self._label_depth = max(0, self._label_depth - 1)
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i]["tag"] == tag:
                entry = self._stack.pop(i)
                if tag == "script":
                    self.scripts.append({"attrs": entry["attrs"], "text": entry["text"]})
                elif tag in NAMED_TAGS:
                    self.named.append(entry)
                elif tag in HEADINGS:
                    self.headings.append(entry["text"].strip())
                break

    def handle_data(self, data):
        if self._in_title:
            self.title = (self.title or "") + data
        in_code = any(s["tag"] in ("script", "style") for s in self._stack)
        for s in self._stack:
            s["text"] += data
        if not in_code:
            self.text_chunks.append(data)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_chunks))


class Audit:
    def __init__(self, dist: Path, business: dict | None) -> None:
        self.dist = dist
        self.business = business or {}
        self.issues: list[dict] = []
        self.todos: list[dict] = []
        self.pages: dict[str, Page] = {}

    def add(self, severity: str, page: str, message: str) -> None:
        self.issues.append({"severity": severity, "page": page, "message": message})

    # -- loading
    def load(self) -> None:
        for path in sorted(self.dist.rglob("*.html")):
            rel = path.relative_to(self.dist).as_posix()
            p = Page()
            p.feed(path.read_text(encoding="utf-8", errors="replace"))
            p.close()
            self.pages[rel] = p

    def resolve(self, href: str, from_page: str) -> tuple[Path | None, str]:
        """Map an internal href to a file in dist. Returns (path or None, fragment)."""
        u = urlparse(href)
        path = unquote(u.path)
        if not path:
            return self.dist / from_page, u.fragment
        if path.startswith("/"):
            base = self.dist / path.lstrip("/")
        else:
            base = (self.dist / from_page).parent / path
        candidates = [base, base / "index.html", base.with_suffix(".html")] if not path.endswith("/") else [base / "index.html"]
        for c in candidates:
            if c.is_file():
                return c, u.fragment
        return None, u.fragment

    def is_internal(self, href: str) -> bool:
        u = urlparse(href)
        if u.scheme in ("http", "https"):
            dom = self.business.get("domain")
            return bool(dom) and u.netloc.lower().removeprefix("www.") == dom.removeprefix("www.")
        return not u.scheme and not href.startswith("//")

    # -- checks
    def check_page(self, rel: str, p: Page) -> None:
        if not p.lang:
            self.add("error", rel, "<html> has no lang attribute")
        if not p.title or not p.title.strip():
            self.add("error", rel, "missing <title>")
        elif len(p.title.strip()) > 65:
            self.add("warning", rel, f"title is {len(p.title.strip())} chars; keep under ~60")
        desc = p.meta.get("description")
        if not desc:
            self.add("error", rel, "missing meta description")
        elif not 50 <= len(desc) <= 165:
            self.add("warning", rel, f"meta description is {len(desc)} chars; aim for 50-160")
        if "viewport" not in p.meta:
            self.add("error", rel, "missing viewport meta tag")
        is_404 = rel.startswith("404")
        if not is_404 and not any("canonical" in lk.get("rel", "").split() for lk in p.links):
            self.add("error", rel, "missing canonical link")
        for og in ("og:title", "og:description", "og:image"):
            if not is_404 and og not in p.meta:
                self.add("error", rel, f"missing {og}")
        if p.h1 == 0:
            self.add("error", rel, "no <h1>")
        elif p.h1 > 1:
            self.add("warning", rel, f"{p.h1} <h1> elements; use one per page")

        dupes = sorted({i for i in p.ids if p.ids.count(i) > 1})
        if dupes:
            self.add("error", rel, f"duplicate ids: {', '.join(dupes[:8])}")

        for img in p.imgs:
            src = img.get("src", "")
            if "alt" not in img:
                self.add("error", rel, f"<img> without alt: {src[:80]}")
            if not (img.get("width") and img.get("height")):
                self.add("warning", rel, f"<img> without width/height (layout shift): {src[:80]}")
            if src.startswith("http://"):
                self.add("error", rel, f"insecure image URL: {src[:80]}")
            elif src.startswith(("http", "//")) and not self.is_internal(src):
                self.add("error", rel, f"hotlinked external image {src[:80]}: use owner-provided local files")
            elif src and not src.startswith(("data:", "http", "//")):
                f, _ = self.resolve(src.split("?")[0], rel)
                if f is None:
                    self.add("error", rel, f"image not found: {src}")
                elif f.stat().st_size > IMAGE_WEIGHT_WARN:
                    self.add("warning", rel, f"large image {src} ({f.stat().st_size // 1024} KB)")

        for fr in p.iframes:
            if not fr.get("title"):
                self.add("error", rel, f"<iframe> without title: {fr.get('src', '')[:80]}")

        for a in p.anchors:
            href = a.get("href")
            if href is None:
                continue
            if href.strip() in ("", "#"):
                self.add("error", rel, f"link goes nowhere (href={href!r})")
                continue
            if href.startswith("http://"):
                self.add("warning", rel, f"insecure link {href[:80]}")
            if a.get("target") == "_blank" and "noopener" not in a.get("rel", ""):
                self.add("warning", rel, f"target=_blank without rel=noopener: {href[:80]}")
            if href.startswith(("mailto:", "tel:", "sms:", "javascript:")):
                if href.startswith("tel:") and not re.fullmatch(r"tel:\+?\d{6,15}", href):
                    self.add("warning", rel, f"tel: link should be E.164 digits: {href}")
                continue
            if self.is_internal(href):
                target, frag = self.resolve(href if not href.startswith("http") else urlparse(href).path or "/", rel)
                if target is None:
                    self.add("error", rel, f"broken internal link: {href}")
                elif frag:
                    trel = target.relative_to(self.dist).as_posix()
                    tp = self.pages.get(trel)
                    if tp is not None and frag not in tp.ids:
                        self.add("error", rel, f"link to missing anchor #{frag} on {trel}")

        for n in p.named:
            label = n["attrs"].get("aria-label") or n["attrs"].get("aria-labelledby") or n["attrs"].get("title")
            if not (n["text"].strip() or label):
                self.add(
                    "error",
                    rel,
                    f"<{n['tag']}> has no accessible name ({n['attrs'].get('href', n['attrs'].get('class', ''))[:60]})",
                )
            txt = n["text"].strip()
            if EMOJI_RE.search(txt):
                self.add("warning", rel, f"emoji used in a {n['tag']}: {txt[:40]!r}; use an SVG icon or none")
            if n["tag"] == "a" and txt.lower() in ("click here", "here", "read more", "learn more") and not label:
                self.add("warning", rel, f"vague link text {txt!r}; describe the destination")

        for h in p.headings:
            if EMOJI_RE.search(h):
                self.add("warning", rel, f"emoji in heading {h[:40]!r}")

        for inp in p.inputs:
            iid = inp.get("id")
            if not (inp["_in_label"] or (iid and iid in p.label_for) or inp.get("aria-label") or inp.get("aria-labelledby")):
                self.add("error", rel, f"form field without label: <{inp['_tag']} name={inp.get('name', '')!r}>")

        text = p.text
        if LOREM_RE.search(text):
            self.add("error", rel, "lorem ipsum text found")
        low = text.lower()
        for phrase in FILLER:
            if phrase in low:
                self.add("warning", rel, f"filler phrase {phrase!r}; write something specific")

        for s in p.scripts:
            src = s["attrs"].get("src", "")
            if src.startswith("http://"):
                self.add("error", rel, f"insecure script {src[:80]}")
            if s["attrs"].get("type") == "application/ld+json":
                self.check_jsonld(rel, s["text"])
        for lk in p.links:
            href = lk.get("href", "")
            if "fonts.googleapis.com" in href or "fonts.gstatic.com" in href:
                self.add("warning", rel, "Google Fonts CDN request; self-host fonts with Fontsource")
            if href.startswith("http://"):
                self.add("error", rel, f"insecure stylesheet/link {href[:80]}")

        for t in p.todos:
            self.todos.append({"where": rel, "todo": t})

        self.check_weight(rel, p)

    def check_jsonld(self, rel: str, raw: str) -> None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            self.add("error", rel, f"JSON-LD is not valid JSON: {e}")
            return
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if "@context" not in item and "@context" not in (data if isinstance(data, dict) else {}):
                self.add("error", rel, "JSON-LD block has no @context")
            if "@type" not in item and "@id" not in item:
                self.add("error", rel, "JSON-LD item has no @type")
            self.check_ld_item(rel, item)

    def check_ld_item(self, rel: str, item: dict) -> None:
        facts = self.business.get("facts") or {}
        for prop, kind in FORBIDDEN_LD.items():
            if prop in item and not facts.get(kind):
                self.add("error", rel, f"JSON-LD has {prop} but business.json facts has no {kind}: never fabricate {kind}")
        b = self.business
        if not b or "name" not in item or "address" not in item and "telephone" not in item:
            return
        if item.get("name") != b.get("name"):
            self.add("error", rel, f"NAP mismatch: JSON-LD name {item.get('name')!r} != business.json {b.get('name')!r}")
        if b.get("phone") and item.get("telephone") and item["telephone"] != b["phone"]:
            self.add("error", rel, f"NAP mismatch: telephone {item['telephone']!r} != {b['phone']!r}")
        addr = b.get("address") or {}
        la = item.get("address") or {}
        if addr.get("street") and isinstance(la, dict) and la.get("streetAddress") != addr["street"]:
            self.add("error", rel, f"NAP mismatch: streetAddress {la.get('streetAddress')!r} != {addr['street']!r}")
        if "openingHoursSpecification" in item:
            for spec in item["openingHoursSpecification"]:
                for key in ("opens", "closes"):
                    if not re.fullmatch(r"\d{2}:\d{2}(:\d{2})?", str(spec.get(key, ""))):
                        self.add("error", rel, f"openingHoursSpecification {key} {spec.get(key)!r} is not HH:MM")

    def check_weight(self, rel: str, p: Page) -> None:
        total = (self.dist / rel).stat().st_size
        refs = [lk.get("href", "") for lk in p.links if "stylesheet" in lk.get("rel", "")]
        refs += [s["attrs"].get("src", "") for s in p.scripts if s["attrs"].get("src")]
        refs += [i.get("src", "") for i in p.imgs if i.get("loading") != "lazy"]
        seen = set()
        for ref in refs:
            if not ref or ref in seen or ref.startswith(("http", "//", "data:")):
                continue
            seen.add(ref)
            f, _ = self.resolve(ref.split("?")[0], rel)
            if f is not None:
                total += f.stat().st_size
        if total > PAGE_WEIGHT_WARN:
            self.add("warning", rel, f"initial page weight about {total // 1024} KB; aim for under {PAGE_WEIGHT_WARN // 1024} KB")

    # -- multi-language
    @staticmethod
    def alternates(p: Page) -> dict[str, str]:
        out = {}
        for lk in p.links:
            if "alternate" in lk.get("rel", "").split() and lk.get("hreflang"):
                out[lk["hreflang"]] = lk.get("href", "")
        return out

    def page_for(self, href: str) -> str | None:
        """Relative dist path of the HTML page an absolute or root-relative URL points at."""
        target, _ = self.resolve(urlparse(href).path or "/", "index.html")
        return target.relative_to(self.dist).as_posix() if target else None

    def check_i18n(self) -> None:
        langs = list(self.business.get("languages") or [])
        if len(langs) < 2:
            self.add("error", "(site)", "pages carry hreflang alternates but business.json lists fewer than 2 languages")
            return
        default = langs[0]
        prefix = {code: code.lower() for code in langs}
        by_lang: dict[str, dict[str, str]] = {code: {} for code in langs}  # lang -> {path under prefix: rel file}
        for rel in self.pages:
            head, _, tail = rel.partition("/")
            for code, pre in prefix.items():
                if head == pre and tail:
                    by_lang[code][tail] = rel
        for code in langs:
            if not by_lang[code]:
                self.add("error", "(site)", f"no pages under /{prefix[code]}/ for language {code!r}")
        base_set = set(by_lang[default])
        for code in langs[1:]:
            missing, extra = base_set - set(by_lang[code]), set(by_lang[code]) - base_set
            if missing:
                self.add(
                    "error",
                    "(site)",
                    f"/{prefix[code]}/ lacks pages that exist in /{prefix[default]}/: {', '.join(sorted(missing))}",
                )
            if extra:
                self.add(
                    "error", "(site)", f"/{prefix[code]}/ has pages missing in /{prefix[default]}/: {', '.join(sorted(extra))}"
                )

        index = self.pages.get("index.html")
        want = f"/{prefix[default]}/"
        if index is None:
            self.add("error", "index.html", f"no redirect page at / (expected to send visitors to {want})")
        elif want not in index.meta.get("refresh", ""):
            self.add("error", "index.html", f"the page at / does not redirect to the default language {want}")

        for code in langs:
            for tail, rel in sorted(by_lang[code].items()):
                p = self.pages[rel]
                if (p.lang or "").lower() != code.lower():
                    self.add("error", rel, f"<html lang={p.lang!r}> but the page is in {code!r}")
                alts = self.alternates(p)
                for want_code in [*langs, "x-default"]:
                    if want_code not in alts:
                        self.add("error", rel, f"missing hreflang alternate for {want_code!r}")
                for hl, href in alts.items():
                    if not href.startswith("http"):
                        self.add("error", rel, f"hreflang {hl!r} href must be absolute, got {href!r}")
                    target = self.page_for(href)
                    if target is None:
                        self.add("error", rel, f"hreflang {hl!r} points at {href!r}, which is not a page in dist")
                        continue
                    expected = by_lang.get(hl, {}).get(tail) if hl != "x-default" else by_lang[default].get(tail)
                    if expected and target != expected:
                        self.add(
                            "error",
                            rel,
                            f"hreflang {hl!r} should point at the same page in that language ({expected}), not {target}",
                        )
                    back_href = self.alternates(self.pages[target]).get(code) if target in self.pages else None
                    if not back_href or self.page_for(back_href) != rel:
                        self.add(
                            "error",
                            rel,
                            f"hreflang {hl!r} target {target} does not link back to this page (alternates must be reciprocal)",
                        )
                canonical = next((lk.get("href", "") for lk in p.links if "canonical" in lk.get("rel", "").split()), "")
                if canonical and self.page_for(canonical) != rel:
                    self.add(
                        "error",
                        rel,
                        f"canonical {canonical!r} is not this page; each language needs a self-referencing canonical",
                    )
                if alts.get(code) and self.page_for(alts[code]) != rel:
                    self.add("error", rel, f"its own hreflang {code!r} entry does not point at itself")
                locales = [v for k, v in p.meta_list if k == "og:locale:alternate"]
                if not p.meta.get("og:locale"):
                    self.add("error", rel, "missing og:locale")
                if len(set(locales)) != len(langs) - 1:
                    self.add("error", rel, f"expected {len(langs) - 1} og:locale:alternate tags, found {len(set(locales))}")
                if not any(a.get("hreflang") and a.get("lang") for a in p.anchors):
                    self.add("error", rel, "no language switcher (links with hreflang and lang attributes)")

        sitemap = self.dist / "sitemap-0.xml"
        if sitemap.exists():
            xml = sitemap.read_text(encoding="utf-8")
            if "xhtml:link" not in xml or "hreflang=" not in xml:
                self.add("error", "sitemap-0.xml", "sitemap has no xhtml:link hreflang alternates")
        elif not (self.dist / "sitemap.xml").exists():
            self.add("warning", "(site)", "no sitemap-0.xml to check hreflang alternates in")

    def check_site(self) -> None:
        robots = self.dist / "robots.txt"
        if not robots.exists():
            self.add("error", "(site)", "robots.txt missing")
        elif "sitemap:" not in robots.read_text(encoding="utf-8").lower():
            self.add("warning", "(site)", "robots.txt has no Sitemap line")
        if not ((self.dist / "sitemap-index.xml").exists() or (self.dist / "sitemap.xml").exists()):
            self.add("error", "(site)", "no sitemap (sitemap-index.xml or sitemap.xml)")
        if not any((self.dist / f).exists() for f in ("favicon.svg", "favicon.ico")):
            self.add("error", "(site)", "no favicon.svg or favicon.ico")
        if not (self.dist / "404.html").exists():
            self.add("warning", "(site)", "no 404.html page")
        if not (self.dist / "og.png").exists() and not (self.dist / "og.jpg").exists():
            self.add("warning", "(site)", "no og.png social preview image")
        if not self.business.get("domain"):
            self.add("warning", "(site)", "domain unknown: canonical URLs and sitemap point at a placeholder")
        for css in self.dist.rglob("*.css"):
            content = css.read_text(encoding="utf-8", errors="replace").lower()
            for grad in re.findall(r"linear-gradient\([^;{}]*\)", content):
                if any(c in grad for c in SLOP_COLORS):
                    self.add(
                        "warning",
                        css.relative_to(self.dist).as_posix(),
                        "default purple/indigo gradient: off-brand slop, use the palette",
                    )
                    break

    def scan_src(self, src: Path) -> None:
        seen = set()
        for path in sorted(src.rglob("*")):
            if not path.is_file() or path.suffix not in (".astro", ".md", ".mdx", ".ts", ".js", ".json", ".css", ".html"):
                continue
            for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                m = re.search(r"TODO\(shingle\):?\s*(.*)$", line)
                if m:
                    key = (path, n)
                    if key not in seen:
                        seen.add(key)
                        self.todos.append(
                            {
                                "where": f"{path.relative_to(src.parent).as_posix()}:{n}",
                                "todo": re.sub(r"(?:\s*(?:-->|\*/|[}\"'`]))+\s*$", "", m.group(1)).strip(),
                            }
                        )

    def run(self, src: Path | None) -> dict:
        self.load()
        if not self.pages:
            self.add("error", "(site)", f"no HTML pages in {self.dist}; did the build run?")
        languages = self.business.get("languages") or []
        self.multilingual = len(languages) > 1 or any(self.alternates(p) for p in self.pages.values())
        for rel, p in self.pages.items():
            if self.multilingual and rel == "index.html" and "refresh" in p.meta:
                continue  # the language redirect page at "/" has no content of its own
            self.check_page(rel, p)
        self.check_site()
        if self.multilingual:
            self.check_i18n()
        if src and src.exists():
            self.scan_src(src)
        errors = [i for i in self.issues if i["severity"] == "error"]
        warnings = [i for i in self.issues if i["severity"] == "warning"]
        return {
            "ok": not errors,
            "pages": len(self.pages),
            "errors": errors,
            "warnings": warnings,
            "todos": self.todos,
        }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit a built Shingle site")
    ap.add_argument("dist", type=Path)
    ap.add_argument("--business", type=Path, help="business.json (default: ../business.json)")
    ap.add_argument("--src", type=Path, help="source folder to scan for TODO(shingle) (default: ../src)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args(argv)
    dist = args.dist.resolve()
    if not dist.is_dir():
        print(f"error: {dist} is not a directory", file=sys.stderr)
        return 2
    bpath = args.business or dist.parent / "business.json"
    business = None
    if bpath.exists():
        try:
            business = json.loads(bpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"error: {bpath}: {e}", file=sys.stderr)
            return 2
    src = args.src or dist.parent / "src"
    report = Audit(dist, business).run(src)
    failed = bool(report["errors"]) or (args.strict and bool(report["warnings"]))
    if args.json:
        report["ok"] = not failed
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if failed else 0
    print(
        f"{'PASS' if not failed else 'FAIL'}: {report['pages']} page(s), "
        f"{len(report['errors'])} error(s), {len(report['warnings'])} warning(s), {len(report['todos'])} TODO(s)"
    )
    for key in ("errors", "warnings"):
        if report[key]:
            print(f"\n{key}:")
            for i in report[key]:
                print(f"  [{i['page']}] {i['message']}")
    if report["todos"]:
        print("\nplaceholders to fill (TODO(shingle)):")
        for t in report["todos"]:
            print(f"  {t['where']}: {t['todo']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
