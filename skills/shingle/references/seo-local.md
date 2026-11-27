# Local SEO

Everything here is generated from `business.json` (via `src/data/site.json`), so the name,
address and phone (NAP) are typed once and appear identically everywhere.

## 1. NAP consistency
- One source: `site.json`. Components read it; never retype the address or phone in copy.
- Same format everywhere on the page: header, footer, contact section, JSON-LD.
- Phone: display in the local national format (`021 300 0000`) and link with E.164
  (`tel:+351213000000`). Never put a phone number only in an image.
- Address in the footer as a `<address>` element, on every page.
- Remind the owner in the handoff: the Google Business Profile, Facebook and directory listings
  must use the exact same name, address and phone.

## 2. JSON-LD (one block per page, in `<head>`)
Use the category's schema type (`@type`) from its category file. Mapping:

| category | @type | notes |
|---|---|---|
| restaurant | `Restaurant` | `servesCuisine`, `menu` (URL of menu section/page), `acceptsReservations` |
| cafe | `CafeOrCoffeeShop` | `servesCuisine`, `menu` |
| dental-clinic | `Dentist` | `medicalSpecialty` only if stated |
| law-firm | `LegalService` | `areaServed`, `knowsAbout` from stated practice areas. Individual lawyers: `Attorney` only with owner-provided names |
| salon-spa | `BeautySalon`, `HairSalon`, `NailSalon` or `DaySpa` | pick the most specific stated |
| gym-fitness | `ExerciseGym` (or `SportsActivityLocation`) | |
| real-estate | `RealEstateAgent` | `areaServed` |
| travel-agency | `TravelAgency` | |
| photographer | `ProfessionalService` with `"additionalType": "https://www.wikidata.org/wiki/Q33231"` | schema.org has no Photographer business type |
| contractor-home-services | most specific of `Plumber`, `Electrician`, `RoofingContractor`, `HVACBusiness`, `Locksmith`, `HousePainter`, `MovingCompany`, `GeneralContractor`; else `HomeAndConstructionBusiness` | `areaServed` for service-area businesses |
| ecommerce-boutique | `ClothingStore`, `JewelryStore`, `BookStore`, `GardenStore`, … else `Store` | online-only: `OnlineStore` (schema.org) |
| nonprofit | `NGO` | `nonprofitStatus` only if stated |
| generic-local-business | `LocalBusiness` or a more specific subtype if obvious | |

Template (omit any property whose value is unknown; never output empty strings or guesses):

```json
{
  "@context": "https://schema.org",
  "@type": "Restaurant",
  "@id": "https://marigoldkitchen.pt/#business",
  "name": "Marigold Kitchen",
  "url": "https://marigoldkitchen.pt/",
  "description": "Family-run Goan restaurant in Lisbon.",
  "telephone": "+351213000000",
  "email": "ola@marigoldkitchen.pt",
  "image": "https://marigoldkitchen.pt/og.png",
  "logo": "https://marigoldkitchen.pt/favicon.svg",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Rua da Rosa 112",
    "addressLocality": "Lisboa",
    "addressRegion": "Lisboa",
    "postalCode": "1200-389",
    "addressCountry": "PT"
  },
  "geo": { "@type": "GeoCoordinates", "latitude": 38.7139, "longitude": -9.1445 },
  "openingHoursSpecification": [
    { "@type": "OpeningHoursSpecification", "dayOfWeek": ["Tuesday","Wednesday","Thursday"], "opens": "12:00", "closes": "15:00" }
  ],
  "sameAs": ["https://instagram.com/marigoldkitchen"],
  "priceRange": "€€",
  "servesCuisine": ["Goan", "Indian"]
}
```

Rules:
- `openingHoursSpecification`: group days with identical ranges; one entry per range. Past
  midnight: `closes` is the next-day time (e.g. `"00:30"`); that is valid. Closed days: omit.
- Never output `aggregateRating`, `review`, `award`, `foundingDate`, `numberOfEmployees` unless
  the value is in `facts` and came from the owner. Ratings scraped from elsewhere: never.
- `priceRange` only from `facts.price_range`.
- `sameAs`: only the business's own profiles from `socials`.
- Multi-page sites: the full block on the home page; other pages reference it with
  `{"@id": "https://<domain>/#business"}` inside a `WebPage`'s `about`.
- Add a `BreadcrumbList` on inner pages of multi-page sites.
- FAQ section present: add `FAQPage` with exactly the visible questions and answers.

## 3. Head tags (every page)
```html
<title>{Page} · {Business name}, {locality}</title>     <!-- home: "{Business name} · {what} in {locality}" -->
<meta name="description" content="{140-160 chars, specific, includes locality}">
<link rel="canonical" href="https://{domain}{path}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{Business name}">
<meta property="og:title" content="{same as title}">
<meta property="og:description" content="{same as description}">
<meta property="og:url" content="https://{domain}{path}">
<meta property="og:image" content="https://{domain}/og.png">       <!-- 1200x630 -->
<meta property="og:image:alt" content="{Business name} — {what} in {locality}">
<meta property="og:locale" content="{lang_REGION, e.g. pt_PT}">
<meta name="twitter:card" content="summary_large_image">
<meta name="theme-color" content="{background}" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="{dark.background}" media="(prefers-color-scheme: dark)">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
```
- `og.png`: the template renders a typographic card (name, what, locality on the palette) to
  `public/og.png` at build time; swap for a real photo later (TODO in handoff).
- `<html lang="…">` set per language. Multi-language: see section 7.

## 4. Sitemap and robots
- `@astrojs/sitemap` with `site: "https://<domain>"` in `astro.config.mjs` writes
  `sitemap-index.xml`. If `domain` is unknown, set `site` to a TODO URL and flag it: the sitemap
  and canonical URLs are wrong until it is set.
- `public/robots.txt`:
  ```
  User-agent: *
  Allow: /
  Sitemap: https://<domain>/sitemap-index.xml
  ```

## 5. Map embed
- Default: a **click-to-load map** (privacy and speed): a static, styled SVG/CSS panel with the
  address and two links: "Open in Google Maps" (`https://www.google.com/maps/search/?api=1&query=<urlencoded name + address>`)
  and "Directions" (`https://www.google.com/maps/dir/?api=1&destination=<urlencoded address>`).
  A "Show map" button swaps in the iframe.
- Iframe (no API key needed):
  ```html
  <iframe title="Map showing {Business name} at {street}, {locality}"
    src="https://www.google.com/maps?q={urlencoded name + full address}&output=embed"
    width="600" height="400" style="border:0" loading="lazy"
    referrerpolicy="no-referrer-when-downgrade" allowfullscreen></iframe>
  ```
- If `socials.google_maps` exists, use it for the "Open in Google Maps" link.
- Service-area businesses without a public address: no map; list the areas served instead.

## 6. On-page basics
- One `h1` per page containing what + where ("Goan restaurant in Bairro Alto").
- Locality in the first paragraph, naturally. No keyword stuffing, no hidden text.
- Descriptive link text (no "click here"). Alt text describes the image, no "image of".
- Images: `astro:assets` `<Image>` with width/height (no layout shift), `loading="lazy"` below
  the fold, modern formats.

## 7. Multiple languages
Sites with 2+ `languages` have one copy of every page per language at `/<code>/…` (the code
lower-cased: `/pt/`, `/en/`, `/pt-br/`). `/` is a static redirect to the default language.
On **every** page, in `<head>`, list **all** languages including the page itself, plus `x-default`:
```html
<html lang="pt" dir="ltr">
<link rel="canonical" href="https://{domain}/pt/{path}">                 <!-- self-referencing, per language -->
<link rel="alternate" hreflang="pt" href="https://{domain}/pt/{path}">
<link rel="alternate" hreflang="en" href="https://{domain}/en/{path}">
<link rel="alternate" hreflang="x-default" href="https://{domain}/pt/{path}">   <!-- default language -->
<meta property="og:locale" content="pt_PT">
<meta property="og:locale:alternate" content="en_US">
```
- Alternates must be **absolute**, **reciprocal** (A lists B and B lists A) and point at the same
  page in the other language.
- Never canonical one language to another: each language page is its own canonical.
- The sitemap carries the alternates as `xhtml:link` (the template turns this on via the sitemap
  integration's `i18n` option).
- JSON-LD: same `@id` on every page, per-language `url`, `description` and `hasMenu`, and
  `knowsLanguage` listing the languages. Address, phone and hours are identical in every language
  (NAP consistency).
- Title, description, headings and alt text are translated; prices, phone numbers and the business
  name are not.
- The language switcher links carry `lang` and `hreflang` so assistive tech reads each label in its
  own language.
