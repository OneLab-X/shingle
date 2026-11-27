# Design directions

Pick **one** direction per site. Each is a complete system: type, spacing, shape, motion and one
**signature element** that makes the site recognisable. Build the signature element properly; it
is what keeps sites from looking alike.

Fonts are self-hosted with Fontsource packages (`@fontsource-variable/<name>` where it exists,
else `@fontsource/<name>`). No Google Fonts CDN: faster, and no third-party requests.
Tokens map to CSS variables in `src/styles/theme.css` (`--font-display`, `--font-body`,
`--space-unit`, `--radius`, `--measure`).

| id | Name | Best for | Avoid for |
|---|---|---|---|
| `broadsheet` | Broadsheet | restaurant, law-firm, nonprofit, cafe | gym-fitness |
| `swiss-grid` | Swiss Grid | contractor-home-services, real-estate, law-firm, generic | salon-spa |
| `handmade` | Handmade | cafe, restaurant, ecommerce-boutique, nonprofit | law-firm, dental-clinic |
| `quiet-luxury` | Quiet Luxury | salon-spa, ecommerce-boutique, real-estate, photographer | contractor-home-services |
| `clinical-calm` | Clinical Calm | dental-clinic, generic, law-firm | gym-fitness, photographer |
| `poster` | Poster | gym-fitness, cafe, contractor-home-services | dental-clinic, law-firm |
| `gallery` | Gallery | photographer, ecommerce-boutique, salon-spa | contractor-home-services |
| `wayfinder` | Wayfinder | travel-agency, nonprofit, real-estate | dental-clinic |
| `ledger` | Ledger | generic (bookkeeping, repairs, trades), law-firm, real-estate | salon-spa, gym-fitness |
| `postcard` | Postcard | nonprofit (heritage, tourism), travel-agency, cafe, ecommerce-boutique | law-firm, dental-clinic |

---

## broadsheet: Broadsheet
Newspaper-inspired, confident, text-forward.
- **Fonts:** Fraunces (display, optical size high, weight 600-800) + Source Serif 4 (body 400).
  UI labels: Source Serif 4 small caps, letter-spacing 0.06em.
- **Scale:** 1.333 (perfect fourth); h1 clamp(2.75rem, 7vw, 5.5rem). Body 1.125rem / 1.65.
- **Spacing:** 8px unit; sections 96-128px apart on desktop; 3-column text grid with 1px rules.
- **Shape:** radius 0. Rules (1px `text` at 20% opacity) instead of cards and shadows.
- **Motion:** none beyond 150ms color transitions.
- **Signature element:** a masthead hero: business name set huge across the full width, a thin
  double rule beneath, and a "dateline" row (neighbourhood · today's hours · phone) like a paper's
  front page. Section openers use a drop cap.

## swiss-grid: Swiss Grid
Rational, trustworthy, built for scanning services and numbers.
- **Fonts:** Archivo (display, 700-800, width 110 where supported) + IBM Plex Sans (body 400).
  Numerals: IBM Plex Sans tabular.
- **Scale:** 1.25; h1 clamp(2.5rem, 6vw, 4.75rem); tight tracking -0.02em on headings.
- **Spacing:** 4px unit, 12-column grid, generous gutters (24-32px). Everything aligns to it.
- **Shape:** radius 2px. Flat blocks of `surface`; borders, no shadows.
- **Motion:** 120ms; nothing animated on scroll.
- **Signature element:** oversized index numerals: services and process steps are numbered
  01, 02, 03 in 6-8rem `primary` digits that hang in the left grid column, with a visible hairline
  grid in the hero background.

## handmade: Handmade
Warm, crafted, personal. For places where the owner is the brand.
- **Fonts:** Young Serif (display 400) + Nunito Sans (body 400/700).
- **Scale:** 1.25; h1 clamp(2.5rem, 6vw, 4.5rem). Body 1.0625rem / 1.7.
- **Spacing:** 8px unit; slightly irregular rhythm (alternate 80/112px section gaps).
- **Shape:** radius 14-20px; one rotated (-2deg) element per section at most.
- **Motion:** gentle 200ms; underline "draws" on hover (respect reduced motion).
- **Signature element:** a hand-drawn SVG underline/scribble under the key word of each heading,
  and an opening-hours "stamp": a circular badge with the hours set on a path, reading
  "OPEN TODAY 8–4" (computed from `hours`).

## quiet-luxury: Quiet Luxury
Restraint, air, and precision. Fewer words, more space.
- **Fonts:** Cormorant Garamond (display 500-600, italic for accents) + Jost (body 400, UI 500
  uppercase with 0.14em tracking).
- **Scale:** 1.414; h1 clamp(2.75rem, 7vw, 6rem); body 1rem / 1.75, measure 60ch.
- **Spacing:** 8px unit; very generous (sections 128-160px), wide side margins.
- **Shape:** radius 0; hairline 1px frames inset 12px inside image placeholders.
- **Motion:** slow 400ms fades on hover only.
- **Signature element:** an inset hairline frame around the whole viewport on desktop (fixed 1px
  border 16px from the edge) and small-caps section labels set vertically in the margin.

## clinical-calm: Clinical Calm
Reassuring, legible, accessible first. For health and anxious visitors.
- **Fonts:** Figtree (display 600-700) + Atkinson Hyperlegible (body 400/700).
- **Scale:** 1.2; h1 clamp(2.25rem, 5vw, 3.75rem); body 1.125rem / 1.65 (larger than usual).
- **Spacing:** 8px unit; predictable 96px section gaps; max 2 columns.
- **Shape:** radius 12px; soft `surface` panels; focus rings 3px `primary`.
- **Motion:** minimal, 150ms.
- **Signature element:** a live "Open now / Opens at 9:00 tomorrow" status pill in the header,
  computed client-side from `hours` with a no-JS fallback showing today's hours, plus a sticky
  bottom bar on phones with Call and Book buttons.

## poster: Poster
Loud, energetic, high contrast. Built to be remembered.
- **Fonts:** Anton (display 400, uppercase) + Work Sans (body 400/600).
- **Scale:** 1.5; h1 clamp(3.5rem, 12vw, 9rem), line-height 0.9.
- **Spacing:** 4px unit; tight, blocky sections; full-bleed color bands.
- **Shape:** radius 0; thick 3-4px borders; offset solid shadows (6px 6px 0 `text`).
- **Motion:** marquee only, and only when reduced motion is off; otherwise static.
- **Signature element:** a diagonal (-4deg) marquee band crossing the page between hero and
  content, repeating the business's real offer words (from facts, e.g. "STRENGTH · BOXING ·
  OPEN 6AM"), never invented slogans.

## gallery: Gallery
Image-first; type steps back. For visual work.
- **Fonts:** Instrument Serif (display 400, italic accents) + Instrument Sans (body 400/500).
- **Scale:** 1.25; h1 clamp(2.5rem, 6vw, 5rem); captions 0.8125rem uppercase 0.08em.
- **Spacing:** 4px unit; images nearly edge to edge with 4-8px gutters.
- **Shape:** radius 0; no borders.
- **Motion:** 250ms image fade-in on load; keyboard-accessible lightbox.
- **Signature element:** an asymmetric masonry of image slots with numbered captions set in the
  margin ("03 — Wedding, Porto"), and a horizontally scrolling "contact sheet" strip on phones.
  With no images yet, slots are tinted SVG frames labelled with the shot to add.

## wayfinder: Wayfinder
Journeys, maps, places. Sense of movement.
- **Fonts:** Bricolage Grotesque (display 700, opsz high) + Literata (body 400).
- **Scale:** 1.333; h1 clamp(2.5rem, 6.5vw, 5rem).
- **Spacing:** 8px unit; sections connected vertically.
- **Shape:** radius 8px; ticket/stub shapes with notched corners for cards that must exist.
- **Motion:** route line draws on scroll (CSS scroll-driven animation, static under reduced motion).
- **Signature element:** a dotted SVG route line running down the left edge, linking section
  markers shaped like map pins or passport stamps, ending at the contact section.

## ledger: Ledger
Exact, plain-spoken, built on tables. For businesses that sell care with numbers and records.
- **Fonts:** Spline Sans Mono (display 600, labels, figures) + Newsreader (body 400, italic for notes).
- **Scale:** 1.2; h1 clamp(2.25rem, 5.5vw, 4rem). Body 1.0625rem / 1.7; numerals always tabular.
- **Spacing:** 8px unit; one 28px baseline so ruled lines and text line up; sections 64-96px apart.
- **Shape:** radius 0; 1px `border` rules, no shadows, no cards.
- **Motion:** 100ms color changes only.
- **Signature element:** ruled-paper sections: a faint horizontal ruling in `border`, a double
  vertical margin rule on the left, and a folio label ("Folio 02 · Services") opening each section.
  Services, hours and process steps are real `<table>`s: right-aligned tabular figures, dotted
  leaders between label and value, and a closing "total" row built only from facts (e.g. days open).

## postcard: Postcard
Retro travel, hand-stamped and friendly. For places people visit, send a card from, or love.
- **Fonts:** Bevan (display 400) + Josefin Sans (body 400/600, UI uppercase with 0.12em tracking).
- **Scale:** 1.333; h1 clamp(2.75rem, 8vw, 6rem). Body 1.125rem / 1.65.
- **Spacing:** 8px unit; generous, with one slightly rotated (-1.5deg) card per section at most.
- **Shape:** radius 6px; 2px borders; stamp edges cut with a radial-gradient mask; air-mail
  stripes (diagonal `primary` / `accent` bands) as the only decoration.
- **Motion:** 180ms hover lifts; nothing animates on scroll.
- **Signature element:** the hero is a postcard: a perforated postage stamp holding the monogram,
  a round postmark whose text (set on an SVG path) reads the real place and opening days from
  facts, and an address block with ruled lines for the contact details. Detail cards are
  smaller cards edged in air-mail stripes.

---

## Anti-slop list (never ship these)
- Default purple/indigo-to-pink gradients, "aurora" blobs, glassmorphism cards on gradients.
- The generic layout: centered hero with headline + subhead + two buttons, then a row of 3
  identical icon cards, then a testimonial carousel. If the page looks like this, redo it with
  the direction's signature element.
- Lorem ipsum or vague filler ("We are passionate about excellence", "Your trusted partner",
  "Welcome to our website"). Write specific copy from facts or a TODO.
- Emoji used as icons, or icon-font soup. Use simple inline SVG icons (stroke 1.5-2) or none.
- Fake social proof: invented testimonials, star ratings, "500+ happy clients", award badges,
  "as seen in" logo rows.
- Stock photo hotlinks, AI photos of the real business, or people images posing as the team.
- Inter + default Tailwind gray on white as the whole design. Every direction sets its own fonts.
- Centered body text longer than 2 lines; text over busy images without a scrim.
- Auto-playing carousels, parallax, scroll-jacking, cursor effects.
- Cookie banners when nothing sets cookies (Shingle sites set none by default).
- "Learn more" buttons with no destination; buttons that go to `#`.
- Shadow + gradient + border + rounded on the same element.

## Pairing directions with palettes
Directions are palette-agnostic, but these pairs are tested: broadsheet + any palette with a
dark `text` and warm `background`; poster + palettes tagged `bold`; quiet-luxury + `muted`
or `elegant`; clinical-calm + `calm` or `clean`; ledger + `trustworthy` or `muted` (try `ledger-green`);
postcard + `warm` or `playful` (try `postcard-stamp`). Avoid poster with `calm` palettes.
Need strict accessibility? `high-contrast-ink` clears 7:1 and pairs with any direction.
