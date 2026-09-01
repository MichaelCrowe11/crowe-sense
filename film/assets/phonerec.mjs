// The Crowe Sense app page (app/dist) at phone size, reading the live demo node, 12 s at 10 fps.
import { chromium } from "/Users/crowelogic/Projects/crowe-logic-browser-extension/node_modules/playwright/index.mjs";
import fs from "node:fs";
const dir = "/Users/crowelogic/crowe-sense/film/assets/phonerec"; fs.mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args: ["--hide-scrollbars"] });
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true });
const page = await ctx.newPage();
await page.addInitScript(() => { localStorage.setItem("crowe-sense-cfg", JSON.stringify({ source: "direct", url: "http://127.0.0.1:8078", node: "", relay: "https://sense.crowelogic.com", token: "", hours: 6 })); });
await page.goto("http://127.0.0.1:8091/index.html"); await page.waitForSelector(".card", { timeout: 30000 });
await page.evaluate(() => { document.getElementById("settings").classList.remove("open"); setInterval(() => load(), 1500); });
await page.waitForTimeout(800);
const N = 120, t0 = Date.now();
for (let i = 0; i < N; i++) {
  if (i === 45) await page.evaluate(() => window.scrollTo({ top: 520, behavior: "smooth" }));
  if (i === 90) await page.evaluate(() => window.scrollTo({ top: 0, behavior: "smooth" }));
  await page.screenshot({ path: `${dir}/f${String(i).padStart(4, "0")}.png` });
  const w = t0 + (i + 1) * 100 - Date.now(); if (w > 0) await new Promise(r => setTimeout(r, w));
}
await browser.close(); console.log("phone frames", N);
