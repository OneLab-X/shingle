# Category: contractor-home-services

Plumbers, electricians, builders, roofers, HVAC, painters, landscapers, cleaners, locksmiths,
handypeople: anyone who comes to the customer.

- **Audience:** homeowners with a problem now (burst pipe, no power: on a phone, stressed) and
  homeowners planning a job (comparing quotes). Property managers.
- **Tone options:** Confident and direct (default) · Friendly and local · Premium and precise.
- **Schema type:** most specific of `Plumber`, `Electrician`, `RoofingContractor`,
  `HVACBusiness`, `Locksmith`, `HousePainter`, `MovingCompany`, `GeneralContractor`; else
  `HomeAndConstructionBusiness`. Set `decisions.schema_type`. Use `areaServed` from
  `service_area`.
- **Default pages:** single page. Multi-page when there are more than 6 distinct services (one
  page per service helps local SEO).
- **Primary CTA options:** Call now (default for emergency trades) · Get a free quote (only if
  quotes are free: ask) · Send photos on WhatsApp.

## Required sections
1. Hero: trade + service area in the headline, phone number large, primary CTA, emergency
   availability if real.
2. Services: the owner's list, each with what it covers.
3. Service area: list of suburbs/towns from `service_area` (no map for service-area businesses
   without a public address).
4. How it works / what to expect: only from `facts.process`.
5. Contact/quote: call, WhatsApp, quote form via a form service (endpoint stays a TODO).

## Optional sections (rank by fit)
Licence and insurance (numbers only from the owner) · Recent jobs gallery (owner photos) ·
FAQ · Guarantees/warranties (only stated ones) · Payment methods · Reviews (owner-supplied
quotes with names and permission only).

## Category questions (ask at most 4, skip any answered)
- "Do you offer emergency call-outs?" Yes, 24/7 / Yes, extended hours / No.
- "Are quotes free?" Yes (Recommended label "Free quote" only if yes) / Call-out fee applies /
  Depends on the job.
- "Licence/registration number to display?" Enter it / Leave a TODO (Recommended if unsure)
  / Not required in my area.
- "How should quote requests arrive?" Phone or WhatsApp only (Recommended) / Form to email via
  Web3Forms or Formspree.

## Imagery
Real jobs beat everything: van, team at work, before/after of their own jobs (owner photos
only). Without photos, lean on bold type, numerals and icons. Never stock "smiling plumber"
photos, never other companies' work.

## Never invent
Licence or registration numbers · insurance cover amounts · "fully licensed/insured" unless
stated · years in business · number of jobs or customers · response times ("within 1 hour") ·
prices or call-out fees · guarantees · reviews or ratings · trade association logos.

## Design fit
Directions: `swiss-grid` (default; numbered services), `poster` (bold, urgent), `handmade`
(gardeners, cleaners). Palettes: `safety-orange`, `blueprint`, `ember-steel`, `main-street`.

## Copy notes
- Headline = trade + place: "Plumbing and gas fitting across Newcastle and Lake Macquarie".
- Phone number visible without scrolling on phones; tap-to-call everywhere.
- Service descriptions say what problem it fixes ("No hot water? We repair and replace...").
- If no public address, never show a map pin; show the service area list instead.
