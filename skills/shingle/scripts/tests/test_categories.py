"""Every category file follows the shared format and only references real directions/palettes.

This is the check a contributor runs after adding a category (see docs/adding-a-category.md).
"""

from __future__ import annotations

import json
import re
import unittest

from helpers import SCRIPTS

import sync
import validate_input

REFS = SCRIPTS.parent / "references"
CATS = REFS / "categories"
REQUIRED = [
    "- **Audience:**",
    "- **Tone options:**",
    "- **Schema type:**",
    "- **Default pages:**",
    "- **Primary CTA options:**",
    "## Required sections",
    "## Optional sections",
    "## Category questions",
    "## Imagery",
    "## Never invent",
    "## Design fit",
    "## Copy notes",
]
DIRECTIONS = set(json.loads((REFS / "directions.json").read_text())["directions"])
PALETTES = {p["id"]: p for p in json.loads((REFS / "palettes.json").read_text())["palettes"]}


class CategoryFileTests(unittest.TestCase):
    def test_files_match_known_categories(self):
        on_disk = {p.stem for p in CATS.glob("*.md")}
        self.assertEqual(on_disk, set(validate_input.CATEGORIES))

    def test_every_category_is_wired_into_sync(self):
        for c in validate_input.CATEGORIES:
            self.assertIn(c, sync.SCHEMA_TYPES, c)
            self.assertIn(c, sync.CATEGORY_LABELS, c)

    def test_format(self):
        for path in sorted(CATS.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            with self.subTest(path.name):
                self.assertTrue(text.startswith(f"# Category: {path.stem}\n"), "first line must be '# Category: <file name>'")
                for heading in REQUIRED:
                    self.assertIn(heading, text)
                self.assertLessEqual(len(text.splitlines()), 90, "keep category files short (progressive disclosure)")

    def test_design_fit_references_exist(self):
        for path in sorted(CATS.glob("*.md")):
            fit = path.read_text(encoding="utf-8").split("## Design fit", 1)[1].split("##", 1)[0]
            names = re.findall(r"`([a-z0-9-]+)`", fit)
            with self.subTest(path.name):
                self.assertTrue(names)
                unknown = [n for n in names if n not in DIRECTIONS and n not in PALETTES]
                self.assertEqual(unknown, [])

    def test_registry(self):
        reg = validate_input.REGISTRY["categories"]
        aliases = [a for c in reg.values() for a in c.get("aliases", [])]
        self.assertEqual(len(aliases), len(set(aliases)), "an alias may point to one category only")
        self.assertFalse(set(aliases) & set(reg), "an alias must not equal a category id")
        for cid, c in reg.items():
            with self.subTest(cid):
                self.assertRegex(cid, r"^[a-z0-9]+(-[a-z0-9]+)*$")
                self.assertTrue(c["label"] and c["schema_type"])
                for a in c.get("aliases", []):
                    self.assertEqual(a, validate_input.slugify(a), f"alias {a!r} must be a slug")

    def test_each_category_has_palettes(self):
        for c in validate_input.CATEGORIES:
            self.assertGreaterEqual(sum(c in p["categories"] for p in PALETTES.values()), 2, c)


if __name__ == "__main__":
    unittest.main()
