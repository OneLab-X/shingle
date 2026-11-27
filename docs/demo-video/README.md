# Demo video

Source for `docs/media/demo.gif` and `docs/media/demo.mp4` (20 seconds, 1280×720, 30 fps; the GIF is 960×540 at 12 fps).
Built with [Remotion](https://www.remotion.dev).

## What is real and what is re-created

- **Real:** the command output (`validate_input`, `check_contrast`, `sync`, `audit_site`), the palettes and their colours, the interview questions and recommended answers (from `references/interview.md`), and the finished site (full-page screenshots of `examples/marigold-kitchen`).
- **Re-created:** the Claude Code terminal and question cards are drawn, not screen-recorded, and the build is sped up.

## Re-render

Needs Node 22.23.4+ and ffmpeg.

```bash
cd docs/demo-video
npm install
npm run dev       # Remotion Studio: scrub the timeline
npm run render    # writes ../media/demo.mp4 and ../media/demo.gif
```

If the example site changes, refresh the two screenshots in `public/` (full-page, 1280 px desktop and 390 px mobile at 2×) before rendering.

## Timeline

| Seconds | Scene |
|---|---|
| 0–3.7 | Intake: the command is typed, details are normalized |
| 3.7–8.3 | Interview: 4 questions, recommended answers picked |
| 8.3–11.3 | Design: three AA-checked palettes, one picked, Broadsheet direction |
| 11.3–15 | Build and audit output |
| 15–18 | The finished site, desktop and phone |
| 18–20 | End card with the install command |
