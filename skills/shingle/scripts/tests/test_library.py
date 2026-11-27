"""validate_library.py passes on the shipped palettes and directions, and each rule has a negative test.

Nothing here touches the network: --check-fonts is exercised with a fake opener.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path

from helpers import SCRIPTS, write_json

import validate_library as vl

LIB = vl.load_library()


def fresh() -> dict:
    """A deep copy of the shipped library that a test may break."""
    return copy.deepcopy(LIB)


def errors_of(results: dict[str, list[str]]) -> list[str]:
    return [e for errs in results.values() for e in errs]


class ShippedLibraryTests(unittest.TestCase):
    def test_palettes_pass(self):
        self.assertEqual(errors_of(vl.check_palettes(LIB)), [])

    def test_directions_pass(self):
        self.assertEqual(errors_of(vl.check_directions(LIB)), [])

    def test_cli_passes(self):
        res = subprocess.run([sys.executable, str(SCRIPTS / "validate_library.py")], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_moods_documented(self):
        used = {m for p in LIB["palettes"]["palettes"] for m in p["moods"]}
        self.assertLessEqual(used, LIB["moods"])

    def test_library_grew(self):
        self.assertGreaterEqual(len(LIB["palettes"]["palettes"]), 30)
        self.assertGreaterEqual(len(LIB["directions"]["directions"]), 10)

    def test_docs_table_matches_json(self):
        self.assertEqual(vl.table_ids(LIB["docs"]), set(LIB["directions"]["directions"]))


class PaletteRuleTests(unittest.TestCase):
    def palette(self) -> dict:
        return copy.deepcopy(next(p for p in LIB["palettes"]["palettes"] if p["id"] == "harbor-blue"))

    def check(self, p: dict, **kw) -> list[str]:
        return vl.check_palette(p, LIB, **kw)

    def assertRule(self, p: dict, needle: str, **kw):
        errs = self.check(p, **kw)
        self.assertTrue(any(needle in e for e in errs), f"expected {needle!r} in {errs}")

    def test_baseline_ok(self):
        self.assertEqual(self.check(self.palette()), [])

    def test_missing_role(self):
        p = self.palette()
        del p["light"]["border"]
        self.assertRule(p, "missing role 'border'")

    def test_missing_role_in_dark(self):
        p = self.palette()
        del p["dark"]["on_accent"]
        self.assertRule(p, "dark: missing role 'on_accent'")

    def test_bad_hex(self):
        p = self.palette()
        p["light"]["primary"] = "#12G456"
        self.assertRule(p, "not a #RRGGBB hex color")

    def test_short_hex_rejected(self):
        p = self.palette()
        p["light"]["primary"] = "#FFF"
        self.assertRule(p, "not a #RRGGBB hex color")

    def test_unknown_role(self):
        p = self.palette()
        p["light"]["tertiary"] = "#123456"
        self.assertRule(p, "unknown role 'tertiary'")

    def test_duplicate_id(self):
        self.assertRule(self.palette(), "duplicate palette id", seen_ids={"harbor-blue"})

    def test_duplicate_id_in_library(self):
        lib = fresh()
        lib["palettes"]["palettes"].append(copy.deepcopy(lib["palettes"]["palettes"][0]))
        self.assertTrue(any("duplicate palette id" in e for e in errors_of(vl.check_palettes(lib))))

    def test_id_must_be_kebab(self):
        p = self.palette()
        p["id"] = "Harbor_Blue"
        self.assertRule(p, "kebab-case")

    def test_contrast_failure(self):
        p = self.palette()
        p["light"]["text"] = "#BBBBBB"
        self.assertRule(p, "text/background")

    def test_contrast_failure_in_dark(self):
        p = self.palette()
        p["dark"]["muted"] = "#222222"
        self.assertRule(p, "dark muted/background")

    def test_unknown_category(self):
        p = self.palette()
        p["categories"] = ["dental-clinic", "spaceport"]
        self.assertRule(p, "unknown category 'spaceport'")

    def test_empty_categories(self):
        p = self.palette()
        p["categories"] = []
        self.assertRule(p, "categories must be")

    def test_unknown_mood(self):
        p = self.palette()
        p["moods"] = ["warm", "spicy"]
        self.assertRule(p, "unknown mood 'spicy'")

    def test_missing_name_and_rationale(self):
        p = self.palette()
        del p["name"]
        p["rationale"] = " "
        errs = self.check(p)
        self.assertTrue(any("name is required" in e for e in errs))
        self.assertTrue(any("rationale is required" in e for e in errs))

    def test_light_only_is_fine(self):
        p = self.palette()
        del p["dark"]
        self.assertEqual(self.check(p), [])

    def test_null_dark_is_fine(self):
        p = self.palette()
        p["dark"] = None
        self.assertEqual(self.check(p), [])

    def test_category_needs_two_palettes(self):
        lib = fresh()
        lib["categories"].add("florist")
        lib["palettes"]["palettes"][0]["categories"].append("florist")
        self.assertTrue(any("'florist'" in e for e in vl.check_palettes(lib)["palette coverage"]))


class DirectionRuleTests(unittest.TestCase):
    def direction(self) -> dict:
        return copy.deepcopy(LIB["directions"]["directions"]["swiss-grid"])

    def check(self, d: dict, did: str = "swiss-grid", **kw) -> list[str]:
        return vl.check_direction(did, d, LIB, **kw)

    def assertRule(self, d: dict, needle: str, **kw):
        errs = self.check(d, **kw)
        self.assertTrue(any(needle in e for e in errs), f"expected {needle!r} in {errs}")

    def test_baseline_ok(self):
        self.assertEqual(self.check(self.direction()), [])

    def test_missing_token(self):
        d = self.direction()
        del d["tokens"]["radius"]
        self.assertRule(d, "tokens.radius is missing")

    def test_unknown_token(self):
        d = self.direction()
        d["tokens"]["glow"] = "1px"
        self.assertRule(d, "unknown token 'glow'")

    def test_bad_heading_case(self):
        d = self.direction()
        d["tokens"]["heading-case"] = "shouting"
        self.assertRule(d, "heading-case must be")

    def test_missing_font_role(self):
        d = self.direction()
        del d["fonts"]["body"]
        self.assertRule(d, "fonts.body is missing")

    def test_font_missing_each_key(self):
        for key in ("family", "package", "imports", "fallback"):
            with self.subTest(key):
                d = self.direction()
                del d["fonts"]["display"][key]
                self.assertRule(d, f"fonts.display.{key} is missing")

    def test_package_must_be_fontsource(self):
        d = self.direction()
        d["fonts"]["display"]["package"] = "some-font"
        d["fonts"]["display"]["imports"] = ["some-font"]
        self.assertRule(d, "must be a @fontsource")

    def test_imports_must_match_package(self):
        d = self.direction()
        d["fonts"]["body"]["imports"] = ["@fontsource-variable/other-font"]
        self.assertRule(d, "must all start with the package name")

    def test_id_must_be_kebab(self):
        self.assertRule(self.direction(), "kebab-case", did="Swiss Grid", docs=False)

    def test_not_in_table(self):
        self.assertRule(self.direction(), "missing from the table", did="new-look")

    def test_no_section(self):
        lib = fresh()
        lib["docs"] = lib["docs"].replace("## swiss-grid: Swiss Grid", "## swiss: Swiss Grid")
        errs = vl.check_direction("swiss-grid", self.direction(), lib)
        self.assertTrue(any("no '## swiss-grid: <Name>' section" in e for e in errs), errs)

    def test_section_without_signature_element(self):
        lib = fresh()
        start = lib["docs"].index("## swiss-grid:")
        end = lib["docs"].index("## handmade:")
        lib["docs"] = (
            lib["docs"][:start] + lib["docs"][start:end].replace("**Signature element:**", "**Detail:**") + lib["docs"][end:]
        )
        errs = vl.check_direction("swiss-grid", self.direction(), lib)
        self.assertTrue(any("Signature element" in e for e in errs), errs)

    def test_table_row_without_direction(self):
        lib = fresh()
        lib["docs"] = lib["docs"].replace("| `wayfinder` |", "| `ghost` |", 1)
        self.assertTrue(any("'ghost'" in e for e in vl.check_directions(lib)["direction table"]))

    def test_every_shipped_direction_has_signature_element(self):
        for did in LIB["directions"]["directions"]:
            with self.subTest(did):
                self.assertEqual(vl.docs_problems(did, LIB["docs"]), [])


class FontCheckTests(unittest.TestCase):
    def test_all_found(self):
        seen = []

        class Ok:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def opener(req, timeout):
            seen.append(req.full_url)
            return Ok()

        out = vl.check_fonts(LIB, opener=opener)
        self.assertEqual(errors_of(out), [])
        self.assertIn("https://registry.npmjs.org/@fontsource-variable%2fnewsreader", seen)
        self.assertIn("https://registry.npmjs.org/@fontsource%2fbevan", seen)

    def test_missing_package(self):
        def opener(req, timeout):
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)

        out = vl.check_fonts(LIB, opener=opener)
        self.assertTrue(any("404" in e for e in errors_of(out)))

    def test_offline_is_an_error(self):
        def opener(req, timeout):
            raise urllib.error.URLError("no network")

        self.assertTrue(any("could not reach" in e for e in errors_of(vl.check_fonts(LIB, opener=opener))))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "validate_library.py"), *args], capture_output=True, text=True)

    def test_palette_file_ok(self):
        p = copy.deepcopy(LIB["palettes"]["palettes"][0])
        p["id"] = "totally-new"
        with tempfile.TemporaryDirectory() as d:
            res = self.run_cli("--palette", str(write_json(Path(d) / "p.json", p)))
        self.assertEqual(res.returncode, 0, res.stdout)

    def test_palette_file_clashing_id(self):
        p = copy.deepcopy(LIB["palettes"]["palettes"][0])
        with tempfile.TemporaryDirectory() as d:
            res = self.run_cli("--palette", str(write_json(Path(d) / "p.json", p)))
        self.assertEqual(res.returncode, 1)
        self.assertIn("duplicate palette id", res.stdout)

    def test_palette_file_low_contrast(self):
        p = copy.deepcopy(LIB["palettes"]["palettes"][0])
        p["id"] = "totally-new"
        p["light"]["text"] = "#CCCCCC"
        with tempfile.TemporaryDirectory() as d:
            res = self.run_cli("--palette", str(write_json(Path(d) / "p.json", p)), "--json")
        self.assertEqual(res.returncode, 1)
        self.assertFalse(json.loads(res.stdout)["ok"])

    def test_direction_file_ok_and_reminds_about_docs(self):
        d = {"id": "fresh-look", **copy.deepcopy(LIB["directions"]["directions"]["swiss-grid"])}
        with tempfile.TemporaryDirectory() as t:
            res = self.run_cli("--direction", str(write_json(Path(t) / "d.json", d)))
        self.assertEqual(res.returncode, 0, res.stdout)
        self.assertIn("before merging", res.stdout)

    def test_direction_file_clashing_id(self):
        d = {"id": "poster", **copy.deepcopy(LIB["directions"]["directions"]["poster"])}
        with tempfile.TemporaryDirectory() as t:
            res = self.run_cli("--direction", str(write_json(Path(t) / "d.json", d)))
        self.assertEqual(res.returncode, 1)
        self.assertIn("already exists", res.stdout)

    def test_direction_file_missing_token(self):
        d = {"id": "fresh-look", **copy.deepcopy(LIB["directions"]["directions"]["swiss-grid"])}
        del d["tokens"]["transition"]
        with tempfile.TemporaryDirectory() as t:
            res = self.run_cli("--direction", str(write_json(Path(t) / "d.json", d)))
        self.assertEqual(res.returncode, 1)
        self.assertIn("tokens.transition", res.stdout)

    def test_unreadable_file(self):
        self.assertEqual(self.run_cli("--palette", "/nonexistent/p.json").returncode, 2)

    def test_broken_references_folder(self):
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(self.run_cli("--references", t).returncode, 2)


class ShippedDataMatchesSyncTests(unittest.TestCase):
    """The new directions must work with sync.py's generators, not just pass the validator."""

    def test_theme_and_fonts_css(self):
        import sync

        palettes = {p["id"]: p for p in LIB["palettes"]["palettes"]}
        for did, d in LIB["directions"]["directions"].items():
            with self.subTest(did):
                css = sync.build_theme_css(palettes["high-contrast-ink"], did, d)
                self.assertIn(f"direction: {did}", css)
                for k in vl.TOKEN_KEYS:
                    self.assertRegex(css, rf"--sh-{re.escape(k)}:")
                for role in ("display", "body"):
                    for imp in d["fonts"][role]["imports"]:
                        self.assertIn(imp, sync.build_fonts_css(d))
                self.assertEqual(len(sync.font_packages(d)), 2)


if __name__ == "__main__":
    unittest.main()
