# Importing a Google Business Profile export

Most owners already keep their name, address, phone, hours and description in Google. Import
them instead of retyping.

## Get the file
**Spreadsheet (what an owner can do):** sign in to [Business Profile Manager](https://business.google.com/manage/),
select the profile(s), then **Actions > Download > Businesses**, tick nothing else, choose a file
type and **Download**. Accepted: `.csv`, `.tsv`, `.xlsx` (comma, semicolon or tab separated; UTF-8,
UTF-16 or Windows-1252; Excel and Sheets exports both work).

**API JSON (developers and agencies):** the `Location` resource of the Business Information API
(`accounts.locations`): one location, a list, or `{"locations": [...]}`.

Not supported: Google Takeout (no documented Business Profile export there), scraping, reviews.

## Run it
```bash
python3 SK/scripts/import_gbp.py export.csv                 # dry run: shows what would be imported
python3 SK/scripts/import_gbp.py export.csv --location 2 --out business.json --write
```
- Several locations: it exits 2 and lists them; pick with `--location` (number, store code or part of
  the name).
- If `business.json` already exists it is filled, never overwritten: only empty fields change.
  Differences are listed as **kept your value, Google differs**; `--prefer-google` takes Google's value.
- Nothing is written without `--write`, or when the result is invalid.
- After it: `validate_input.py business.json --write`, then continue with the interview. Skip every
  question the import already answered.

## What is imported
| Google | business.json |
|---|---|
| Business name / `title` | `name` |
| Address lines 1-5, Locality (or Sub-locality), Administrative area, Postal code, Country/Region | `address.{street, locality, region, postal_code, country}` (`CUSTOMER_LOCATION_ONLY` businesses get no address) |
| Primary phone | `phone` (normalized to E.164 using the country) |
| Website | `domain` (host only; a Facebook/Instagram/... page goes to `socials` instead) |
| `<Day> hours` / `regularHours` | `hours` (split shifts, past midnight, 24 h; empty week = hours unknown, not "closed") |
| From the business / `profile.description` | `description` |
| Primary category | `category` (via `google-categories.json`), `category_label` (Google's wording), `decisions.schema_type` for specific trades |
| Additional categories | `facts.google_categories` |
| yes/no attributes ("Outdoor seating") | `facts.attributes` (the "yes" ones) |
| Opening date | `facts.opening_date` (not auto-published as `foundingDate`) |
| Latitude / Longitude | `geo` |
| `serviceArea` place names | `service_area` |
| `metadata.mapsUri`, social URLs in any column | `socials` |
| `languageCode` (API) | `languages` |

## What is deliberately NOT imported
- **Reviews and ratings**: never (the site must not display or mark up anyone's reviews unless the
  owner supplies real quotes with permission). Any review/rating column is reported and dropped.
- **Photos** (Logo, Cover, Other Photos): the URLs are counted and listed; nothing is downloaded or
  hotlinked. The owner adds their own files to `public/images/`.
- **Special hours** (holidays): add them to `hours_note` by hand.
- Labels, store/business code, Google Ads phone, additional phone numbers, service items, `[UPDATED]`
  columns (Google's suggested changes to the owner's data: review them in Business Profile first).
- **Email**: Business Profile does not store one, so ask for it.

## After the import: checks to make
- The **domain** Google lists is the *current* website, which may be the one being replaced. Confirm
  it is the domain the new site will use.
- A category with no rule falls back to `generic-local-business` with a warning: tell the user, and
  add a rule to `references/google-categories.json` (first matching keyword wins) if it recurs.
- `[UPDATED]`/`Google updates` warnings mean Google disagrees with the owner's data (e.g. changed
  hours). Imported values are the owner's; mention the difference in the handoff.

## Troubleshooting
- "no business name column found": the file is not the Business Profile download. Re-download, or
  check that the first sheet holds the data.
- Unmapped headers are listed under **ignored columns**. Header spellings were taken from Google's
  help pages; if a real export uses a header the importer does not know, add it to `FIELD_ALIASES`
  in `import_gbp.py` and a row to the test fixture.
- Hours that "look wrong": only `HH:MM-HH:MM` / `HH:MMAM-HH:MMPM` cells are read (Google's own
  format); anything else is skipped with a warning naming the day.
