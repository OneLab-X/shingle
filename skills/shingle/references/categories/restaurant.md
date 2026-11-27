# Category: restaurant

Sit-down restaurants, bistros, takeaways with seating, food halls stalls with a menu.

- **Audience:** locals deciding where to eat tonight (on a phone, often walking), visitors
  searching "<cuisine> near me", groups planning a booking.
- **Tone options:** Warm and neighbourly (default) · Refined and quiet · Bold and playful.
- **Schema type:** `Restaurant` (+ `servesCuisine`, `hasMenu`, `priceRange` from facts).
- **Default pages:** single page. Multi-page only with a long menu (>40 items), events or
  private dining.
- **Primary CTA options:** Book a table (default when bookings are taken) · Call us · Order
  online (only with a real ordering link) · Get directions (walk-in only).

## Required sections
1. Hero: name, cuisine + neighbourhood, today's hours or open status, primary CTA.
2. Menu (or menu highlights) from `facts.menu`, with real prices or a TODO per missing price.
3. Hours + location: full hours table, address, map (click-to-load), transport/parking note if
   provided.
4. Booking/contact: how to book (phone, WhatsApp, booking link), group/large-party policy if given.

## Optional sections (rank by fit)
About/story (from `facts.story`) · Dietary and allergens note · FAQ (from `facts.faq`) ·
Private dining/events · Gallery (owner photos only) · Press quotes (only with source links
the owner provides) · Gift vouchers (only with a real link).

## Category questions (ask at most 4, skip any answered)
- "Do you take bookings?" Yes by phone (Recommended if no link) / Yes, online (ask for link) /
  Walk-ins only.
- "Show the full menu or highlights?" Highlights, 8-12 dishes (Recommended: menus change) /
  Full menu / Link a PDF the owner provides.
- "Dietary labels on dishes?" Yes: V, VG, GF where the owner marks them (Recommended) / No.
- "Anything special about the place?" Free text: story, chef, sourcing. Use only what they say.

## Imagery
Food and room photos sell restaurants, so plan slots for them: hero (room or signature dish,
3:2), 3-6 dish photos (1:1 or 4:5). Until real photos arrive use `PlaceholderImage` with the
exact dish name. Typographic layouts (big menu typography) work well with no photos at all.
Never use stock food photos: visitors notice, and it misrepresents the food.

## Never invent
Prices · dishes · reviews or star ratings · awards, guides, "as seen in" · chef names or
biographies · opening year · "best <cuisine> in <city>" claims · allergen guarantees ·
sourcing claims (organic, local farms) · delivery partners.

## Design fit
Directions: `broadsheet` (menu as newspaper columns), `handmade` (family-run, café-like),
`quiet-luxury` (fine dining). Palettes: `saffron-ink`, `olive-grove`, `espresso-cream`,
`terracotta-sun`.

## Copy notes
- Lead with what and where: "Goan home cooking in Hackney" beats "Welcome to Marigold".
- Menu descriptions: ingredients and method in plain words, no adjectives stacked
  ("slow-cooked pork, vinegar, Kashmiri chilli" not "mouth-watering, delectable").
- Prices: one consistent format with currency symbol; dietary keys explained once.
- Put today's hours near the top; it is the most common question.
