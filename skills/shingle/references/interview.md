# Interview

Goal: collect the few decisions that change the site, in as few rounds as possible.

## How to ask
- Use the interactive question tool (AskUserQuestion). Max **4 questions per round**,
  **2-4 options** each, max **3 rounds** total.
- Put the recommended option first and add " (Recommended)" to its label. Recommend from the
  category file's defaults and what you already know (for example, a restaurant with only a
  phone number: recommend "Call to book").
- Every question must stand alone: say what it is for in the question text.
- The user can always pick "Other"; accept free text and map it to the closest decision.
- Use `multiSelect: true` only for features and contact methods.
- Before asking, drop questions that are answered in business.json `decisions`, inferable from
  the facts, or irrelevant to this category. Typical inferences:
  - Only one contact method given: that is the contact method. Do not ask.
  - One address and no service area: single location, no locations page.
  - Category file says "single page by default" and fewer than 5 sections: do not ask pages.
  - Languages: if all input is in one language and the address is in a monolingual country, use
    that language and do not ask. Ask only when the country is multilingual or the input mixes.
- After the last round, show a one-screen summary of decisions and continue without waiting
  unless something is contradictory.

## Round plan
Round 1 is always about **purpose**; round 2 about **content and features**; round 3 (only if
needed) about **category specifics** from the category file.

## Core question bank
Pick from these, then add the category file's questions. Keys are the `decisions` fields.

### goal / cta (round 1)
"What should most visitors do on the site?" Options from the category file's primary CTA list,
e.g. Book a table / Call now / Get a quote / Book an appointment / Visit the shop / Donate.
Store as `decisions.goal` and `decisions.cta {label, action}` where action is one of
`tel`, `mailto`, `whatsapp`, `booking-url`, `form`, `map`, `external`.

### pages (round 1)
"One scrolling page or separate pages?"
- Single page (Recommended for under ~6 sections): fastest to read on phones.
- Multi-page: Home, About, Services/Menu, Contact (+ category extras). Better for SEO on many services.

### tone (round 1)
"How should the words sound?" Offer the 3 tones from the category file's `Tone` line plus a
recommended one. Examples: Warm and neighbourly / Calm and reassuring / Confident and direct /
Refined and quiet / Playful.

### imagery (round 1)
"What images do we have?"
- I will add my own photos later (Recommended when none given): build with tasteful SVG/CSS
  placeholders sized for the real photos, each with a TODO.
- I have photos now: ask for a folder path; copy into `public/images/`; ask for alt text only
  if the subject is not obvious from the filename.
- No photos, keep it typographic: design leans on type, color and illustration.
Never offer stock-photo hotlinking or AI-generated photos of the real business, staff, or food.

### languages (round 2, only when not inferable)
"Which languages should the site be in?" Options: the local language(s) and English. The
language the owner wrote the facts in is the default (first in `languages`). If more than one:
the site gets `/<lang>/` routes, a language switcher and hreflang tags. Then ask once:
"Who writes the other languages?" Claude drafts and you review (Recommended) / I will write them.
With a draft, store it under `translations.<lang>` with `review: "draft"` (see `i18n.md`); the
site shows a visible review notice until the owner sets `review` to `"reviewed"`.

### contact_method (round 2, multiSelect)
"How should people reach you?" Options built from available facts: Phone call, WhatsApp, Email,
Contact form via a form service. If form is chosen, follow up with `form_service`:
Formspree / Web3Forms / Netlify Forms (only if deploying on Netlify). The endpoint ID stays a TODO.

### features (round 2, multiSelect)
"Which sections do you want?" Offer at most 4: the category's optional sections ranked by fit.
Common: Menu, Pricing, Gallery, Testimonials, FAQ, Blog/news, Team, Map.
- Testimonials: only with real quotes the owner provides (with name or initials and permission).
  Otherwise build the section empty with a TODO, or leave it out. Say this in the option text.
- Pricing / Menu: only real prices. Unknown prices become TODOs, never estimates.

### booking (round 2 or 3, when the CTA is booking)
"Do you already use a booking tool?" Options: Yes, I have a booking link (ask for it) / No,
people call or message to book (Recommended if no link given) / Email me requests.
Never embed a third-party booking widget without a real URL from the owner.

### category specifics (round 3)
From the category file's "Category questions" list. Ask at most 4. Skip any answered by facts.

## After the interview
Write all answers to `decisions` in business.json and re-run `validate_input.py --write`.
