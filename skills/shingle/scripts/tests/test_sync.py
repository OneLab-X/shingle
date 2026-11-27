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


BILINGUAL = {
    "name": "Oficina do Azulejo",
    "category": "ecommerce-boutique",
    "domain": "oficina.example",
    "address": {"street": "Rua do Século 12", "locality": "Lisboa", "postal_code": "1200-433", "country": "PT"},
    "phone": "+351213000000",
    "languages": ["pt", "en"],
    "tagline": "Cerâmica feita à mão em Lisboa",
    "description": "Loja de cerâmica e azulejos pintados à mão.",
    "hours": {"mon": [["10:00", "19:00"]]},
    "facts": {"products": [{"name": "Azulejo", "text": "Pintado à mão", "price": "€18"}]},
    "decisions": {"design": {"direction": "handmade", "palette": "terracotta-sun"}},
    "translations": {
        "en": {
            "review": "draft",
            "tagline": "Handmade ceramics in Lisbon",
            "description": "Shop selling hand-painted ceramics and tiles.",
            "facts": {"products": [{"name": "Tile", "text": "Hand painted", "price": "€18"}]},
        }
    },
}


class I18nDataTests(unittest.TestCase):
    def test_og_locale(self):
        self.assertEqual(sync.og_locale("pt", "PT"), "pt_PT")
        self.assertEqual(sync.og_locale("pt", "BR"), "pt_BR")
        self.assertEqual(sync.og_locale("en", "PT"), "en_US")  # English is not Portugal's language: default region
        self.assertEqual(sync.og_locale("en", "GB"), "en_GB")
        self.assertEqual(sync.og_locale("pt-BR", "PT"), "pt_BR")  # explicit region wins
        self.assertEqual(sync.og_locale("xx", None), "xx_XX")

    def test_build_i18n(self):
        b, _ = sync.normalize(copy.deepcopy(BILINGUAL))
        i18n = sync.build_i18n(b)
        self.assertTrue(i18n["enabled"])
        self.assertEqual(i18n["default"], "pt")
        self.assertEqual([loc["path"] for loc in i18n["locales"]], ["pt", "en"])
        self.assertEqual([loc["label"] for loc in i18n["locales"]], ["Português", "English"])
        self.assertEqual({loc["dir"] for loc in i18n["locales"]}, {"ltr"})
        mono = sync.build_i18n({"name": "X", "languages": ["en"], "address": {"country": "US"}})
        self.assertFalse(mono["enabled"])
        self.assertEqual(sync.build_i18n({"name": "X"})["default"], "en")

    def test_merge_translation(self):
        base = {"a": "x", "n": {"p": 1, "q": [1, 2]}, "l": [1, 2, 3]}
        merged = sync.merge_translation(base, {"a": "y", "n": {"q": [9]}, "l": [7]})
        self.assertEqual(merged, {"a": "y", "n": {"p": 1, "q": [9]}, "l": [7]})
        self.assertEqual(base["a"], "x")  # input untouched

    def test_translated_business(self):
        b, _ = sync.normalize(copy.deepcopy(BILINGUAL))
        en = sync.translated_business(b, "en")
        self.assertEqual(en["tagline"], "Handmade ceramics in Lisbon")
        self.assertEqual(en["facts"]["products"][0]["price"], "€18")
        self.assertEqual(en["phone"], "+351213000000")
        self.assertNotIn("translations", en)
        self.assertNotIn("review", en)

    def test_untranslated_paths(self):
        b, _ = sync.normalize(copy.deepcopy(BILINGUAL))
        base = {k: v for k, v in b.items() if k != "translations"}
        self.assertEqual(sync.untranslated_paths(base, b["translations"]["en"]), [])
        partial = {"tagline": "x"}
        self.assertEqual(sorted(sync.untranslated_paths(base, partial)), ["description", "facts.products[0].text"])

    def test_page_data_per_language(self):
        b, _ = sync.normalize(copy.deepcopy(BILINGUAL))
        i18n = sync.build_i18n(b)
        pt = sync.build_site_data(b, None, "pt", i18n)
        en = sync.build_site_data(sync.translated_business(b, "en"), None, "en", i18n)
        self.assertEqual((pt["lang"], pt["seo"]["lang"], pt["seo"]["locale"]), ("pt", "pt", "pt_PT"))
        self.assertEqual((en["lang"], en["seo"]["lang"], en["seo"]["locale"]), ("en", "en", "en_US"))
        self.assertEqual(en["business"]["tagline"], "Handmade ceramics in Lisbon")
        self.assertEqual(en["seo"]["title"], "Oficina do Azulejo · Handmade ceramics in Lisbon")
        self.assertTrue(pt["seo"]["title"].startswith("Oficina do Azulejo · "))
        self.assertEqual(pt["jsonld"]["url"], "https://oficina.example/pt/")
        self.assertEqual(en["jsonld"]["url"], "https://oficina.example/en/")
        self.assertEqual(en["jsonld"]["@id"], pt["jsonld"]["@id"])
        self.assertEqual(en["jsonld"]["knowsLanguage"], ["pt", "en"])
        self.assertEqual(en["jsonld"]["description"], "Shop selling hand-painted ceramics and tiles.")

    def test_monolingual_has_no_language_prefix(self):
        b, _ = sync.normalize(copy.deepcopy(BUSINESS))
        d = sync.build_site_data(b)
        self.assertFalse(d["i18n"]["enabled"])
        self.assertEqual(d["jsonld"]["url"], "https://marigoldkitchen.pt/")
        self.assertNotIn("knowsLanguage", d["jsonld"])

    def test_hours_groups_have_day_keys(self):
        h = sync.build_hours({"mon": [["09:00", "17:00"]], "tue": [["09:00", "17:00"]], "wed": []}, False, None)
        self.assertEqual(h["groups"][0]["keys"], ["mon", "tue"])
        self.assertEqual(h["groups"][0]["label"], "Mon–Tue")

    def test_ui_strings_fall_back_to_english(self):
        ui = sync.load_ui("xx")
        self.assertEqual(ui["skip.content"], "Skip to content")
        self.assertIsNone(ui["_native_name"])
        self.assertEqual(sync.load_ui("pt-BR")["skip.content"], "Saltar para o conteúdo")


class I18nSyncTests(unittest.TestCase):
    def test_bilingual_cycle(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), copy.deepcopy(BILINGUAL))
            out = run_sync(site)
            for rel in ("src/data/site.json", "src/data/site.en.json", "src/data/ui.json"):
                self.assertIn(rel, out["written"])
            self.assertEqual(out["i18n"]["languages"], ["pt", "en"])
            self.assertEqual(out["i18n"]["draft"], ["en"])
            self.assertNotIn("en", out["i18n"]["untranslated"])
            en = json.loads((site / "src/data/site.en.json").read_text())
            self.assertEqual(en["review"], "draft")
            self.assertEqual(en["lang"], "en")
            ui = json.loads((site / "src/data/ui.json").read_text())
            self.assertEqual(sorted(ui), ["en", "pt"])
            self.assertEqual(ui["pt"]["status.closed_today"], "Fechado · abre hoje às {time}")
            self.assertNotIn("_native_name", ui["pt"])
            self.assertEqual(json.loads((site / "src/data/site.json").read_text())["lang"], "pt")

            # marking the translation reviewed clears the draft flag
            b = json.loads((site / "business.json").read_text())
            b["translations"]["en"]["review"] = "reviewed"
            write_json(site / "business.json", b)
            out = run_sync(site)
            self.assertEqual(out["i18n"]["draft"], [])
            self.assertEqual(json.loads((site / "src/data/site.en.json").read_text())["review"], "reviewed")

            # going back to one language removes the stale file
            b["languages"] = ["pt"]
            write_json(site / "business.json", b)
            out = run_sync(site)
            self.assertIn("src/data/site.en.json", out["removed"])
            self.assertFalse((site / "src/data/site.en.json").exists())
            self.assertFalse(json.loads((site / "src/data/site.json").read_text())["i18n"]["enabled"])

    def test_data_files_are_not_tracked(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), copy.deepcopy(BILINGUAL))
            run_sync(site)
            self.assertFalse(any(r.startswith("src/data/") for r in sync.candidate_files(site)))

    def test_invalid_overlay_stops_sync(self):
        with tempfile.TemporaryDirectory() as d:
            b = copy.deepcopy(BILINGUAL)
            b["translations"]["en"]["phone"] = "+1"
            with self.assertRaises(SystemExit):
                run_sync(make_site(Path(d), b))


class InitI18nTests(unittest.TestCase):
    TEMPLATE = sync.TEMPLATE_DIR

    def bilingual_site(self, root: Path) -> Path:
        return make_site(root, copy.deepcopy(BILINGUAL))

    def test_requires_two_languages(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), copy.deepcopy(BUSINESS))
            with self.assertRaises(SystemExit):
                sync.init_i18n(site)

    def test_pristine_pages_are_replaced(self):
        with tempfile.TemporaryDirectory() as d:
            site = self.bilingual_site(Path(d))
            (site / "src/pages/index.astro").write_bytes((self.TEMPLATE / "src/pages/index.astro").read_bytes())
            (site / "src/pages/404.astro").write_bytes((self.TEMPLATE / "src/pages/404.astro").read_bytes())
            out = sync.init_i18n(site)
            self.assertIn("src/pages/[lang]/index.astro", out["created"])
            self.assertIn("src/pages/index.astro", out["replaced"])
            self.assertIn("src/pages/404.astro", out["replaced"])
            self.assertFalse((site / "src/pages/index.astro").exists())
            self.assertIn("getStaticPaths", (site / "src/pages/[lang]/index.astro").read_text())
            self.assertIn("page.not_found", (site / "src/pages/404.astro").read_text())

    def test_edited_pages_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            site = self.bilingual_site(Path(d))  # make_site writes its own index.astro: not the template's
            (site / "src/pages/404.astro").write_text("<h1>My own 404</h1>\n")
            out = sync.init_i18n(site)
            self.assertEqual((site / "src/pages/index.astro").read_text(), "<h1>Home</h1>\n")
            self.assertEqual((site / "src/pages/404.astro").read_text(), "<h1>My own 404</h1>\n")
            self.assertTrue(any("edited by hand" in w for w in out["warnings"]))

    def test_second_run_keeps_existing_language_pages(self):
        with tempfile.TemporaryDirectory() as d:
            site = self.bilingual_site(Path(d))
            sync.init_i18n(site)
            page = site / "src/pages/[lang]/index.astro"
            page.write_text("<h1>mine</h1>\n")
            out = sync.init_i18n(site)
            self.assertEqual(page.read_text(), "<h1>mine</h1>\n")
            self.assertIn("src/pages/[lang]/index.astro", out["kept"])

    def test_template_overlay_files_exist(self):
        for src_rel, _, _ in sync.I18N_OVERLAY:
            self.assertTrue((self.TEMPLATE / src_rel).is_file(), src_rel)


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
