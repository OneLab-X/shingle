import React from "react";
import { AbsoluteFill, Easing, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig } from "remotion";

export const FPS = 30;
export const DEMO_FRAMES = 20 * FPS; // 20 seconds

// Palette matches docs/media/social-preview.png
const BG = "#141413";
const PANEL = "#1d1c1a";
const LINE = "#3a3936";
const FG = "#F2F2EE";
const MUTED = "#A8A49D";
const GOLD = "#E9B949";
const GREEN = "#7FD08A";
const MONO = "Menlo, 'SF Mono', Consolas, monospace";
const SANS = "'Helvetica Neue', Helvetica, Arial, sans-serif";

const clamp = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Fade a scene in and out over its own length. */
const Scene: React.FC<{ frames: number; children: React.ReactNode }> = ({ frames, children }) => {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [0, 8, frames - 8, frames], [0, 1, 1, 0], clamp);
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

const typed = (text: string, frame: number, start: number, cps = 38) =>
  text.slice(0, Math.max(0, Math.floor(((frame - start) / FPS) * cps)));

const Cursor: React.FC<{ on?: boolean }> = ({ on = true }) => {
  const f = useCurrentFrame();
  const blink = Math.floor(f / 8) % 2 === 0;
  return <span style={{ display: "inline-block", width: 14, height: 28, marginLeft: 3, transform: "translateY(5px)", background: on && blink ? GOLD : "transparent" }} />;
};

const Window: React.FC<{ title: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ title, children, style }) => (
  <div style={{ background: PANEL, border: `1px solid ${LINE}`, borderRadius: 14, overflow: "hidden", boxShadow: "0 24px 60px rgba(0,0,0,.45)", ...style }}>
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "12px 16px", borderBottom: `1px solid ${LINE}`, color: MUTED, fontFamily: SANS, fontSize: 15 }}>
      {[0, 1, 2].map((i) => (
        <span key={i} style={{ width: 11, height: 11, borderRadius: 6, background: LINE }} />
      ))}
      <span style={{ marginLeft: 10 }}>{title}</span>
    </div>
    {children}
  </div>
);

const Caption: React.FC<{ step: number; text: string }> = ({ step, text }) => (
  <div style={{ position: "absolute", left: 60, top: 40, fontFamily: SANS, color: MUTED, fontSize: 24, letterSpacing: 0.4, display: "flex", gap: 14, alignItems: "baseline" }}>
    <span style={{ color: GOLD, fontWeight: 700, fontFamily: MONO }}>{step}/5</span>
    <span style={{ color: FG, fontWeight: 600 }}>{text}</span>
  </div>
);

// ------------------------------------------------------------------ 1. intake (0-3.3s)
const COMMAND =
  "/shingle Marigold Kitchen, Goan restaurant, 27 Fenwick Lane, London E8 4QT, 020 7946 0321, Tue-Thu 5:30pm-10:30pm, Fri-Sat 12-3pm & 5:30pm-11pm, Sun 12-4pm";

const Intake: React.FC = () => {
  const f = useCurrentFrame();
  const done = f > 68;
  const lines = [
    ["name", "Marigold Kitchen"],
    ["category", "restaurant"],
    ["phone", "+442079460321"],
    ["country", "GB"],
    ["hours", "4 groups parsed"],
  ];
  return (
    <AbsoluteFill style={{ padding: "110px 60px 0" }}>
      <Caption step={1} text="Give it whatever you have" />
      <Window title="claude" style={{ width: "100%" }}>
        <div style={{ padding: "28px 32px", fontFamily: MONO, fontSize: 25, lineHeight: 1.5, color: FG, minHeight: 470 }}>
          <div style={{ whiteSpace: "pre-wrap" }}>
            <span style={{ color: GOLD }}>&gt; </span>
            {typed(COMMAND, f, 4, 80)}
            {!done && <Cursor />}
          </div>
          {lines.map(([k, v], i) => {
            const o = interpolate(f, [72 + i * 5, 78 + i * 5], [0, 1], clamp);
            return (
              <div key={k} style={{ opacity: o, marginTop: i === 0 ? 30 : 0, color: MUTED }}>
                <span style={{ color: GREEN }}>✓ </span>
                {k.padEnd(9)}
                <span style={{ color: FG }}>{v}</span>
              </div>
            );
          })}
          <div style={{ opacity: interpolate(f, [98, 104], [0, 1], clamp), marginTop: 14, color: MUTED }}>
            missing (optional): socials, description
          </div>
        </div>
      </Window>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ 2. interview (3.3-8.3s)
const QUESTIONS = [
  { q: "What should most visitors do?", opts: ["Book a table (Recommended)", "Call us", "Get directions"] },
  { q: "One scrolling page or separate pages?", opts: ["Single page (Recommended)", "Multi-page"] },
  { q: "How should the words sound?", opts: ["Warm and neighbourly (Recommended)", "Refined and quiet", "Bold and playful"] },
  { q: "What images do we have?", opts: ["I'll add my own photos later (Recommended)", "I have photos now", "Keep it typographic"] },
];

const Interview: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  return (
    <AbsoluteFill style={{ padding: "110px 60px 0" }}>
      <Caption step={2} text="A short interview: 4 questions, a recommended answer each" />
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 22 }}>
        {QUESTIONS.map((item, i) => {
          const enter = spring({ frame: f - i * 9, fps, config: { damping: 200 } });
          const pick = interpolate(f, [34 + i * 14, 38 + i * 14], [0, 1], clamp);
          return (
            <div
              key={item.q}
              style={{
                background: PANEL,
                border: `1px solid ${LINE}`,
                borderRadius: 14,
                padding: "22px 24px",
                opacity: enter,
                transform: `translateY(${(1 - enter) * 24}px)`,
                fontFamily: SANS,
              }}
            >
              <div style={{ color: FG, fontWeight: 700, fontSize: 25, marginBottom: 16 }}>{item.q}</div>
              <div style={{ display: "grid", gap: 9 }}>
                {item.opts.map((o, j) => {
                  const selected = j === 0;
                  return (
                    <div
                      key={o}
                      style={{
                        fontSize: 21,
                        padding: "10px 14px",
                        borderRadius: 9,
                        border: `1.5px solid ${selected && pick > 0.5 ? GOLD : LINE}`,
                        background: selected ? `rgba(233,185,73,${0.14 * pick})` : "transparent",
                        color: selected && pick > 0.5 ? FG : MUTED,
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span>{o}</span>
                      {selected && pick > 0.5 && <span style={{ color: GOLD, fontWeight: 700 }}>✓</span>}
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ 3. design (8.3-11.3s)
const PALETTES = [
  { id: "saffron-ink", name: "Saffron & Ink", c: ["#FBF6EC", "#F3EAD8", "#1E1A16", "#B4471B", "#E8A33D"], why: "Paper-warm with burnt saffron" },
  { id: "olive-grove", name: "Olive Grove", c: ["#F6F5EE", "#E9E8DA", "#1F231A", "#4F5D2F", "#C17C3A"], why: "Muted olive and terracotta" },
  { id: "espresso-cream", name: "Espresso & Cream", c: ["#F7F1E8", "#EDE3D4", "#2B1E16", "#6F3B22", "#C8894E"], why: "Roasted browns on cream" },
];

const Design: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const choose = interpolate(f, [48, 56], [0, 1], clamp);
  return (
    <AbsoluteFill style={{ padding: "110px 60px 0" }}>
      <Caption step={3} text="Palettes checked for WCAG AA contrast, plus a design direction" />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 24 }}>
        {PALETTES.map((p, i) => {
          const enter = spring({ frame: f - i * 7, fps, config: { damping: 200 } });
          const chosen = i === 0;
          const dim = chosen ? 1 : 1 - 0.55 * choose;
          return (
            <div
              key={p.id}
              style={{
                background: PANEL,
                border: `2px solid ${chosen && choose > 0.5 ? GOLD : LINE}`,
                borderRadius: 16,
                padding: 24,
                opacity: enter * dim,
                transform: `translateY(${(1 - enter) * 26}px) scale(${chosen ? 1 + 0.03 * choose : 1})`,
                fontFamily: SANS,
              }}
            >
              <div style={{ display: "flex", height: 120, borderRadius: 10, overflow: "hidden", border: `1px solid ${LINE}` }}>
                {p.c.map((c, k) => (
                  <div key={c} style={{ flex: k === 0 ? 2.2 : 1, background: c }} />
                ))}
              </div>
              <div style={{ color: FG, fontSize: 27, fontWeight: 700, marginTop: 18 }}>{p.name}</div>
              <div style={{ color: MUTED, fontSize: 20, marginTop: 4 }}>{p.why}</div>
              <div style={{ marginTop: 14, display: "inline-block", fontFamily: MONO, fontSize: 17, color: GREEN, border: `1px solid ${GREEN}`, borderRadius: 6, padding: "3px 9px" }}>
                AA pass
              </div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          marginTop: 34,
          opacity: interpolate(f, [58, 68], [0, 1], clamp),
          background: PANEL,
          border: `1px solid ${LINE}`,
          borderRadius: 14,
          padding: "20px 28px",
          display: "flex",
          alignItems: "center",
          gap: 24,
          fontFamily: SANS,
        }}
      >
        <div style={{ fontFamily: "Georgia, 'Times New Roman', serif", fontSize: 48, fontWeight: 800, color: FG, letterSpacing: -1 }}>Broadsheet</div>
        <div style={{ color: MUTED, fontSize: 21, lineHeight: 1.35 }}>
          Fraunces + Source Serif 4. Signature: a newspaper masthead, a menu in columns with dotted leaders.
        </div>
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ 4. build + verify (11.3-15s)
const BUILD_LINES: { cmd?: string; out: string; ok?: boolean; at: number }[] = [
  { cmd: "python3 sync.py .", out: "data files written: site.json, theme.css, fonts.css, robots.txt", at: 4 },
  { cmd: "npm run build", out: "2 page(s) built in 1.08s", at: 26 },
  { cmd: "python3 audit_site.py dist --strict", out: "PASS: 2 page(s), 0 error(s), 0 warning(s), 6 TODO(s)", ok: true, at: 52 },
  { out: "placeholders to fill (TODO(shingle)):", at: 82 },
  { out: "  index.html: Photo: Fish curry rice on the pass (1200×800)", at: 88 },
  { out: "  src/pages/index.astro:39: photo of the fish curry rice, landscape 3:2", at: 94 },
];

const Build: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{ padding: "110px 60px 0" }}>
      <Caption step={4} text="Build, then audit. Unknowns become visible TODOs, never inventions" />
      <Window title="examples/marigold-kitchen" style={{ width: "100%" }}>
        <div style={{ padding: "26px 32px", fontFamily: MONO, fontSize: 23, lineHeight: 1.62, minHeight: 440 }}>
          {BUILD_LINES.map((l, i) => {
            if (f < l.at) return null;
            const cmdChars = l.cmd ? typed(l.cmd, f, l.at, 60) : "";
            const cmdDone = !l.cmd || cmdChars.length >= l.cmd.length;
            const outAt = l.at + (l.cmd ? Math.ceil((l.cmd.length / 60) * FPS) + 6 : 0);
            return (
              <div key={i}>
                {l.cmd && (
                  <div style={{ color: FG }}>
                    <span style={{ color: GOLD }}>$ </span>
                    {cmdChars}
                    {!cmdDone && <Cursor />}
                  </div>
                )}
                {f >= outAt && <div style={{ color: l.ok ? GREEN : MUTED, fontWeight: l.ok ? 700 : 400 }}>{l.out}</div>}
              </div>
            );
          })}
        </div>
      </Window>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ 5. result + end card (15-20s)
const SITE_W = 1280;
const SITE_H = 4608;
const PHONE_W = 780;
const PHONE_H = 11000;

const Result: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const deskScale = 760 / SITE_W;
  const deskView = 430;
  const deskTravel = SITE_H * deskScale - deskView;
  const deskY = -interpolate(f, [10, 100], [0, deskTravel * 0.62], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const phoneScale = 232 / PHONE_W;
  const phoneView = 470;
  const phoneY = -interpolate(f, [14, 100], [0, 1500], { ...clamp, easing: Easing.inOut(Easing.cubic) });
  const phoneIn = spring({ frame: f - 6, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ padding: "110px 60px 0" }}>
      <Caption step={5} text="A real, accessible site. Yours to edit and host anywhere" />
      <div style={{ display: "flex", gap: 44, alignItems: "flex-start" }}>
        <div style={{ width: 800, background: PANEL, border: `1px solid ${LINE}`, borderRadius: 14, overflow: "hidden", boxShadow: "0 24px 60px rgba(0,0,0,.45)" }}>
          <div style={{ height: 34, borderBottom: `1px solid ${LINE}`, display: "flex", alignItems: "center", gap: 7, padding: "0 14px", color: MUTED, fontFamily: SANS, fontSize: 14 }}>
            {[0, 1, 2].map((i) => (
              <span key={i} style={{ width: 10, height: 10, borderRadius: 5, background: LINE }} />
            ))}
            <span style={{ marginLeft: 12 }}>marigold-kitchen.example</span>
          </div>
          <div style={{ width: 760, height: deskView, margin: "0 auto", overflow: "hidden", position: "relative", marginTop: 20, marginBottom: 20 }}>
            <Img src={staticFile("site-desktop.png")} style={{ width: 760, position: "absolute", top: 0, left: 0, transform: `translateY(${deskY}px)` }} />
          </div>
        </div>
        <div
          style={{
            width: 262,
            border: `3px solid ${LINE}`,
            borderRadius: 34,
            padding: 12,
            background: "#0c0c0b",
            opacity: phoneIn,
            transform: `translateY(${(1 - phoneIn) * 40}px)`,
          }}
        >
          <div style={{ width: 232, height: phoneView, borderRadius: 22, overflow: "hidden", position: "relative", background: "#FBF6EC" }}>
            <Img src={staticFile("site-mobile.png")} style={{ width: 232, height: PHONE_H * phoneScale, position: "absolute", top: 0, left: 0, transform: `translateY(${phoneY}px)` }} />
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = spring({ frame: f, fps, config: { damping: 200 } });
  const b = spring({ frame: f - 10, fps, config: { damping: 200 } });
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", textAlign: "center" }}>
      <div style={{ opacity: a, transform: `translateY(${(1 - a) * 20}px)` }}>
        <div style={{ fontFamily: "Impact, 'Arial Narrow Bold', 'Helvetica Neue', sans-serif", fontSize: 150, color: FG, letterSpacing: 2, textTransform: "uppercase", lineHeight: 1 }}>Shingle</div>
        <div style={{ fontFamily: SANS, fontSize: 40, fontWeight: 700, color: FG, marginTop: 18 }}>
          Business details in. <span style={{ color: GOLD }}>Website out.</span>
        </div>
      </div>
      <div style={{ opacity: b, transform: `translateY(${(1 - b) * 20}px)`, marginTop: 44 }}>
        <div style={{ fontFamily: MONO, fontSize: 28, color: FG, background: PANEL, border: `1px solid ${LINE}`, borderRadius: 12, padding: "16px 26px", display: "inline-block" }}>
          <span style={{ color: GOLD }}>/plugin marketplace add </span>OneLab-X/shingle
        </div>
        <div style={{ fontFamily: SANS, fontSize: 24, color: MUTED, marginTop: 24 }}>Claude Code plugin · open source · MIT · github.com/OneLab-X/shingle</div>
      </div>
    </AbsoluteFill>
  );
};

// ------------------------------------------------------------------ timeline
const T = { intake: [0, 112], interview: [112, 250], design: [250, 340], build: [340, 450], result: [450, 540], end: [540, 600] } as const;
const len = (k: keyof typeof T) => T[k][1] - T[k][0];

export const Demo: React.FC = () => (
  <AbsoluteFill style={{ background: BG }}>
    <Sequence from={T.intake[0]} durationInFrames={len("intake")} premountFor={FPS}>
      <Scene frames={len("intake")}><Intake /></Scene>
    </Sequence>
    <Sequence from={T.interview[0]} durationInFrames={len("interview")} premountFor={FPS}>
      <Scene frames={len("interview")}><Interview /></Scene>
    </Sequence>
    <Sequence from={T.design[0]} durationInFrames={len("design")} premountFor={FPS}>
      <Scene frames={len("design")}><Design /></Scene>
    </Sequence>
    <Sequence from={T.build[0]} durationInFrames={len("build")} premountFor={FPS}>
      <Scene frames={len("build")}><Build /></Scene>
    </Sequence>
    <Sequence from={T.result[0]} durationInFrames={len("result")} premountFor={FPS}>
      <Scene frames={len("result")}><Result /></Scene>
    </Sequence>
    <Sequence from={T.end[0]} durationInFrames={len("end")} premountFor={FPS}>
      <Scene frames={len("end")}><EndCard /></Scene>
    </Sequence>
  </AbsoluteFill>
);
