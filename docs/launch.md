# Launch kit

## Before launch

- [x] GitHub owner set to `OneLab-X` (repo `OneLab-X/shingle`)
- [x] Conduct contact set in `CODE_OF_CONDUCT.md`
- [ ] Settings → Pages → Source: **GitHub Actions**; run the **Gallery** workflow once and check every live preview link in the README
- [ ] Settings → General → Social preview: upload `docs/media/social-preview.png`
- [ ] Add the repo topics (below), description and website URL (the gallery)
- [ ] Enable Discussions (the issue template links to them)
- [ ] Record the demo GIF and replace `docs/media/demo-placeholder.svg` in the README
- [ ] Fresh-machine test: `/plugin marketplace add OneLab-X/shingle`, `/plugin install shingle@shingle`, `/shingle` with a real local business (with the owner's permission)
- [ ] Tag `v0.1.0` and publish a GitHub release with the changelog and 3 screenshots

## Repository settings

**Description:** Claude Code plugin: business details in, distinctive production-ready website out. Interviews you, picks an accessible design, builds an Astro site, audits it, ships it.

**Topics:**

```bash
gh repo edit OneLab-X/shingle --add-topic claude-code,claude-code-plugin,claude,ai-agents,website-generator,static-site,astro,tailwindcss,local-business,small-business,local-seo,schema-org,accessibility,wcag
```

## Social preview image

- Size **1280×640** PNG (GitHub's recommended size; minimum 640×320), under 1 MB.
- Content safe area: keep text inside the left 45% and 40px from every edge (cards crop on some platforms).
- Must show: the name, the promise ("Business details in. Website out."), "A Claude Code plugin", and real output (example screenshots), not abstract art.
- Dark background so it stands out in light-mode feeds; one accent colour.
- Current file: `docs/media/social-preview.png`. Regenerate after visual changes to the examples.

## Demo GIF

- 20 seconds, 1280×720, under 8 MB (GitHub inline limit 10 MB), 12–15 fps, loops.
- Script: 0–3 s type `/shingle Marigold Kitchen, Goan restaurant…` · 3–8 s interview question cards (pick recommended) · 8–11 s palette choice with swatches · 11–15 s build and audit output (`PASS: 0 errors`) · 15–20 s the finished site scrolling, then the phone view.
- Speed up the build part; never fake output. Record with a screen recorder at 2× then trim; convert with `ffmpeg -i demo.mov -vf "fps=12,scale=1280:-1:flags=lanczos" -loop 0 demo.gif` (or gifski).
- Save as `docs/media/demo.gif`, update the README `<img>` and its alt text.

## Launch posts

Post Tuesday–Thursday morning US Eastern. Reply to every comment in the first 3 hours. Lead
with the problem and real output, not with "AI".

### Show HN

- **Title:** `Show HN: Shingle – a Claude Code plugin that turns business details into a website`
- **URL:** the GitHub repo.
- **First comment (post immediately):** why (small businesses still lack decent sites; AI site builders invent reviews and look identical), how it works (7 steps, 13 category playbooks, 8 design directions, scripts that audit for fabricated content), what it deliberately doesn't do (no hosting, no lock-in, no invented facts), what you want feedback on. Link the live gallery.

### Product Hunt

- **Tagline (60 chars):** `Business details in, website out, inside Claude Code`
- **Gallery:** social preview, 4 example screenshots (desktop), 2 phone screenshots, the demo GIF.
- **Maker comment:** the story, the "nothing invented" rule, how to install in two commands, ask for category requests.
- Topics: Developer Tools, Website Builder, Open Source, Artificial Intelligence.

### r/ClaudeAI

- **Title:** `I built a Claude Code plugin that interviews you about a local business and builds the website (open source)`
- Body: 3 sentences on what it does, the install commands, the gallery link, 2 screenshots, and one honest limitation. Use the "Built with Claude" flair if available. Follow the subreddit's self-promotion rules.

### X thread

1. Hook + demo GIF: "Give Claude Code a business name, address and hours. Get back a finished, accessible website. No lorem ipsum, no fake reviews. Open source:" + link
2. Screenshot wall: "8 example sites, 8 design directions. None of them is hero + 3 cards."
3. The interview: question-card screenshot, "max 4 questions a round, always a recommended answer"
4. Trust: the audit output catching invented reviews, NAP mismatches, emoji icons
5. Local SEO: the JSON-LD + live "Open now" status
6. Contribute: "a new category is one Markdown file, 10 minutes" + link
7. Install: the two `/plugin` commands

## After launch

- Pin a "Show us your site" Discussion.
- Label easy issues `good first issue` (categories, palettes).
- Weekly: triage, merge category PRs, add community examples to the gallery.
