from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, build_good_dist, jsonld, page

import audit_site


def audit(dist: Path, src: Path | None = None):
    business = json.loads((dist.parent / "business.json").read_text())
    return audit_site.Audit(dist, business).run(src)


def messages(report, severity="errors"):
    return "\n".join(i["message"] for i in report[severity])


class GoodSiteTests(unittest.TestCase):
    def test_good_site_passes(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            report = audit(dist)
            self.assertEqual(report["errors"], [], messages(report))
            self.assertEqual(report["warnings"], [], messages(report, "warnings"))
            self.assertEqual(report["pages"], 3)
            self.assertEqual(report["todos"], [{"where": "index.html", "todo": "Add 3 photos of signature dishes"}])

    def test_src_todos_have_file_and_line(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            src = Path(d) / "src" / "components"
            src.mkdir(parents=True)
            (src / "Menu.astro").write_text("<section>\n<!-- TODO(shingle): add real menu prices -->\n</section>\n")
            report = audit(dist, Path(d) / "src")
            self.assertEqual(len(report["todos"]), 2)  # rendered marker on the page + source comment
            src_todo = report["todos"][-1]
            self.assertEqual(src_todo["where"], "src/components/Menu.astro:2")
            self.assertEqual(src_todo["todo"], "add real menu prices")


class BadSiteTests(unittest.TestCase):
    def test_catches_problems(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            body = """
<main><h1>One</h1><h1>Two</h1>
<img src="/images/missing.jpg">
<img src="https://images.example.com/stock.jpg" alt="Stock" width="10" height="10">
<a href="/nowhere/">Broken</a>
<a href="/about/#nope">Missing anchor</a>
<a href="#">Dead</a>
<a href="/"></a>
<button></button>
<input name="email">
<iframe src="https://maps.example.com"></iframe>
<h2>⭐ Our favourites</h2>
<p>Lorem ipsum dolor sit amet. Welcome to our website!</p>
<p id="x"></p><p id="x"></p>
</main>"""
            ld = jsonld(
                name="Marigold Kitchn",
                telephone="+351000000000",
                aggregateRating={"@type": "AggregateRating", "ratingValue": 4.9},
            )
            (dist / "bad.html").write_text(
                page(body, ld=ld, head_extra='<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">')
            )
            (dist / "_astro" / "slop.css").write_text(".hero{background:linear-gradient(90deg,#8b5cf6,#ec4899)}")
            report = audit(dist)
            errs = messages(report)
            for expected in [
                "2 <h1>",
                "without alt",
                "image not found",
                "hotlinked",
                "broken internal link: /nowhere/",
                "missing anchor #nope",
                "goes nowhere",
                "no accessible name",
                "form field without label",
                "<iframe> without title",
                "lorem ipsum",
                "duplicate ids",
                "aggregateRating",
                "NAP mismatch: JSON-LD name",
                "NAP mismatch: telephone",
            ]:
                with self.subTest(expected):
                    self.assertIn(expected, errs + messages(report, "warnings"))
            warns = messages(report, "warnings")
            for expected in ["emoji in heading", "filler phrase", "Google Fonts", "purple", "width/height"]:
                with self.subTest(expected):
                    self.assertIn(expected, warns)

    def test_missing_site_files(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            for f in ("robots.txt", "sitemap-index.xml", "favicon.svg", "404.html"):
                (dist / f).unlink()
            report = audit(dist)
            errs = messages(report)
            self.assertIn("robots.txt missing", errs)
            self.assertIn("no sitemap", errs)
            self.assertIn("favicon", errs)
            self.assertIn("404", messages(report, "warnings"))

    def test_invalid_jsonld(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            (dist / "x.html").write_text(page("<h1>X</h1>", ld="{not json"))
            self.assertIn("not valid JSON", messages(audit(dist)))

    def test_head_requirements(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            (dist / "bare.html").write_text("<html><head></head><body><h1>x</h1></body></html>")
            errs = messages(audit(dist))
            for expected in ["no lang", "missing <title>", "missing meta description", "viewport", "canonical", "og:image"]:
                self.assertIn(expected, errs)


class CliTests(unittest.TestCase):
    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            run = lambda *a: subprocess.run([sys.executable, str(SCRIPTS / "audit_site.py"), *a], capture_output=True, text=True)
            res = run(str(dist))
            self.assertEqual(res.returncode, 0, res.stdout)
            self.assertIn("PASS", res.stdout)
            (dist / "index.html").write_text(page("<h1>x</h1><img src='/a.png'>"))
            res = run(str(dist), "--json")
            self.assertEqual(res.returncode, 1)
            self.assertFalse(json.loads(res.stdout)["ok"])
            self.assertEqual(run(str(Path(d) / "nope")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
