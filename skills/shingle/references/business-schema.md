# business.json

The single source of truth for a Shingle site. Lives at the site root. Every key is optional
except `name` and `category`; leave unknowns out (never write guesses).
`validate_input.py --write` normalizes it in place.

```json
{
  "schema_version": 1,
  "name": "Marigold Kitchen",
  "slug": "marigold-kitchen",
  "category": "restaurant",
  "tagline": "Coastal Goan cooking in Lisbon",
  "description": "Family-run Goan restaurant. Fish curries, xacuti, bebinca.",
  "domain": "marigoldkitchen.pt",
  "address": {
    "street": "Rua da Rosa 112",
    "locality": "Lisboa",
    "region": "Lisboa",
    "postal_code": "1200-389",
    "country": "PT"
  },
  "geo": { "lat": 38.7139, "lng": -9.1445 },
  "phone": "+351213000000",
  "whatsapp": "+351913000000",
  "email": "ola@marigoldkitchen.pt",
  "hours": {
    "mon": [],
    "tue": [["12:00", "15:00"], ["19:00", "23:00"]],
    "wed": [["12:00", "15:00"], ["19:00", "23:00"]],
    "thu": [["12:00", "15:00"], ["19:00", "23:00"]],
    "fri": [["12:00", "15:00"], ["19:00", "00:30"]],
    "sat": [["19:00", "00:30"]],
    "sun": [["12:00", "16:00"]]
  },
  "hours_note": "Kitchen closes 30 minutes before closing time.",
  "socials": {
    "instagram": "https://instagram.com/marigoldkitchen",
    "google_maps": "https://maps.app.goo.gl/xxxx"
  },
  "languages": ["en", "pt"],
  "translations": { "pt": { "review": "draft", "tagline": "Cozinha caseira goesa em Hackney" } },
  "service_area": [],
  "images": [
    { "src": "public/images/dining-room.jpg", "alt": "Dining room with blue tiles", "subject": "Dining room",
      "width": 1600, "height": 1067, "status": "ok" }
  ],
  "facts": {
    "cuisine": ["Goan", "Indian"],
    "price_range": "€€"
  },
  "decisions": {
    "goal": "reservations",
    "cta": { "label": "Book a table", "action": "tel" },
    "pages": "single",
    "tone": "warm",
    "imagery": "svg-placeholders",
    "languages": ["en", "pt"],
    "contact_method": ["tel", "whatsapp", "map"],
    "form_service": null,
    "features": ["menu", "faq", "map"],
    "design": { "direction": "broadsheet", "palette": "saffron-ink" },
    "badge": true
  }
}
```

## Field rules
| Field | Rule |
|---|---|
| `name` | Exactly as the owner writes it (keep capitalization, accents, ampersands). |
| `category_label` | Optional human label used in titles and eyebrows ("Ceramics shop"). Defaults to the category's label. Translatable. |
| `slug` | Derived: lowercase ASCII, hyphens. Used for the folder name. |
| `category` | One of the file names in `categories/` without `.md`. |
| `domain` | Bare host, no scheme or path (`example.com`). Site URL is `https://<domain>`. |
| `timezone` | IANA name (`America/Chicago`). Optional for single-zone countries (inferred); needed in US, CA, AU, BR, MX, RU, ID, AR for the live "open now" status. |
| `address.country` | ISO 3166-1 alpha-2. Needed for phone normalization and JSON-LD. |
| `phone`, `whatsapp` | E.164 (`+` and digits). Display formatting happens at render time. |
| `hours` | Keys `mon`..`sun`; list of `[open, close]` 24h pairs. `[]` = closed. Missing key = unknown. A close earlier than open means past midnight. |
| `socials` | Full https URLs. Known keys: instagram, facebook, tiktok, x, linkedin, youtube, pinterest, threads, yelp, tripadvisor, google_maps, whatsapp_channel. |
| `images[].src` | Path inside the site project. Never a remote URL to someone else's image. |
| `images[].subject` | The page slot this photo fills: `<Photo slot="Dining room">` shows the image whose subject matches (case-insensitive). Not translated. |
| `images[].alt` | Confirmed alt text, at most 125 characters, one per image. Translated per language in `translations.<lang>.images[i].alt` (same position). |
| `images[].decorative` | `true` for a purely decorative picture: rendered with empty alt, so `alt` may be empty. |
| `images[].suggested_alt` | Claude's proposal until the owner confirms it; never published. Cleared by `import_images.py --apply-alt`. |
| `images[].status` | `needs-alt` (imported, alt not confirmed; the audit fails) or `ok`. |
| `images[].width`, `height` | Pixels as displayed, read from the file by `import_images.py`. Also `sha256` of the stored file, used to skip re-imports. |
| `facts` | Extra **verified** facts the owner stated (cuisine, specialties, licence numbers, founding year). Only facts in here may appear as claims on the site. |
| `decisions` | Interview and design answers. Present keys are not asked again on re-runs. |
| `decisions.badge` | `false` removes the "Built with Shingle" footer badge. |

## Multiple languages
`languages` lists the site's languages; the **first is the default** (it is what the top-level fields
are written in, and what `x-default` points at). Everything else lives in `translations`:

```json
"languages": ["pt", "en"],
"tagline": "Cerâmica pintada à mão",
"translations": {
  "en": {
    "review": "draft",
    "tagline": "Hand-painted ceramics",
    "facts": { "products": [{ "name": "Hand-painted tile", "price": "€18" }] }
  }
}
```
- `translations.<lang>` is an overlay: objects merge into the default-language data, arrays replace
  the original array whole (so list every item), anything missing falls back to the default language.
- `review`: `"draft"` (default) shows a visible "native speaker should review" notice on that
  language's pages; set `"reviewed"` once someone has checked the text.
- **Locked fields** must be identical in every language, and `validate_input.py` fails otherwise:
  `price`, `phone`, `whatsapp`, `email`, `url`, `href`, `booking_url`, `domain`, `slug`, `category`,
  and the `name` of people (under `team`, `staff`, `coaches`…). Dish and product names may be translated.
- Only keys that exist in the default language are used; unknown keys are ignored with a warning.

## Fields written by the Google Business Profile import
`import_gbp.py` adds these (see `google-business-profile.md`); the site only uses them if a page asks:
- `imported_from`: `{source, file, location, imported_at}`, a record of where the facts came from.
- `category_label`: Google's primary category wording, e.g. "Indian restaurant" (used in titles).
- `facts.google_categories`: primary + additional categories, verbatim.
- `facts.attributes`: attributes the owner answered "yes" to, verbatim ("Wheelchair accessible entrance").
- `facts.opening_date`: Google's opening date (`YYYY` / `YYYY-MM` / `YYYY-MM-DD`). It is **not** copied to
  JSON-LD `foundingDate`: say it on the site only if the owner confirms.
