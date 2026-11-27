#!/usr/bin/env node
// Screenshot one URL through the Chrome DevTools protocol (Node 22+, no dependencies).
// Usage: node shot.mjs <chrome> <url> <out.png> <width> <height> [scale] [dark]
import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

const [chrome, url, out, w, h, scale = "1", dark = "0"] = process.argv.slice(2);
const proc = spawn(chrome, ["--no-sandbox", "--disable-gpu", "--hide-scrollbars", "--remote-debugging-port=0", "about:blank"], {
  stdio: ["ignore", "ignore", "pipe"],
});
const done = (code) => {
  proc.kill();
  process.exit(code);
};
setTimeout(() => {
  console.error("timeout");
  done(1);
}, 60000);

const wsUrl = await new Promise((resolve) => {
  let buf = "";
  proc.stderr.on("data", (d) => {
    buf += d;
    const m = buf.match(/ws:\/\/\S+/);
    if (m) resolve(m[0]);
  });
});

const ws = new WebSocket(wsUrl);
await new Promise((r) => (ws.onopen = r));
let id = 0;
const pending = new Map();
const waiters = [];
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result);
  } else if (msg.method) {
    for (const wt of waiters) if (wt.method === msg.method) wt.resolve(msg.params);
  }
};
const send = (method, params = {}, sessionId) =>
  new Promise((resolve, reject) => {
    const n = ++id;
    pending.set(n, { resolve, reject });
    ws.send(JSON.stringify({ id: n, method, params, sessionId }));
  });
const once = (method) => new Promise((resolve) => waiters.push({ method, resolve }));

const { targetId } = await send("Target.createTarget", { url: "about:blank" });
const { sessionId } = await send("Target.attachToTarget", { targetId, flatten: true });
const s = (m, p) => send(m, p, sessionId);
await s("Page.enable");
await s("Emulation.setDeviceMetricsOverride", {
  width: +w,
  height: +h,
  deviceScaleFactor: +scale,
  mobile: +w < 600,
});
await s("Emulation.setEmulatedMedia", {
  features: [{ name: "prefers-color-scheme", value: dark === "1" ? "dark" : "light" }],
});
const loaded = once("Page.loadEventFired");
await s("Page.navigate", { url });
await loaded;
await s("Runtime.enable");
await s("Runtime.evaluate", { expression: "document.fonts.ready.then(() => new Promise(r => setTimeout(r, 400)))", awaitPromise: true });
const { data } = await s("Page.captureScreenshot", { format: "png" });
writeFileSync(out, Buffer.from(data, "base64"));
done(0);
