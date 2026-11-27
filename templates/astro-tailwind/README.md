# Your website

Built with [Shingle](https://github.com/OneLab-X/shingle): a static [Astro](https://astro.build) site
with Tailwind CSS. No server, no database, no monthly fee beyond hosting (often free).

## Edit
| What | Where |
|---|---|
| Name, address, phone, email, hours, socials, palette, design | `business.json`, then run sync (below) |
| Page text and sections | `src/pages/` and `src/components/` |
| Photos | `public/images/` (then reference them in the page) |
| Social preview image | delete `src/pages/og.png.ts` and add `public/og.png` (1200×630) |
| "Built with Shingle" badge | `"badge": false` under `decisions` in `business.json` |

Never edit `src/data/site.json`, `src/styles/theme.css`, `src/styles/fonts.css` or
`public/robots.txt` by hand: they are regenerated from `business.json`.

After changing `business.json`, re-run `/shingle .` in Claude Code, or run sync directly:
`python3 <shingle plugin>/skills/shingle/scripts/sync.py .`. Your hand edits to pages and
components are detected and never overwritten.

## Run locally
Needs Node.js 22.23.4 or newer (`nvm use` reads `.nvmrc`).
```
npm install
npm run dev       # http://localhost:4321
npm run build     # static site in dist/
```

## Deploy
- **GitHub Pages:** push to GitHub, then Settings → Pages → Source: GitHub Actions. The included
  `.github/workflows/deploy.yml` builds and deploys on every push to `main`.
- **Netlify:** `npx netlify-cli deploy --prod --dir=dist`
- **Cloudflare Pages:** `npx wrangler pages deploy dist`
