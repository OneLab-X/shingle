from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import image_fixtures as fx
from helpers import BUSINESS, SCRIPTS, build_good_dist, build_i18n_dist, jsonld, page, write_json

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


class I18nAuditTests(unittest.TestCase):
    def audit_defect(self, *tweaks, **kw):
        with tempfile.TemporaryDirectory() as d:
            dist = build_i18n_dist(Path(d), tweaks=frozenset(tweaks), **kw)
            return audit(dist)

    def test_good_bilingual_site_passes(self):
        report = self.audit_defect()
        self.assertEqual(report["errors"], [], messages(report))
        self.assertEqual(report["warnings"], [], messages(report, "warnings"))
        self.assertEqual(report["pages"], 6)  # redirect, 404, 2 languages x 2 pages

    def test_three_languages_pass(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_i18n_dist(Path(d), langs=("pt", "en", "es"))
            business = json.loads((Path(d) / "business.json").read_text())
            business["languages"] = ["pt", "en", "es"]
            report = audit_site.Audit(dist, business).run(None)
            self.assertEqual(report["errors"], [], messages(report))

    def test_each_defect_is_reported(self):
        cases = {
            "no_xdefault": "missing hreflang alternate for 'x-default'",
            "one_way": "does not link back",
            "wrong_target": "should point at the same page in that language",
            "wrong_lang": "<html lang='fr'> but the page is in 'en'",
            "other_canonical": "self-referencing canonical",
            "no_og_alternate": "og:locale:alternate",
            "no_switcher": "no language switcher",
            "missing_page": "lacks pages that exist in /pt/",
            "no_redirect": "no redirect page at /",
            "bad_redirect": "does not redirect to the default language /pt/",
            "no_sitemap_alternates": "xhtml:link hreflang alternates",
        }
        for tweak, expected in cases.items():
            with self.subTest(tweak):
                report = self.audit_defect(tweak)
                self.assertIn(expected, messages(report))
                self.assertFalse(report["ok"])

    def test_monolingual_site_skips_language_checks(self):
        with tempfile.TemporaryDirectory() as d:
            dist = build_good_dist(Path(d))
            self.assertNotIn("hreflang", messages(audit(dist)))


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


class ImageAuditTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.dist = build_good_dist(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def set_body(self, body: str):
        (self.dist / "index.html").write_text(page(f'<main id="main"><h1>Home</h1>{body}</main>'), encoding="utf-8")

    def img(self, src: str, alt: str) -> str:
        return f'<img src="{src}" alt="{alt}" width="10" height="10">'

    def warnings(self) -> str:
        return messages(audit(self.dist), "warnings")

    def test_alt_quality_warnings(self):
        for name in ("a.svg", "b.svg", "c.svg", "d.svg", "e.svg"):
            (self.dist / "images" / name).write_text("<svg xmlns='http://www.w3.org/2000/svg'/>")
        self.set_body(
            self.img("/images/a.svg", "dining-room.jpg")
            + self.img("/images/b.svg", "x" * 130)
            + self.img("/images/c.svg", "Photo of a table")
            + self.img("/images/d.svg", "Blue door")
            + self.img("/images/e.svg", "blue  DOOR")
        )
        w = self.warnings()
        for expected in ["file name", "130 characters", "image of", "share the alt text"]:
            self.assertIn(expected, w)

    def test_same_image_used_twice_is_fine_and_decorative_alt_is_not_flagged(self):
        self.set_body(self.img("/images/room.svg", "Dining room with blue tiles") * 2 + self.img("/images/room.svg", ""))
        self.assertEqual(audit(self.dist)["warnings"], [])

    def test_good_alt_adds_no_warnings(self):
        self.set_body(self.img("/images/room.svg", "Dining room with blue tiles"))
        self.assertEqual(audit(self.dist)["warnings"], [])

    def test_needs_alt_is_an_error(self):
        data = dict(BUSINESS, images=[{"src": "public/images/room.svg", "alt": "", "status": "needs-alt"}])
        write_json(self.root / "business.json", data)
        report = audit(self.dist)
        self.assertIn("still needs alt text", messages(report))

    def test_confirmed_images_pass(self):
        folder = self.root / "public" / "images"
        folder.mkdir(parents=True)
        (folder / "room.svg").write_text("<svg/>")
        write_json(
            self.root / "business.json", dict(BUSINESS, images=[{"src": "public/images/room.svg", "alt": "Room", "status": "ok"}])
        )
        report = audit(self.dist)
        self.assertEqual(report["errors"], [], messages(report))
        self.assertEqual(report["warnings"], [], messages(report, "warnings"))

    def test_missing_source_file_is_an_error(self):
        (self.root / "public" / "images").mkdir(parents=True)
        write_json(
            self.root / "business.json",
            dict(BUSINESS, images=[{"src": "public/images/ghost.jpg", "alt": "Ghost", "status": "ok"}]),
        )
        self.assertIn("does not exist", messages(audit(self.dist)))

    def test_unused_files_in_public_images_warn(self):
        folder = self.root / "public" / "images"
        folder.mkdir(parents=True)
        (folder / "room.svg").write_text("<svg/>")
        (folder / "spare.jpg").write_bytes(fx.make_jpeg())
        write_json(
            self.root / "business.json",
            dict(BUSINESS, images=[{"src": "public/images/spare.jpg", "alt": "Spare", "subject": "Kitchen", "status": "ok"}]),
        )
        w = self.warnings()
        self.assertIn("spare.jpg is not used on any page", w)
        self.assertIn("Kitchen", w)
        self.assertNotIn("room.svg", w)

    def test_optimised_photo_counts_as_used(self):
        folder = self.root / "public" / "images"
        folder.mkdir(parents=True)
        (folder / "spare.jpg").write_bytes(fx.make_jpeg())
        (self.dist / "_astro").mkdir(exist_ok=True)
        (self.dist / "_astro" / "spare.AbC123_Z1x.webp").write_bytes(b"RIFF")
        self.set_body('<img src="/_astro/spare.AbC123_Z1x.webp" alt="A spare room" width="10" height="10">')
        self.assertNotIn("spare.jpg", self.warnings())

    def test_gps_surviving_in_dist_is_an_error(self):
        (self.dist / "images" / "leak.jpg").write_bytes(fx.make_jpeg(exif=fx.exif_block(1)))
        (self.dist / "images" / "clean.JPG").write_bytes(fx.make_jpeg(exif=fx.exif_block(1, gps=False)))
        errs = messages(audit(self.dist))
        self.assertIn("images/leak.jpg", errs)
        self.assertIn("GPS", errs)
        self.assertNotIn("clean.JPG", errs)

    def test_gps_in_xmp_is_also_caught(self):
        (self.dist / "_astro" / "x.jpg").write_bytes(fx.make_jpeg(xmp=True))
        self.assertIn("x.jpg", messages(audit(self.dist)))

    def test_large_original_not_optimised_warns(self):
        (self.dist / "images" / "huge.jpg").write_bytes(fx.make_jpeg(trailer=b"\0" * 600_000))
        self.set_body(self.img("/images/huge.jpg", "A huge photo of nothing much"))
        self.assertIn("served as it is", self.warnings())
        self.set_body(self.img("/images/huge.jpg", "A huge photo of nothing much").replace("/images/", "/_astro/"))
        (self.dist / "_astro" / "huge.jpg").write_bytes(fx.make_jpeg(trailer=b"\0" * 600_000))
        self.assertNotIn("served as it is", self.warnings())


if __name__ == "__main__":
    unittest.main()
