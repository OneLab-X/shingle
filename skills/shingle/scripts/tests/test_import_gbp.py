from __future__ import annotations

import copy
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from helpers import SCRIPTS, write_json

import import_gbp as g
import sync
import validate_input as v

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "gbp"
CSV_PATH = FIXTURES / "locations.csv"
API_PATH = FIXTURES / "api-location.json"


def csv_rows() -> list[list[str]]:
    return list(csv.reader(io.StringIO(CSV_PATH.read_text(encoding="utf-8"))))


def write_table(path: Path, rows: list[list[str]], *, delimiter: str = ",", encoding: str = "utf-8", newline: str = "\n") -> Path:
    buf = io.StringIO()
    csv.writer(buf, delimiter=delimiter, lineterminator=newline).writerows(rows)
    path.write_bytes(buf.getvalue().encode(encoding))
    return path


def col_letters(i: int) -> str:
    out = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(65 + r) + out
    return out


def write_xlsx(path: Path, sheets: list[tuple[str, list[list[str]]]], *, shared: bool = True) -> Path:
    """A minimal valid .xlsx (what Excel or Sheets would save), built with zipfile only."""
    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    strings: list[str] = []

    def cell(ref: str, text: str) -> str:
        if text == "":
            return ""
        if text.isdigit():
            return f'<c r="{ref}"><v>{text}</v></c>'
        if shared:
            if text not in strings:
                strings.append(text)
            return f'<c r="{ref}" t="s"><v>{strings.index(text)}</v></c>'
        esc = text.replace("&", "&amp;").replace("<", "&lt;")
        return f'<c r="{ref}" t="inlineStr"><is><t>{esc}</t></is></c>'

    sheet_xml = []
    for _, rows in sheets:
        body = "".join(
            f'<row r="{r + 1}">' + "".join(cell(f"{col_letters(c)}{r + 1}", t) for c, t in enumerate(row)) + "</row>"
            for r, row in enumerate(rows)
        )
        sheet_xml.append(f'<?xml version="1.0"?><worksheet xmlns="{ns}"><sheetData>{body}</sheetData></worksheet>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        z.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0"?><workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
            + "".join(f'<sheet name="{n}" sheetId="{i + 1}" r:id="rId{i + 1}"/>' for i, (n, _) in enumerate(sheets))
            + "</sheets></workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(f'<Relationship Id="rId{i + 1}" Target="worksheets/sheet{i + 1}.xml"/>' for i in range(len(sheets)))
            + "</Relationships>",
        )
        for i, xml in enumerate(sheet_xml):
            z.writestr(f"xl/worksheets/sheet{i + 1}.xml", xml)
        if shared:
            z.writestr(
                "xl/sharedStrings.xml",
                f'<?xml version="1.0"?><sst xmlns="{ns}">'
                + "".join(f"<si><t>{s.replace('&', '&amp;').replace('<', '&lt;')}</t></si>" for s in strings)
                + "</sst>",
            )
    return path


class HeaderTests(unittest.TestCase):
    def test_canonical_fields(self):
        cases = {
            "Business name": "name",
            "  Business Name *": "name",
            "Address line 3": "address_3",
            "Country/Region": "country",
            "Administrative area": "region",
            "Sunday hours": "hours_sun",
            "From the business": "description",
            "Other Photos": "photos",
            "Primary phone": "phone",
        }
        for header, field in cases.items():
            with self.subTest(header):
                self.assertEqual(g.field_of(header), field)
        self.assertIsNone(g.field_of("Wheelchair accessible entrance"))


class DayCellTests(unittest.TestCase):
    def test_grammar(self):
        cases = {
            "": [],
            "X": [],
            "x": [],
            "09:00-17:00": [["09:00", "17:00"]],
            "09:00AM-05:30PM": [["09:00", "17:30"]],
            "11:30AM-02:00PM, 05:00PM-10:00PM": [["11:30", "14:00"], ["17:00", "22:00"]],
            "11:30-14:00, 17:00-22:00": [["11:30", "14:00"], ["17:00", "22:00"]],
            "09:00AM-12:00AM": [["09:00", "00:00"]],
            "09:00-24:00": [["09:00", "00:00"]],
            "06:00PM-02:00AM": [["18:00", "02:00"]],
            "00:00-00:00": [["00:00", "23:59"]],
            "00:00-24:00": [["00:00", "23:59"]],
            "12:00AM-12:00AM": [["00:00", "23:59"]],
            "12:00PM-1:00PM": [["12:00", "13:00"]],
        }
        for cell, expected in cases.items():
            with self.subTest(cell):
                self.assertEqual(g.parse_day_cell(cell), expected)

    def test_bad_cells(self):
        for cell in ("closed", "9", "09:00-09:00", "25:00-26:00", "09:00-10:00-11:00"):
            with self.subTest(cell), self.assertRaises(ValueError):
                g.parse_day_cell(cell)

    def test_all_empty_means_unknown_not_closed(self):
        r = g.ImportReport()
        self.assertIsNone(g.hours_from_cells({d: "" for d in v.DAY_KEYS}, r))
        hours = g.hours_from_cells({"mon": "09:00-17:00"}, r)
        self.assertEqual(hours["mon"], [["09:00", "17:00"]])
        self.assertEqual(hours["tue"], [])

    def test_unreadable_day_is_skipped_with_warning(self):
        r = g.ImportReport()
        hours = g.hours_from_cells({"mon": "soon", "tue": "09:00-17:00"}, r)
        self.assertNotIn("mon", hours)
        self.assertTrue(any("mon hours skipped" in w for w in r.warnings))


class ApiHoursTests(unittest.TestCase):
    def test_periods(self):
        periods = json.loads(API_PATH.read_text())["regularHours"]["periods"]
        hours = g.hours_from_periods(periods, g.ImportReport())
        self.assertEqual(hours["mon"], [])
        self.assertEqual(hours["tue"], [["10:00", "19:00"]])
        self.assertEqual(hours["wed"], [["10:00", "13:30"], ["14:30", "19:00"]])
        self.assertEqual(hours["fri"], [["18:00", "02:00"]])  # past midnight, kept on the opening day
        self.assertEqual(hours["sat"], [["00:00", "23:59"]])  # 00:00 to 00:00 next day = 24 h

    def test_close_at_24_00(self):
        p = [{"openDay": "MONDAY", "openTime": {"hours": 9}, "closeDay": "MONDAY", "closeTime": {"hours": 24}}]
        self.assertEqual(g.hours_from_periods(p, g.ImportReport())["mon"], [["09:00", "00:00"]])


class CategoryTests(unittest.TestCase):
    RULES = g.load_rules()

    def test_matches(self):
        cases = {
            "Italian restaurant": ("restaurant", None),
            "Pizza restaurant": ("restaurant", None),
            "Coffee shop": ("cafe", None),
            "Dentist": ("dental-clinic", None),
            "Plumber": ("contractor-home-services", "Plumber"),
            "Hair salon": ("salon-spa", None),
            "Gift shop": ("ecommerce-boutique", None),
            "Personal trainer": ("gym-fitness", None),
            "Spanish restaurant": ("restaurant", None),  # "spa" must not match inside "Spanish"
            "Photography studio": ("photographer", None),
        }
        for name, (category, schema) in cases.items():
            with self.subTest(name):
                got = g.map_category(name, self.RULES)
                self.assertEqual((got[0], got[1], got[2]), (category, schema, True))

    def test_fallback(self):
        self.assertEqual(g.map_category("Dog groomer", self.RULES), ("generic-local-business", None, False))

    def test_every_rule_targets_a_real_category(self):
        for rule in self.RULES["rules"]:
            self.assertIn(rule["category"], v.CATEGORIES)
        self.assertIn(self.RULES["fallback"], v.CATEGORIES)

    def test_label_from_id(self):
        self.assertEqual(g.category_label_from_id("categories/gcid:italian_restaurant"), "Italian restaurant")


class ReadingTests(unittest.TestCase):
    def rows_for(self, path: Path) -> list[dict]:
        kind, rows = g.read_export(path)
        self.assertEqual(kind, "table")
        return rows

    def test_csv_fixture(self):
        rows = self.rows_for(CSV_PATH)
        self.assertEqual([r["Business name"] for r in rows], ["Marigold Kitchen", "Northside Plumbing & Gas", "Wag & Wash"])
        self.assertEqual(rows[0]["Friday hours"], "12:00-15:00, 17:30-23:00")  # quoted comma kept

    def test_encodings_and_delimiters(self):
        base = csv_rows()
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            variants = {
                "semicolon.csv": write_table(d / "semicolon.csv", base, delimiter=";", newline="\r\n"),
                "tabs.tsv": write_table(d / "tabs.tsv", base, delimiter="\t"),
                "bom.csv": write_table(d / "bom.csv", base, encoding="utf-8-sig"),
                "utf16.tsv": write_table(d / "utf16.tsv", base, delimiter="\t", encoding="utf-16"),
                "cp1252.csv": write_table(d / "cp1252.csv", base, encoding="cp1252"),
            }
            for name, path in variants.items():
                with self.subTest(name):
                    rows = self.rows_for(path)
                    self.assertEqual(len(rows), 3)
                    self.assertEqual(rows[1]["Business name"], "Northside Plumbing & Gas")
                    self.assertEqual(rows[0]["Locality"], "London")

    def test_non_ascii_survives(self):
        base = csv_rows()
        base[1][1] = "Café Lumière"
        with tempfile.TemporaryDirectory() as d:
            for enc in ("utf-8", "utf-8-sig", "utf-16", "cp1252"):
                path = write_table(Path(d) / f"{enc}.csv", base, encoding=enc)
                self.assertEqual(self.rows_for(path)[0]["Business name"], "Café Lumière", enc)

    def test_xlsx_shared_and_inline_strings(self):
        with tempfile.TemporaryDirectory() as d:
            for shared in (True, False):
                path = write_xlsx(Path(d) / f"s{shared}.xlsx", [("Businesses", csv_rows())], shared=shared)
                rows = self.rows_for(path)
                self.assertEqual(len(rows), 3, shared)
                self.assertEqual(rows[0]["Business name"], "Marigold Kitchen")
                self.assertEqual(rows[0]["Friday hours"], "12:00-15:00, 17:30-23:00")

    def test_xlsx_picks_the_sheet_with_google_headers(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_xlsx(Path(d) / "two.xlsx", [("Read me", [["Instructions"], ["Do not edit"]]), ("Data", csv_rows())])
            self.assertEqual(len(self.rows_for(path)), 3)

    def test_header_row_after_junk_lines(self):
        base = [["Exported from Business Profile"], [""], *csv_rows()]
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(len(self.rows_for(write_table(Path(d) / "x.csv", base))), 3)

    def test_api_json_shapes(self):
        loc = json.loads(API_PATH.read_text())
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            for name, payload in {"one.json": loc, "list.json": [loc, loc], "wrapped.json": {"locations": [loc]}}.items():
                kind, items = g.read_export(write_json(d / name, payload))
                self.assertEqual(kind, "api", name)
                self.assertEqual(items[0]["title"], "Barro & Luz")

    def test_rejects_other_json(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                g.read_export(write_json(Path(d) / "business.json", {"name": "X", "category": "cafe"}))

    def test_rejects_a_table_without_a_name_column(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_table(Path(d) / "x.csv", [["Foo", "Bar"], ["1", "2"]])
            with self.assertRaises(ValueError):
                g.build_result(path, None, None)


class MappingTests(unittest.TestCase):
    def build(self, selector, existing=None, prefer=False, path=CSV_PATH):
        return g.build_result(path, selector, existing, prefer)

    def test_restaurant_row(self):
        final, report, validation, meta = self.build("FLK01")
        self.assertEqual(validation.errors, [])
        self.assertEqual(meta["code"], "FLK01")
        self.assertEqual(final["name"], "Marigold Kitchen")
        self.assertEqual(final["category"], "restaurant")
        self.assertEqual(final["category_label"], "Indian restaurant")
        self.assertEqual(
            final["address"],
            {
                "street": "27 Fenwick Lane",
                "locality": "London",
                "region": "Greater London",
                "postal_code": "E8 4QT",
                "country": "GB",
            },
        )
        self.assertEqual(final["phone"], "+442079460321")
        self.assertEqual(final["domain"], "marigold-kitchen.example")
        self.assertEqual(final["geo"], {"lat": 51.5451, "lng": -0.0553})
        self.assertEqual(final["hours"]["mon"], [])
        self.assertEqual(final["hours"]["fri"], [["12:00", "15:00"], ["17:30", "23:00"]])
        self.assertEqual(final["facts"]["google_categories"], ["Indian restaurant", "Goan restaurant", "Takeaway"])
        self.assertEqual(final["facts"]["attributes"], ["Wheelchair accessible entrance"])
        self.assertEqual(final["facts"]["opening_date"], "2019-04")
        self.assertEqual(final["imported_from"]["source"], "google-business-profile")
        self.assertEqual(final["imported_from"]["file"], "locations.csv")

    def test_reports_what_it_skipped(self):
        _, report, _, _ = self.build("FLK01")
        skipped = " ".join(report.not_imported)
        self.assertIn("3 photo link(s)", skipped)
        self.assertIn("special hours", skipped)
        self.assertIn("labels", skipped)
        self.assertIn("additional phone numbers", skipped)
        self.assertTrue(any("[UPDATED]" in w for w in report.warnings))
        self.assertNotIn("Logo", report.ignored_columns)

    def test_no_image_urls_or_reviews_in_the_result(self):
        final, *_ = self.build("FLK01")
        text = json.dumps(final)
        self.assertNotIn("googleusercontent", text)
        self.assertNotIn("images", final)
        for forbidden in ("review", "rating", "aggregateRating"):
            self.assertNotIn(forbidden, text.lower())

    def test_social_website_goes_to_socials(self):
        final, report, _, _ = self.build("2")
        self.assertNotIn("domain", final)
        self.assertEqual(final["socials"], {"facebook": "https://www.facebook.com/northsideplumbing"})
        self.assertTrue(any("social profile" in n for n in report.notes))

    def test_trade_gets_a_specific_schema_type_and_hours(self):
        final, *_ = self.build("Northside")
        self.assertEqual(final["category"], "contractor-home-services")
        self.assertEqual(final["decisions"]["schema_type"], "Plumber")
        self.assertEqual(final["hours"]["mon"], [["07:00", "17:00"]])
        self.assertEqual(final["hours"]["fri"], [["18:00", "02:00"]])
        self.assertEqual(final["hours"]["sat"], [["00:00", "23:59"]])
        self.assertEqual(final["hours"]["sun"], [])
        self.assertEqual(final["address"]["country"], "AU")
        self.assertEqual(final["phone"], "+61491570156")

    def test_unmatched_category_warns_and_falls_back(self):
        final, report, _, _ = self.build("3")
        self.assertEqual(final["category"], "generic-local-business")
        self.assertEqual(final["category_label"], "Dog groomer")
        self.assertTrue(any("Dog groomer" in w for w in report.warnings))
        self.assertNotIn("hours", final)  # no hours at all in the row: unknown, not "closed"

    def test_api_location(self):
        final, report, validation, _ = self.build(None, path=API_PATH)
        self.assertEqual(validation.errors, [])
        self.assertEqual(final["name"], "Barro & Luz")
        self.assertEqual(final["category"], "ecommerce-boutique")
        self.assertEqual(final["category_label"], "Gift shop")
        self.assertEqual(final["phone"], "+351210000000")
        self.assertEqual(final["domain"], "barroeluz.example")
        self.assertEqual(final["languages"], ["pt"])
        self.assertEqual(final["geo"], {"lat": 38.7117, "lng": -9.144})
        self.assertEqual(final["socials"]["google_maps"], "https://maps.google.com/?cid=123456789")
        self.assertEqual(final["facts"]["opening_date"], "2021-05")
        self.assertEqual(final["hours"]["wed"], [["10:00", "13:30"], ["14:30", "19:00"]])
        self.assertTrue(any("special hours" in s for s in report.not_imported))

    def test_api_service_area_business_has_no_address(self):
        loc = {
            "title": "Mobile Vet",
            "serviceArea": {
                "businessType": "CUSTOMER_LOCATION_ONLY",
                "places": {"placeInfos": [{"placeName": "Leeds"}, {"placeName": "York"}]},
            },
            "storefrontAddress": {"regionCode": "GB", "addressLines": ["1 Hidden Street"]},
            "phoneNumbers": {"primaryPhone": "+44 113 496 0000"},
        }
        with tempfile.TemporaryDirectory() as d:
            final, *_ = g.build_result(write_json(Path(d) / "loc.json", loc), None, None)
        self.assertEqual(final["service_area"], ["Leeds", "York"])
        self.assertNotIn("address", final)

    def test_permanently_closed_is_flagged(self):
        loc = {"title": "Gone Cafe", "openInfo": {"status": "CLOSED_PERMANENTLY"}}
        with tempfile.TemporaryDirectory() as d:
            _, report, _, _ = g.build_result(write_json(Path(d) / "loc.json", loc), None, None)
        self.assertTrue(any("PERMANENTLY CLOSED" in w for w in report.warnings))


class SelectionTests(unittest.TestCase):
    def test_several_locations_need_a_choice(self):
        with self.assertRaises(g.Ambiguous) as ctx:
            g.build_result(CSV_PATH, None, None)
        self.assertIn("3 locations", str(ctx.exception))
        self.assertIn("FLK02", str(ctx.exception))

    def test_by_number_code_and_name(self):
        for selector in ("1", "flk01", "marigold"):
            _, _, _, meta = g.build_result(CSV_PATH, selector, None)
            self.assertEqual(meta["name"], "Marigold Kitchen", selector)

    def test_ambiguous_or_unknown_name(self):
        for selector in ("9", "zzz", "a"):  # "a" matches several names
            with self.subTest(selector), self.assertRaises(g.Ambiguous):
                g.build_result(CSV_PATH, selector, None)


class MergeTests(unittest.TestCase):
    EXISTING = {
        "name": "Marigold Kitchen",
        "category": "restaurant",
        "phone": "+442079460999",
        "tagline": "Goan home cooking",
        "address": {"street": "27 Fenwick Lane", "country": "GB"},
        "hours": {},
        "decisions": {"cta": {"label": "Book a table"}, "design": {"direction": "broadsheet"}},
        "facts": {"cuisine": ["Goan"]},
    }

    def test_fill_gaps_and_keep_existing(self):
        final, report, validation, _ = g.build_result(CSV_PATH, "FLK01", copy.deepcopy(self.EXISTING))
        self.assertEqual(validation.errors, [])
        self.assertEqual(final["phone"], "+442079460999")  # kept
        self.assertEqual(final["tagline"], "Goan home cooking")
        self.assertEqual(final["decisions"]["design"], {"direction": "broadsheet"})
        self.assertEqual(final["facts"]["cuisine"], ["Goan"])
        self.assertEqual(final["address"]["locality"], "London")  # gap filled
        self.assertEqual(final["hours"]["tue"], [["17:30", "22:30"]])
        self.assertIn("address.locality", report.filled)
        self.assertIn("hours", report.filled)
        conflict = next(c for c in report.conflicts if c["path"] == "phone")
        self.assertEqual((conflict["existing"], conflict["google"]), ("+442079460999", "+442079460321"))

    def test_prefer_google_replaces_differences(self):
        final, report, _, _ = g.build_result(CSV_PATH, "FLK01", copy.deepcopy(self.EXISTING), prefer_google=True)
        self.assertEqual(final["phone"], "+442079460321")
        self.assertEqual(report.conflicts, [])
        self.assertIn("phone", report.replaced)
        self.assertEqual(final["tagline"], "Goan home cooking")  # Google has no tagline: untouched

    def test_second_import_changes_nothing(self):
        first, *_ = g.build_result(CSV_PATH, "FLK01", None)
        second, report, _, _ = g.build_result(CSV_PATH, "FLK01", copy.deepcopy(first))
        self.assertEqual(report.conflicts, [])
        self.assertEqual(report.filled, [])
        first.pop("imported_from"), second.pop("imported_from")
        self.assertEqual(first, second)

    def test_translations_and_images_are_never_touched(self):
        existing = {
            "name": "Barro",
            "languages": ["pt", "en"],
            "translations": {"en": {"tagline": "x"}},
            "images": [{"src": "public/images/a.jpg", "alt": "A"}],
        }
        final, *_ = g.build_result(API_PATH, None, copy.deepcopy(existing))
        self.assertEqual(final["translations"], existing["translations"])
        self.assertEqual(final["images"], existing["images"])
        self.assertEqual(final["languages"], ["pt", "en"])


class CliTests(unittest.TestCase):
    def run_cli(self, *args, cwd=None):
        return subprocess.run([sys.executable, str(SCRIPTS / "import_gbp.py"), *args], capture_output=True, text=True, cwd=cwd)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            res = self.run_cli(str(CSV_PATH), "--location", "1", "--out", str(Path(d) / "business.json"))
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertIn("dry run", res.stdout)
            self.assertFalse((Path(d) / "business.json").exists())

    def test_write_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "business.json"
            res = self.run_cli(str(CSV_PATH), "--location", "FLK01", "--out", str(out), "--write")
            self.assertEqual(res.returncode, 0, res.stderr)
            data = json.loads(out.read_text())
            self.assertEqual(data["phone"], "+442079460321")
            self.assertEqual(data["schema_version"], 1)
            self.assertEqual(list(data)[:3], ["schema_version", "name", "slug"])
            # a second run onto the same file is a no-op
            again = self.run_cli(str(CSV_PATH), "--location", "FLK01", "--out", str(out), "--write", "--json")
            self.assertEqual(json.loads(again.stdout)["report"]["conflicts"], [])
            # several locations and none chosen -> exit 2 with the list on stderr
            res = self.run_cli(str(CSV_PATH), "--out", str(Path(d) / "x.json"), "--write")
            self.assertEqual(res.returncode, 2)
            self.assertIn("FLK03", res.stderr)
            self.assertFalse((Path(d) / "x.json").exists())
            self.assertEqual(self.run_cli(str(Path(d) / "missing.csv")).returncode, 2)

    def test_unreadable_files_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            junk = Path(d) / "junk.xlsx"
            junk.write_bytes(b"PK not really a zip")
            self.assertEqual(self.run_cli(str(junk)).returncode, 2)

    def test_invalid_result_is_not_written(self):
        rows = csv_rows()
        rows[1][rows[0].index("Business name")] = "Bad Domain"
        rows[1][rows[0].index("Primary phone")] = "not a number"
        with tempfile.TemporaryDirectory() as d:
            path = write_table(Path(d) / "bad.csv", rows[:2])
            out = Path(d) / "business.json"
            res = self.run_cli(str(path), "--out", str(out), "--write")
            self.assertEqual(res.returncode, 1)
            self.assertFalse(out.exists())

    def test_json_output(self):
        res = self.run_cli(str(API_PATH), "--json")
        data = json.loads(res.stdout)
        self.assertTrue(data["ok"])
        self.assertFalse(data["written"])
        self.assertEqual(data["business"]["name"], "Barro & Luz")


class EndToEndTests(unittest.TestCase):
    def test_import_then_sync_produces_a_site_data_set(self):
        with tempfile.TemporaryDirectory() as d:
            site = Path(d) / "site"
            (site / "src").mkdir(parents=True)
            write_json(site / "package.json", {"name": "x", "dependencies": {}})
            final, _, validation, _ = g.build_result(CSV_PATH, "FLK01", None)
            final["decisions"] = {"design": {"direction": "broadsheet", "palette": "saffron-ink"}}
            write_json(site / "business.json", final)
            self.assertEqual(validation.errors, [])
            refs = SCRIPTS.parent / "references"
            out = sync.sync(site, refs / "palettes.json", refs / "directions.json")
            self.assertIn("src/data/site.json", out["written"])
            data = json.loads((site / "src/data/site.json").read_text())
            self.assertEqual(data["business"]["name"], "Marigold Kitchen")
            self.assertEqual(data["contact"]["tel"]["href"], "tel:+442079460321")
            self.assertEqual(data["business"]["category_label"], "Indian restaurant")
            self.assertEqual(data["seo"]["title"], "Marigold Kitchen · Indian restaurant in London")
            self.assertNotIn("aggregateRating", data["jsonld"])
            self.assertEqual(data["jsonld"]["openingHoursSpecification"][0]["dayOfWeek"], ["Tuesday", "Wednesday", "Thursday"])

    def test_imported_file_validates_cleanly(self):
        final, *_ = g.build_result(API_PATH, None, None)
        _, report = v.normalize(final)
        self.assertEqual(report.errors, [])


if __name__ == "__main__":
    unittest.main()
