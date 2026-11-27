from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from helpers import BUSINESS, SCRIPTS, write_json

import sync

REFS = SCRIPTS.parent / "references"


def make_site(root: Path, business=None) -> Path:
    site = root / "site"
    (site / "src" / "pages").mkdir(parents=True)
    (site / "src" / "pages" / "index.astro").write_text("<h1>Home</h1>\n", encoding="utf-8")
    (site / "src" / "components").mkdir()
    (site / "src" / "components" / "Hero.astro").write_text("<section>Hero</section>\n", encoding="utf-8")
    (site / "public" / "images").mkdir(parents=True)
    (site / "public" / "images" / "owner.jpg").write_bytes(b"jpg")
    write_json(site / "package.json", {"name": "site", "dependencies": {"astro": "^7.4.0"}})
    write_json(site / "business.json", business or BUSINESS)
    return site


def run_sync(site: Path, write=True):
    return sync.sync(site, REFS / "palettes.json", REFS / "directions.json", write=write)


class DataTests(unittest.TestCase):
    def test_site_data(self):
        b, _ = sync.normalize(copy.deepcopy(BUSINESS))
        d = sync.build_site_data(b)
        self.assertEqual(d["business"]["url"], "https://marigoldkitchen.pt/")
        self.assertFalse(d["business"]["url_is_placeholder"])
        self.assertEqual(d["contact"]["tel"]["href"], "tel:+351213000000")
        self.assertEqual(d["business"]["address_lines"], ["Rua da Rosa 112", "1200-389 Lisboa"])
        self.assertIn("output=embed", d["maps"]["embed"])
        self.assertTrue(d["badge"])
        self.assertEqual(d["hours"]["format"], "24h")
        labels = [(g["label"], g["text"]) for g in d["hours"]["groups"]]
        self.assertEqual(labels[0], ("Mon", "Closed"))
        self.assertEqual(labels[1], ("Tue", "12:00–15:00, 19:00–23:00"))
        self.assertEqual(labels[2], ("Wed–Thu", "Hours not set"))

    def test_twelve_hour_country(self):
        h = sync.build_hours({"mon": [["09:00", "17:30"], ["12:00", "00:00"]]}, True, None)
        self.assertEqual(h["days"][0]["ranges"][0]["text"], "9 am–5:30 pm")
        self.assertEqual(h["days"][0]["ranges"][1]["text"], "12 pm–12 am")

    def test_jsonld_never_invents(self):
        b, _ = sync.normalize(copy.deepcopy(BUSINESS))
        ld = sync.build_jsonld(b, "https://marigoldkitchen.pt/")
        self.assertEqual(ld["@type"], "Restaurant")
        self.assertEqual(ld["servesCuisine"], ["Goan"])
        self.assertEqual(ld["priceRange"], "€€")
        self.assertEqual(ld["hasMenu"], "https://marigoldkitchen.pt/#menu")
        for forbidden in ("aggregateRating", "review", "award", "foundingDate"):
            self.assertNotIn(forbidden, ld)
        spec = ld["openingHoursSpecification"]
        self.assertEqual(
            spec[0], {"@type": "OpeningHoursSpecification", "dayOfWeek": ["Tuesday"], "opens": "12:00", "closes": "15:00"}
        )
        self.assertTrue(any(s["closes"] == "00:30" for s in spec))

    def test_placeholder_url_and_badge_off(self):
        b = copy.deepcopy(BUSINESS)
        del b["domain"]
        b["decisions"]["badge"] = False
        d = sync.build_site_data(sync.normalize(b)[0])
        self.assertEqual(d["business"]["url"], sync.PLACEHOLDER_URL)
        self.assertTrue(d["business"]["url_is_placeholder"])
        self.assertFalse(d["badge"])

    def test_timezone_and_theme(self):
        palettes = json.loads((REFS / "palettes.json").read_text())
        pal = next(p for p in palettes["palettes"] if p["id"] == "saffron-ink")
        b, _ = sync.normalize(copy.deepcopy(BUSINESS))
        d = sync.build_site_data(b, pal)
        self.assertEqual(d["hours"]["timezone"], "Europe/Lisbon")  # inferred from PT
        self.assertTrue(d["theme"]["dark"])
        self.assertEqual(d["theme"]["colors"]["light"]["primary"], pal["light"]["primary"])
        us = sync.build_site_data({"name": "X", "category": "cafe", "address": {"country": "US"}})
        self.assertIsNone(us["hours"]["timezone"])  # multi-zone country: must be explicit
        us = sync.build_site_data({"name": "X", "category": "cafe", "timezone": "America/Denver", "address": {"country": "US"}})
        self.assertEqual(us["hours"]["timezone"], "America/Denver")

    def test_photographer_additional_type(self):
        b = {"name": "Lens", "category": "photographer"}
        self.assertIn("additionalType", sync.build_jsonld(b, "https://x.com/"))


class ThemeTests(unittest.TestCase):
    def test_theme_css(self):
        palettes = json.loads((REFS / "palettes.json").read_text())
        directions = json.loads((REFS / "directions.json").read_text())
        pal = next(p for p in palettes["palettes"] if p["id"] == "saffron-ink")
        css = sync.build_theme_css(pal, "broadsheet", directions["directions"]["broadsheet"])
        self.assertIn("--sh-background: #FBF6EC;", css)
        self.assertIn("prefers-color-scheme: dark", css)
        self.assertIn(':root[data-theme="dark"]', css)
        self.assertIn('"Fraunces Variable"', css)
        no_dark = next(p for p in palettes["palettes"] if not p["dark"])
        self.assertNotIn("prefers-color-scheme", sync.build_theme_css(no_dark, "poster", directions["directions"]["poster"]))

    def test_every_direction_has_tokens(self):
        directions = json.loads((REFS / "directions.json").read_text())["directions"]
        self.assertEqual(len(directions), 8)
        for name, d in directions.items():
            with self.subTest(name):
                for role in ("display", "body"):
                    self.assertTrue(d["fonts"][role]["imports"])
                    self.assertTrue(d["fonts"][role]["package"].startswith("@fontsource"))
                self.assertIn("h1", d["tokens"])


class SyncTests(unittest.TestCase):
    def test_full_cycle_preserves_edits(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d))
            out = run_sync(site)
            self.assertIn("src/data/site.json", out["written"])
            self.assertIn("public/CNAME", out["written"])
            self.assertEqual((site / "public/CNAME").read_text(), "marigoldkitchen.pt\n")
            pkg = json.loads((site / "package.json").read_text())
            self.assertIn("@fontsource-variable/fraunces", pkg["dependencies"])

            rec = sync.record(site, None)
            self.assertEqual(sorted(rec["recorded"]), ["src/components/Hero.astro", "src/pages/index.astro"])
            self.assertNotIn("public/images/owner.jpg", rec["recorded"])

            # user edits one file; business.json changes
            (site / "src/pages/index.astro").write_text("<h1>Home, edited</h1>\n")
            b = json.loads((site / "business.json").read_text())
            b["phone"] = "+351210000001"
            b["decisions"]["design"]["direction"] = "poster"
            del b["domain"]
            write_json(site / "business.json", b)

            out = run_sync(site)
            self.assertEqual(out["status"]["edited"], ["src/pages/index.astro"])
            self.assertEqual(out["status"]["clean"], ["src/components/Hero.astro"])
            self.assertEqual((site / "src/pages/index.astro").read_text(), "<h1>Home, edited</h1>\n")
            data = json.loads((site / "src/data/site.json").read_text())
            self.assertEqual(data["business"]["phone"], "+351210000001")
            self.assertFalse((site / "public/CNAME").exists())
            pkg = json.loads((site / "package.json").read_text())
            self.assertNotIn("@fontsource-variable/fraunces", pkg["dependencies"])
            self.assertIn("@fontsource/anton", pkg["dependencies"])
            self.assertIn("astro", pkg["dependencies"])

            # second sync with no changes writes nothing
            self.assertEqual(run_sync(site)["written"], [])

            # status mode writes nothing even if data changed
            b["phone"] = "+351210000002"
            write_json(site / "business.json", b)
            run_sync(site, write=False)
            self.assertIn("+351210000001", (site / "src/data/site.json").read_text())

            # re-record a single rewritten file
            sync.record(site, ["src/pages/index.astro"])
            self.assertEqual(run_sync(site)["status"]["edited"], [])

    def test_missing_tracked_file(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d))
            run_sync(site)
            sync.record(site, None)
            (site / "src/components/Hero.astro").unlink()
            self.assertEqual(run_sync(site, write=False)["status"]["missing"], ["src/components/Hero.astro"])

    def test_invalid_business_stops(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), {"name": "X", "category": "nope"})
            with self.assertRaises(SystemExit):
                run_sync(site)
            self.assertFalse((site / "src/data/site.json").exists())

    def test_unknown_palette(self):
        with tempfile.TemporaryDirectory() as d:
            b = copy.deepcopy(BUSINESS)
            b["decisions"]["design"]["palette"] = "does-not-exist"
            with self.assertRaises(SystemExit):
                run_sync(make_site(Path(d), b))


if __name__ == "__main__":
    unittest.main()
