from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, write_json

import check_contrast as cc

PALETTES = json.loads((SCRIPTS.parent / "references" / "palettes.json").read_text())


class MathTests(unittest.TestCase):
    def test_known_ratios(self):
        self.assertAlmostEqual(cc.contrast("#000000", "#FFFFFF"), 21.0, places=2)
        self.assertAlmostEqual(cc.contrast("#FFF", "#FFF"), 1.0, places=2)
        self.assertAlmostEqual(cc.contrast("#777777", "#FFFFFF"), 4.48, places=2)
        self.assertAlmostEqual(cc.contrast("#0B5F8A", "#F7FAFC"), cc.contrast("#F7FAFC", "#0B5F8A"))

    def test_bad_hex(self):
        with self.assertRaises(ValueError):
            cc.parse_hex("#12")

    def test_suggestion_passes(self):
        fix = cc.suggest_fix("#999999", "#FFFFFF", 4.5)
        self.assertGreaterEqual(cc.contrast(fix, "#FFFFFF"), 4.5)
        fix = cc.suggest_fix("#444444", "#111111", 4.5)
        self.assertGreaterEqual(cc.contrast(fix, "#111111"), 4.5)


class PaletteTests(unittest.TestCase):
    def test_every_curated_palette_passes(self):
        for p in PALETTES["palettes"]:
            with self.subTest(p["id"]):
                failures = [r for r in cc.check_palette(p, PALETTES["contrast_rules"]) if not r["ok"]]
                self.assertEqual(failures, [])

    def test_palette_shape(self):
        ids = [p["id"] for p in PALETTES["palettes"]]
        self.assertEqual(len(ids), len(set(ids)))
        cats = {c for p in PALETTES["palettes"] for c in p["categories"]}
        from validate_input import CATEGORIES

        self.assertTrue(cats <= set(CATEGORIES), cats - set(CATEGORIES))
        for c in CATEGORIES:
            self.assertGreaterEqual(sum(c in p["categories"] for p in PALETTES["palettes"]), 2, c)

    def test_failing_palette_reports_fixes(self):
        bad = {
            "light": {
                "background": "#FFFFFF",
                "surface": "#F5F5F5",
                "text": "#999999",
                "muted": "#AAAAAA",
                "primary": "#8B5CF6",
                "on_primary": "#FFFFFF",
                "accent": "#FFE066",
            }
        }
        results = cc.check_palette(bad)
        fails = [r for r in results if not r["ok"]]
        self.assertTrue(any(r["pair"] == "text/background" for r in fails))
        for r in fails:
            self.assertTrue(r["suggestions"])
            self.assertNotIn("change background to #3", " ".join(r["suggestions"]))  # never flips light to dark

    def test_missing_role(self):
        results = cc.check_palette({"light": {"background": "#FFFFFF", "text": "#000000"}})
        self.assertTrue(any("missing role" in r.get("message", "") for r in results))

    def test_suggest_ranks_category(self):
        picks = cc.suggest(PALETTES, "dental-clinic", ["calm"], 3)
        self.assertEqual(len(picks), 3)
        self.assertTrue(all("dental-clinic" in p["categories"] for p in picks))
        self.assertEqual(cc.suggest(PALETTES, "unknown-category", [], 3)[0]["categories"].count("generic-local-business"), 1)


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "check_contrast.py"), *args], capture_output=True, text=True)

    def test_cli(self):
        self.assertEqual(self.run_cli("--all").returncode, 0)
        self.assertEqual(self.run_cli("--palette", "harbor-blue").returncode, 0)
        self.assertEqual(self.run_cli("--palette", "nope").returncode, 2)
        res = self.run_cli("--suggest", "--category", "cafe", "--json")
        self.assertEqual(res.returncode, 0)
        self.assertTrue(json.loads(res.stdout))
        with tempfile.TemporaryDirectory() as d:
            f = write_json(
                Path(d) / "p.json",
                {
                    "light": {
                        "background": "#FFFFFF",
                        "surface": "#FFFFFF",
                        "text": "#BBBBBB",
                        "muted": "#000000",
                        "primary": "#000000",
                        "on_primary": "#FFFFFF",
                        "accent": "#000000",
                    }
                },
            )
            res = self.run_cli("--file", str(f))
            self.assertEqual(res.returncode, 1)
            self.assertIn("FAIL", res.stdout)
            self.assertIn("fix:", res.stdout)


if __name__ == "__main__":
    unittest.main()
