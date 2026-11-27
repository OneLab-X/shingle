from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import image_fixtures as fx
from helpers import BUSINESS, SCRIPTS, write_json

import import_images
import imagemeta
import sync


def make_site(root: Path, **extra) -> Path:
    site = root / "site"
    write_json(site / "business.json", {**BUSINESS, **extra})
    return site


def photos(root: Path) -> Path:
    folder = root / "photos"
    folder.mkdir()
    return folder


def business(site: Path) -> dict:
    return json.loads((site / "business.json").read_text(encoding="utf-8"))


def cli(*args):
    return subprocess.run([sys.executable, str(SCRIPTS / "import_images.py"), *map(str, args)], capture_output=True, text=True)


class ImportTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.site = make_site(self.root)
        self.folder = photos(self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def run_import(self, **kw):
        return import_images.import_folder(self.folder, self.site, **kw)

    def test_scans_images_only_case_insensitive_skips_hidden_and_nonrecursive(self):
        (self.folder / "Dining Room.JPG").write_bytes(fx.make_jpeg())
        (self.folder / "menu.PNG").write_bytes(fx.make_png())
        (self.folder / "notes.txt").write_text("hi")
        (self.folder / ".hidden.jpg").write_bytes(fx.make_jpeg())
        (self.folder / "._menu.png").write_bytes(b"apple double")
        (self.folder / ".DS_Store").write_bytes(b"x")
        (self.folder / "sub").mkdir()
        (self.folder / "sub" / "deep.jpg").write_bytes(fx.make_jpeg(10, 10))
        report = self.run_import()
        self.assertEqual(sorted(i["file"] for i in report["imported"]), ["dining-room.jpg", "menu.png"])
        self.assertEqual([s["source"] for s in report["skipped"]], ["notes.txt"])
        deep = self.run_import(recursive=True)
        self.assertEqual([i["source"] for i in deep["imported"]], ["sub/deep.jpg"])

    def test_entries_and_clean_names(self):
        (self.folder / "Dining Room.JPG").write_bytes(fx.make_jpeg(80, 60))
        (self.folder / "IMG_4521.png").write_bytes(fx.make_png(30, 20))
        self.run_import()
        entries = business(self.site)["images"]
        self.assertEqual(
            [{k: v for k, v in e.items() if k != "sha256"} for e in entries],
            [
                {
                    "src": "public/images/dining-room.jpg",
                    "alt": "",
                    "subject": "Dining room",
                    "width": 80,
                    "height": 60,
                    "suggested_alt": "",
                    "status": "needs-alt",
                },
                {
                    "src": "public/images/img-4521.png",
                    "alt": "",
                    "subject": "",
                    "width": 30,
                    "height": 20,
                    "suggested_alt": "",
                    "status": "needs-alt",
                },
            ],
        )
        self.assertTrue((self.site / "public/images/dining-room.jpg").is_file())

    def test_extension_follows_the_real_format(self):
        (self.folder / "logo.jpg").write_bytes(fx.make_png())
        self.assertEqual(self.run_import()["imported"][0]["file"], "logo.png")

    def test_gps_is_stripped_from_the_copy_and_reported_and_original_untouched(self):
        original = fx.make_jpeg(64, 48, exif=fx.exif_block(1), xmp=True)
        (self.folder / "shop.jpg").write_bytes(original)
        report = self.run_import()
        copy = (self.site / "public/images/shop.jpg").read_bytes()
        self.assertNotIn(fx.GPS_MARKER, copy)
        self.assertFalse(imagemeta.has_gps(copy))
        self.assertIn("GPS location", " ".join(report["imported"][0]["stripped"]))
        self.assertEqual((self.folder / "shop.jpg").read_bytes(), original)

    def test_rotated_phone_photo_reports_display_size(self):
        (self.folder / "tall.jpg").write_bytes(fx.make_jpeg(64, 48, exif=fx.exif_block(6)))
        report = self.run_import()
        self.assertEqual((report["imported"][0]["width"], report["imported"][0]["height"]), (48, 64))
        self.assertTrue(report["imported"][0]["rotated"])

    def test_name_collisions_never_overwrite(self):
        (self.site / "public/images").mkdir(parents=True)
        precious = b"owner's own file"
        (self.site / "public/images/shop.jpg").write_bytes(precious)
        (self.folder / "Shop.jpg").write_bytes(fx.make_jpeg(10, 10))
        (self.folder / "shop.png").write_bytes(fx.make_png(10, 10))
        (self.folder / "SHOP!.jpg").write_bytes(fx.make_jpeg(20, 20))
        report = self.run_import()
        self.assertEqual(sorted(i["file"] for i in report["imported"]), ["shop-2.jpg", "shop-3.jpg", "shop.png"])
        self.assertEqual((self.site / "public/images/shop.jpg").read_bytes(), precious)

    def test_reimport_is_idempotent(self):
        (self.folder / "a.jpg").write_bytes(fx.make_jpeg(40, 30, exif=fx.exif_block(1)))
        (self.folder / "b.png").write_bytes(fx.make_png(40, 30, (1, 2, 3)))
        self.run_import()
        first = (self.site / "business.json").read_bytes()
        files = sorted(p.name for p in (self.site / "public/images").iterdir())
        again = self.run_import()
        self.assertEqual(again["imported"], [])
        self.assertEqual(len(again["skipped"]), 2)
        self.assertEqual((self.site / "business.json").read_bytes(), first)
        self.assertEqual(sorted(p.name for p in (self.site / "public/images").iterdir()), files)

    def test_same_picture_twice_in_one_folder_and_renamed_copy(self):
        (self.folder / "a.png").write_bytes(fx.make_png())
        (self.folder / "copy of a.png").write_bytes(fx.make_png())
        report = self.run_import()
        self.assertEqual(len(report["imported"]), 1)
        self.assertIn("same picture", report["skipped"][0]["reason"])
        (self.folder / "renamed.png").write_bytes(fx.make_png())
        self.assertEqual(self.run_import()["imported"], [])

    def test_existing_confirmed_entry_is_untouched(self):
        (self.folder / "a.png").write_bytes(fx.make_png())
        self.run_import()
        data = business(self.site)
        data["images"][0].update(alt="Orange rectangle", status="ok", subject="Hero")
        write_json(self.site / "business.json", data)
        self.run_import()
        self.assertEqual(business(self.site)["images"][0]["alt"], "Orange rectangle")

    def test_corrupt_zero_and_oversized_files_are_rejected_with_reasons(self):
        (self.folder / "ok.png").write_bytes(fx.make_png())
        (self.folder / "broken.jpg").write_bytes(fx.make_jpeg()[:-40])
        (self.folder / "empty.png").write_bytes(b"")
        (self.folder / "zero.png").write_bytes(fx.make_png(0, 4))
        (self.folder / "fake.gif").write_bytes(b"this is text")
        (self.folder / "huge.jpg").write_bytes(b"\xff\xd8" + b"\0" * (imagemeta.MAX_BYTES + 10))
        report = self.run_import()
        self.assertEqual([i["file"] for i in report["imported"]], ["ok.png"])
        reasons = {r["source"]: r["reason"] for r in report["rejected"]}
        self.assertEqual(sorted(reasons), ["broken.jpg", "empty.png", "fake.gif", "huge.jpg", "zero.png"])
        self.assertIn("25 MB", reasons["huge.jpg"])
        self.assertIn("empty", reasons["empty.png"])
        self.assertIn("corrupt", reasons["broken.jpg"])
        self.assertEqual(len(business(self.site)["images"]), 1)

    def test_all_rejected_exits_1(self):
        (self.folder / "bad.png").write_bytes(b"nope")
        out = cli(self.folder, "--site", self.site, "--json")
        self.assertEqual(out.returncode, 1)
        self.assertEqual(json.loads(out.stdout)["rejected"][0]["source"], "bad.png")

    def test_dry_run_writes_nothing(self):
        (self.folder / "a.png").write_bytes(fx.make_png())
        report = self.run_import(dry_run=True)
        self.assertEqual(report["imported"][0]["file"], "a.png")
        self.assertFalse((self.site / "public/images").exists())
        self.assertNotIn("images", business(self.site))

    def test_hand_placed_file_is_adopted_not_duplicated(self):
        (self.site / "public/images").mkdir(parents=True)
        data = fx.make_png()
        (self.site / "public/images/hero.png").write_bytes(data)
        (self.folder / "x.png").write_bytes(data)
        report = self.run_import()
        self.assertEqual(report["imported"][0]["file"], "hero.png")
        self.assertEqual(len(list((self.site / "public/images").iterdir())), 1)

    def test_cli_json_and_usage_errors(self):
        (self.folder / "a.png").write_bytes(fx.make_png())
        out = cli(self.folder, "--site", self.site, "--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["needs_alt"][0]["file"], "a.png")
        self.assertEqual(cli(self.folder, "--site", self.root / "nope").returncode, 2)
        self.assertEqual(cli("--site", self.site).returncode, 2)
        listing = cli("--list", "--site", self.site, "--json")
        self.assertEqual(json.loads(listing.stdout)["needs_alt"][0]["file"], "a.png")


class ApplyAltTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def site_with_images(self, **extra) -> Path:
        site = make_site(self.root, **extra)
        folder = photos(self.root)
        (folder / "dining-room.jpg").write_bytes(fx.make_jpeg(40, 30, (200, 100, 50)))
        (folder / "front-door.png").write_bytes(fx.make_png(40, 30, (20, 90, 160)))
        (folder / "IMG_0001.png").write_bytes(fx.make_png(40, 30, (90, 160, 20)))
        import_images.import_folder(folder, site)
        return site

    def apply(self, site, answers):
        return import_images.apply_alt(site, answers)

    def test_applies_alt_clears_suggestion_and_sets_ok(self):
        site = self.site_with_images()
        data = business(site)
        for img in data["images"]:
            img["suggested_alt"] = "Wooden tables"
        write_json(site / "business.json", data)
        result = self.apply(
            site,
            [
                {"file": "dining-room.jpg", "alt": "Wooden tables set for dinner", "subject": "Dining room"},
                {"file": "front-door.png", "alt": "Blue front door", "subject": "Entrance"},
                {"file": "img-0001.png", "decorative": True},
            ],
        )
        self.assertTrue(result["ok"], result["errors"])
        images = business(site)["images"]
        by = {Path(i["src"]).name: i for i in images}
        self.assertEqual([i["status"] for i in images], ["ok", "ok", "ok"])
        self.assertEqual(by["dining-room.jpg"]["alt"], "Wooden tables set for dinner")
        self.assertEqual(by["dining-room.jpg"]["suggested_alt"], "")
        self.assertEqual(by["front-door.png"]["subject"], "Entrance")
        self.assertEqual((by["img-0001.png"]["alt"], by["img-0001.png"]["decorative"]), ("", True))
        self.assertEqual(result["needs_alt"], [])

    def test_rules_are_enforced_and_nothing_is_written_on_error(self):
        site = self.site_with_images()
        before = (site / "business.json").read_bytes()
        cases = {
            "": "empty",
            "x" * 126: "126 characters",
            "Photo of a dining room": "image of",
            "Image of a door": "image of",
            "front-door.png": "file name",
            "IMG_0001": "file name",
        }
        for alt, expect in cases.items():
            result = self.apply(site, [{"file": "front-door.png", "alt": alt}])
            self.assertFalse(result["ok"], alt)
            self.assertIn(expect, " ".join(result["errors"]))
        self.assertEqual((site / "business.json").read_bytes(), before)

    def test_two_images_cannot_share_alt_text(self):
        site = self.site_with_images()
        result = self.apply(
            site,
            [{"file": "dining-room.jpg", "alt": "A room with tables"}, {"file": "front-door.png", "alt": "a room  with TABLES"}],
        )
        self.assertFalse(result["ok"])
        self.assertIn("same alt text", result["errors"][0])

    def test_clash_with_alt_confirmed_earlier(self):
        site = self.site_with_images()
        self.assertTrue(self.apply(site, [{"file": "dining-room.jpg", "alt": "A room with tables"}])["ok"])
        result = self.apply(site, [{"file": "front-door.png", "alt": "A room with tables"}])
        self.assertFalse(result["ok"])

    def test_unknown_file_and_bad_shapes(self):
        site = self.site_with_images()
        self.assertIn("no image named", self.apply(site, [{"file": "ghost.jpg", "alt": "x y"}])["errors"][0])
        with self.assertRaises(import_images.UsageError):
            self.apply(site, "nonsense")
        self.assertTrue(self.apply(site, {"images": [{"file": "front-door.png", "alt": "Blue front door"}]})["ok"])

    def test_translations_for_multilingual_sites(self):
        site = self.site_with_images(languages=["pt", "en"])
        result = self.apply(
            site,
            [
                {
                    "file": "dining-room.jpg",
                    "alt": "Mesas de madeira postas para o jantar",
                    "translations": {"en": "Wooden tables set for dinner"},
                },
                {"file": "front-door.png", "alt": "Porta azul"},
            ],
        )
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(any("no en alt text" in w for w in result["warnings"]))
        names = [Path(i["src"]).name for i in business(site)["images"]]
        rows = business(site)["translations"]["en"]["images"]
        self.assertEqual(rows[names.index("dining-room.jpg")], {"alt": "Wooden tables set for dinner"})
        self.assertEqual(rows[names.index("front-door.png")], {})
        self.assertEqual(len(rows), 3)

    def test_translation_for_unknown_language_is_an_error(self):
        site = self.site_with_images(languages=["pt", "en"])
        result = self.apply(site, [{"file": "front-door.png", "alt": "Porta azul", "translations": {"fr": "Porte bleue"}}])
        self.assertFalse(result["ok"])

    def test_translated_alt_rules_and_duplicates(self):
        site = self.site_with_images(languages=["pt", "en"])
        result = self.apply(
            site,
            [
                {"file": "dining-room.jpg", "alt": "Mesas", "translations": {"en": "Photo of tables"}},
                {"file": "front-door.png", "alt": "Porta", "translations": {"en": "Photo of tables"}},
            ],
        )
        self.assertFalse(result["ok"])
        self.assertTrue(any("translations.en" in e for e in result["errors"]))
        same = self.apply(
            site,
            [
                {"file": "dining-room.jpg", "alt": "Mesas", "translations": {"en": "Tables"}},
                {"file": "front-door.png", "alt": "Porta", "translations": {"en": "tables"}},
            ],
        )
        self.assertFalse(same["ok"])
        self.assertIn("translations.en", same["errors"][0])

    def test_cli(self):
        site = self.site_with_images()
        answers = write_json(self.root / "answers.json", [{"file": "front-door.png", "alt": "Blue front door"}])
        out = cli("--apply-alt", answers, "--site", site, "--json")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(json.loads(out.stdout)["applied"], ["front-door.png"])
        bad = write_json(self.root / "bad.json", [{"file": "dining-room.jpg", "alt": "image of a room"}])
        out = cli("--apply-alt", bad, "--site", site)
        self.assertEqual(out.returncode, 1)
        self.assertIn("nothing saved", out.stdout)


class SiteDataTests(unittest.TestCase):
    """Confirmed images reach src/data/site*.json, with the right language's alt and never suggested_alt."""

    def test_site_data_carries_only_confirmed_images_with_translated_alt(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            site = make_site(root, languages=["pt", "en"])
            folder = photos(root)
            (folder / "dining-room.jpg").write_bytes(fx.make_jpeg(40, 30))
            (folder / "front-door.png").write_bytes(fx.make_png(40, 30, (1, 2, 3)))
            import_images.import_folder(folder, site)
            data = business(site)
            for img in data["images"]:
                img["suggested_alt"] = "never published"
            write_json(site / "business.json", data)
            import_images.apply_alt(
                site, [{"file": "dining-room.jpg", "alt": "Mesas", "subject": "Sala", "translations": {"en": "Tables"}}]
            )
            normalized, _ = sync.normalize(business(site))
            i18n = sync.build_i18n(normalized)
            pt = sync.build_site_data(normalized, None, "pt", i18n)
            en = sync.build_site_data(sync.translated_business(normalized, "en"), None, "en", i18n)
            self.assertEqual([i["alt"] for i in pt["images"]], ["Mesas"])
            self.assertEqual([i["alt"] for i in en["images"]], ["Tables"])
            self.assertEqual(en["images"][0]["subject"], "Sala")
            self.assertEqual(en["images"][0]["file"], "dining-room.jpg")
            self.assertNotIn("never published", json.dumps(pt) + json.dumps(en))

    def test_no_images_key_without_photos(self):
        normalized, _ = sync.normalize(dict(BUSINESS))
        self.assertNotIn("images", sync.build_site_data(normalized))

    def test_validator_accepts_translated_image_rows(self):
        with tempfile.TemporaryDirectory() as d:
            site = make_site(Path(d), languages=["pt", "en"])
            folder = photos(Path(d))
            (folder / "a.png").write_bytes(fx.make_png())
            import_images.import_folder(folder, site)
            import_images.apply_alt(site, [{"file": "a.png", "alt": "Cor", "translations": {"en": "Colour"}}])
            _, report = sync.normalize(business(site))
            self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
