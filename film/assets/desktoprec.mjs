import { chromium } from "/Users/crowelogic/Projects/crowe-logic-browser-extension/node_modules/playwright/index.mjs";
import fs from "node:fs";
const dir = "/Users/crowelogic/crowe-sense/film/assets/desktoprec"; fs.mkdirSync(dir, { recursive: true }); for (const f of fs.readdirSync(dir)) fs.unlinkSync(`${dir}/${f}`);
const browser = await chromium.connectOverCDP("http://127.0.0.1:9333");
const pages = browser.contexts().flatMap(c => c.pages());
const page = pages.find(p => /app\.html/.test(p.url())) || pages[0];
console.log("page:", page.url());
try { await page.setViewportSize({ width: 1920, height: 1080 }); } catch (e) { console.log("viewport:", e.message.slice(0, 80)); }
await page.waitForTimeout(1500);
const cult = page.locator('[data-space="cultivation"]'); if (await cult.count()) { await cult.first().click(); console.log("cultivation clicked"); }
await page.waitForTimeout(2500);
const N = 150, t0 = Date.now();
for (let i = 0; i < N; i++) {
  if (i === 60) { const env = page.locator('#cult-nav [data-cult="env"]'); if (await env.count()) await env.first().click(); }
  if (i === 110) { const home = page.locator('#cult-nav [data-cult="home"]'); if (await home.count()) await home.first().click(); }
  await page.screenshot({ path: `${dir}/f${String(i).padStart(4, "0")}.png` });
  const w = t0 + (i + 1) * 100 - Date.now(); if (w > 0) await new Promise(r => setTimeout(r, w));
}
console.log("desktop frames", N); process.exit(0);
