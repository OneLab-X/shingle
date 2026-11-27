from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import SCRIPTS, write_json

import validate_input as v


class PhoneTests(unittest.TestCase):
    def test_national_numbers_become_e164(self):
        cases = [
            ("(415) 555-0132", "US", "+14155550132"),
            ("020 7946 0958", "GB", "+442079460958"),
            ("21 300 0000", "PT", "+351213000000"),
            ("06 1234 5678", "IT", "+390612345678"),  # Italy keeps the leading 0
            ("098765 43210", "IN", "+919876543210"),
            ("02 9876 5432", "AU", "+61298765432"),
            ("0044 20 7946 0958", None, "+442079460958"),
            ("+1 415-555-0132 ext. 12", None, "+14155550132"),
        ]
        for raw, country, expected in cases:
            with self.subTest(raw=raw):
                e164, problem = v.normalize_phone(raw, country)
                self.assertEqual(e164, expected)
                self.assertIsNone(problem)

    def test_bad_numbers(self):
        self.assertIsNone(v.normalize_phone("555-0132", "US")[0])
        self.assertIsNone(v.normalize_phone("12345", None)[0])
        self.assertIsNone(v.normalize_phone("call us", "GB")[0])

    def test_country_mismatch_is_a_warning(self):
        e164, problem = v.normalize_phone("+44 20 7946 0958", "FR")
        self.assertEqual(e164, "+442079460958")
        self.assertIn("+33", problem)

    def test_display(self):
        self.assertEqual(v.display_phone("+14155550132", "US"), "(415) 555-0132")
        self.assertEqual(v.display_phone("+442079460958", "GB"), "020 7946 0958")
        self.assertEqual(v.display_phone("+351213000000", "PT"), "213 000 000")
        self.assertEqual(v.display_phone("+442079460958", None), "+44 20 7946 0958")


class HoursTests(unittest.TestCase):
    def parse(self, text):
        r = v.Report()
        return v.parse_hours_text(text, r), r

    def test_common_formats(self):
        h, r = self.parse("Mon-Fri 9-5, Sat 10-2, Sun closed")
        self.assertEqual(h["mon"], [["09:00", "17:00"]])
        self.assertEqual(h["sat"], [["10:00", "14:00"]])
        self.assertEqual(h["sun"], [])
        self.assertTrue(any("assumed" in w for w in r.warnings))

    def test_split_shifts_and_overnight(self):
        h, _ = self.parse("Tue–Thu 12–3pm & 7–11pm; Fri, Sat 7pm-12:30am")
        self.assertEqual(h["wed"], [["12:00", "15:00"], ["19:00", "23:00"]])
        self.assertEqual(h["fri"], [["19:00", "00:30"]])
        self.assertEqual(h["sat"], [["19:00", "00:30"]])
        self.assertNotIn("mon", h)

    def test_words(self):
        h, _ = self.parse("weekdays 9:30am-6pm, weekends noon-5pm")
        self.assertEqual(h["fri"], [["09:30", "18:00"]])
        self.assertEqual(h["sun"], [["12:00", "17:00"]])
        h, _ = self.parse("Open 24/7")
        self.assertEqual(h["wed"], [["00:00", "23:59"]])
        h, _ = self.parse("Daily 07:00-16:00")
        self.assertEqual(len(h), 7)

    def test_ends_at_noon(self):
        h, _ = self.parse("Sat 8-12pm, Sun 10-12pm")
        self.assertEqual(h["sat"], [["08:00", "12:00"]])
        self.assertEqual(h["sun"], [["10:00", "12:00"]])

    def test_wrap_around_day_range(self):
        h, _ = self.parse("Fri-Mon 10am-4pm")
        self.assertEqual(sorted(h), ["fri", "mon", "sat", "sun"])

    def test_structured_checks(self):
        r = v.Report()
        out = v.check_hours(
            {
                "mon": [["9:00", "17:00"]],
                "tue": [["09:00", "13:00"], ["12:00", "18:00"]],
                "wed": [["25:00", "26:00"]],
                "funday": [],
            },
            r,
        )
        self.assertEqual(out["mon"], [["09:00", "17:00"]])
        self.assertTrue(any("overlap" in e for e in r.errors))
        self.assertTrue(any("HH:MM" in e for e in r.errors))
        self.assertTrue(any("funday" in e for e in r.errors))
        self.assertTrue(any("unknown for" in w for w in r.warnings))


class NormalizeTests(unittest.TestCase):
    def test_full_normalization(self):
        data = {
            "name": "  Café  Lumière & Co ",
            "category": "Coffee Shop",
            "domain": "HTTPS://www.CafeLumiere.fr/menu?x=1",
            "address": {"street": "12 Rue Oberkampf", "locality": "Paris", "postal_code": "75011", "country": "France"},
            "phone": "01 43 55 00 00",
            "email": "Bonjour@CafeLumiere.FR",
            "hours": "Mon-Sat 8-19, Sun closed",
            "socials": {"instagram": "@cafelumiere", "twitter": "cafelumiere"},
            "languages": ["FR", "en_gb"],
        }
        out, r = v.normalize(data)
        self.assertEqual(r.errors, [])
        self.assertEqual(out["name"], "Café Lumière & Co")
        self.assertEqual(out["slug"], "cafe-lumiere-and-co")
        self.assertEqual(out["category"], "cafe")
        self.assertEqual(out["domain"], "www.cafelumiere.fr")
        self.assertEqual(out["address"]["country"], "FR")
        self.assertEqual(out["phone"], "+33143550000")
        self.assertEqual(out["email"], "Bonjour@cafelumiere.fr")
        self.assertEqual(out["hours"]["mon"], [["08:00", "19:00"]])
        self.assertEqual(out["socials"], {"instagram": "https://instagram.com/cafelumiere", "x": "https://x.com/cafelumiere"})
        self.assertEqual(out["languages"], ["fr", "en-GB"])
        self.assertEqual(list(out)[:4], ["schema_version", "name", "slug", "category"])

    def test_missing_essentials(self):
        out, r = v.normalize({"tagline": "hi"})
        fields = {m["field"] for m in r.missing if m["essential"]}
        self.assertEqual(fields, {"name", "category", "phone|email|address"})

    def test_errors(self):
        _, r = v.normalize(
            {
                "name": "X",
                "category": "spaceport",
                "domain": "instagram.com/x",
                "email": "nope",
                "images": [{"src": "https://example.com/a.jpg"}],
            }
        )
        text = " ".join(r.errors)
        self.assertIn("spaceport", text)
        self.assertIn("social profile", text)
        self.assertIn("email", text)
        self.assertIn("remote", text)

    def test_whatsapp_true_copies_phone(self):
        out, r = v.normalize({"name": "X", "category": "cafe", "phone": "+351213000000", "whatsapp": True})
        self.assertEqual(out["whatsapp"], "+351213000000")

    def test_postal_warning(self):
        _, r = v.normalize(
            {
                "name": "X",
                "category": "cafe",
                "address": {"street": "1 Main", "locality": "Austin", "postal_code": "ABC", "country": "US"},
            }
        )
        self.assertTrue(any("postal" in w for w in r.warnings))


class LanguageTests(unittest.TestCase):
    BASE = {
        "name": "Casa",
        "category": "cafe",
        "languages": ["pt", "en"],
        "phone": "+351213000000",
        "tagline": "Café em Lisboa",
        "facts": {
            "menu": [{"name": "Bolo", "description": "De laranja", "price": "€3"}],
            "team": [{"name": "Ana", "role": "Dona"}],
        },
    }

    def run_normalize(self, **extra):
        data = {**self.BASE, **extra}
        return v.normalize(data)

    def test_languages_normalized_and_deduped(self):
        out, r = self.run_normalize(languages=["PT", "en_gb", "pt", "en-GB"])
        self.assertEqual(out["languages"], ["pt", "en-GB"])
        self.assertTrue(any("twice" in w for w in r.warnings))

    def test_warns_without_ui_dictionary_and_for_rtl(self):
        _, r = self.run_normalize(languages=["pt", "xx", "ar"])
        text = " ".join(r.warnings)
        self.assertIn("no interface dictionary for 'xx'", text)
        self.assertIn("right-to-left", text)

    def test_valid_translation_overlay(self):
        tr = {
            "en": {
                "review": "draft",
                "tagline": "Cafe in Lisbon",
                "facts": {
                    "menu": [{"name": "Cake", "description": "Orange", "price": "€3"}],
                    "team": [{"name": "Ana", "role": "Owner"}],
                },
            }
        }
        _, r = self.run_normalize(translations=tr)
        self.assertEqual(r.errors, [])
        self.assertEqual([w for w in r.warnings if "translations" in w], [])

    def test_locked_fields_error(self):
        tr = {"en": {"phone": "+1", "facts": {"menu": [{"price": "€4"}], "team": [{"name": "Anne"}]}}}
        _, r = self.run_normalize(translations=tr)
        text = " ".join(r.errors)
        self.assertIn("translations.en.phone", text)
        self.assertIn("translations.en.facts.menu.0.price", text)
        self.assertIn("translations.en.facts.team.0.name", text)

    def test_dish_names_may_be_translated(self):
        tr = {"en": {"facts": {"menu": [{"name": "Cake"}]}}}
        _, r = self.run_normalize(translations=tr)
        self.assertEqual(r.errors, [])

    def test_bad_keys_and_review_state(self):
        _, r = self.run_normalize(translations={"fr": {}, "en": {"review": "done"}, "pt": {}})
        text = " ".join(r.errors + r.warnings)
        self.assertIn("'fr' is not in languages", text)
        self.assertIn("review must be one of", text)
        self.assertIn("default language is written at the top level", text)

    def test_warnings_for_array_length_unknown_key_and_missing_language(self):
        tr = {"en": {"facts": {"menu": [{"name": "a"}, {"name": "b"}]}, "nonsense": 1}}
        _, r = self.run_normalize(translations=tr)
        text = " ".join(r.warnings)
        self.assertIn("2 items but the default language has 1", text)
        self.assertIn("translations.en.nonsense", text)
        _, r = self.run_normalize(languages=["pt", "en", "es"], translations=tr)
        self.assertIn("no translations for 'es'", " ".join(r.warnings))

    def test_single_language_ignores_translations(self):
        _, r = self.run_normalize(languages=["pt"], translations={"en": {"tagline": "x"}})
        self.assertEqual(r.errors, [])
        self.assertTrue(any("ignored" in w for w in r.warnings))


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPTS / "validate_input.py"), *args], capture_output=True, text=True)

    def test_write_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_json(Path(d) / "business.json", {"name": "Bolt Gym", "category": "gym", "phone": "+1 512 555 0100"})
            res = self.run_cli(str(p), "--write", "--json")
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertTrue(json.loads(res.stdout)["written"])
            saved = json.loads(p.read_text())
            self.assertEqual(saved["category"], "gym-fitness")
            self.assertEqual(saved["phone"], "+15125550100")
            bad = write_json(Path(d) / "bad.json", {"name": "X", "category": "nope"})
            self.assertEqual(self.run_cli(str(bad), "--write").returncode, 1)
            self.assertEqual(json.loads(bad.read_text())["category"], "nope")  # not written on error
            self.assertEqual(self.run_cli(str(Path(d) / "missing.json")).returncode, 2)


if __name__ == "__main__":
    unittest.main()
