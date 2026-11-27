# Deploy

Every Shingle site is a static `dist/` folder built with `npm run build`. Pick one host.

## GitHub Pages
The template includes `.github/workflows/deploy.yml` (official `withastro/action`).
1. Create a GitHub repo and push the site: `git init && git add -A && git commit -m "Site" && gh repo create --source . --push --public`
2. In the repo: Settings → Pages → Source: **GitHub Actions**. The next push deploys.
3. Custom domain: add it in Settings → Pages and create the DNS records GitHub shows
   (CNAME to `<user>.github.io`, or A/AAAA records for an apex domain). Keep `public/CNAME` with
   the domain. Without a custom domain the site is served under `/<repo>/`: set `base` in
   `astro.config.mjs`.

## Netlify
One command (asks to log in the first time):
```
npx netlify-cli deploy --prod --dir=dist
```
Or connect the repo in the Netlify UI: build command `npm run build`, publish directory `dist`.
Netlify Forms works only on Netlify: if chosen, the form already has `data-netlify="true"`.

## Cloudflare Pages
```
npx wrangler pages deploy dist
```
(asks to log in the first time; creates the project on first deploy). Or connect the repo in
the dashboard with build command `npm run build`, output `dist`.

## After any deploy
- Point the domain's DNS at the host; turn on HTTPS (all three do this automatically).
- If the domain changed, update `domain` in business.json and re-run sync, or set `site` in
  `astro.config.mjs`, then redeploy so canonical URLs and the sitemap are right.
- Submit `https://<domain>/sitemap-index.xml` in Google Search Console.
- Update the Google Business Profile website link to the new domain.
