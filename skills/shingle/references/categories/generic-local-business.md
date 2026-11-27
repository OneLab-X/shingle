# Category: generic-local-business

Fallback for anything without its own category: accountants, tailors, repair shops, driving
schools, tutors, vets, florists, printers, car washes, coworking spaces, and so on.
When used, tell the user which category was chosen and why.

- **Audience:** locals with a specific need searching "<service> near me", existing customers
  looking for hours and contact details.
- **Tone options:** Friendly and plain (default) · Confident and direct · Calm and professional.
- **Schema type:** the most specific schema.org `LocalBusiness` subtype that fits (e.g.
  `AccountingService`, `AutoRepair`, `Florist`, `VeterinaryCare`, `ChildCare`,
  `DrivingSchool` via `decisions.schema_type`); else `LocalBusiness`.
- **Default pages:** single page.
- **Primary CTA options:** Call us (default) · Get directions · Email us · Book (real link only).

## Required sections
1. Hero: what the business does + where, the main CTA.
2. Services/products from facts.
3. Hours, address, map (or service area).
4. Contact.

## Optional sections (rank by fit)
About · How it works (from facts) · Prices (only stated) · FAQ · Gallery · Team.

## Category questions (ask at most 4, skip any answered)
- "What do customers most often need from you?" Free text; becomes the hero and services.
- "Do customers visit you, or do you go to them?" They visit (map) / I travel (service area) / Both.
- "Show prices?" Yes, owner's prices / On request (Recommended if none).
- "Any licence, registration or membership to show?" Enter / None / TODO.

## Imagery
The place, the work, the people (owner photos). Without photos, rely on type and a palette
that suits the trade.

## Never invent
Anything not in the facts: prices, years in business, licences, memberships, client names,
reviews, guarantees, response times, awards.

## Design fit
Directions: `swiss-grid` (default), `handmade`, `clinical-calm`. Palettes: `main-street`,
`blueprint`, `meadow-hope`, `harbor-blue`, `civic-red`.

## Copy notes
Lead with the service and the place. If the category file does not cover something important
for this trade, ask one extra question rather than guessing.
