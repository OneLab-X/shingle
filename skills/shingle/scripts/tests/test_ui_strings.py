"""Every UI dictionary has the same keys as English, no empty values, and keeps {placeholders}."""

from __future__ import annotations

import json
import re
import unittest

from helpers import SCRIPTS

UI = SCRIPTS.parent / "references" / "ui-strings"
PLACEHOLDER = re.compile(r"\{(\w+)\}")


def load(code: str) -> dict:
    return json.loads((UI / f"{code}.json").read_text(encoding="utf-8"))


class UiStringTests(unittest.TestCase):
    def test_dictionaries_exist(self):
        self.assertEqual(sorted(p.stem for p in UI.glob("*.json")), ["de", "en", "es", "fr", "it", "pt"])

    def test_same_keys_as_english(self):
        en = {k for k in load("en") if k != "_meta"}
        for path in sorted(UI.glob("*.json")):
            keys = {k for k in load(path.stem) if k != "_meta"}
            with self.subTest(path.stem):
                self.assertEqual(en - keys, set(), "missing keys")
                self.assertEqual(keys - en, set(), "extra keys")

    def test_values_filled_and_placeholders_kept(self):
        en = load("en")
        for path in sorted(UI.glob("*.json")):
            d = load(path.stem)
            self.assertEqual(d["_meta"]["language"], path.stem)
            for key, value in d.items():
                if key == "_meta":
                    continue
                with self.subTest(f"{path.stem}:{key}"):
                    self.assertTrue(isinstance(value, str) and value.strip())
                    self.assertEqual(set(PLACEHOLDER.findall(value)), set(PLACEHOLDER.findall(en[key])))

    def test_all_seven_days_present(self):
        for code in ("en", "pt", "es", "fr", "de", "it"):
            d = load(code)
            for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
                self.assertIn(f"day_long.{day}", d)
                self.assertIn(f"day_short.{day}", d)


if __name__ == "__main__":
    unittest.main()
