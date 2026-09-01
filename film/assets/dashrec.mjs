// Record the node's own dashboard while readings arrive: 12 s at 10 fps, real UI, demonstration data.
import { chromium } from "/Users/crowelogic/Projects/crowe-logic-browser-extension/node_modules/playwright/index.mjs";
import fs from "node:fs";
const dir = "/Users/crowelogic/crowe-sense/film/assets/dashrec"; fs.mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args: ["--hide-scrollbars"] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
await page.goto("http://127.0.0.1:8078/"); await page.waitForSelector(".card", { timeout: 30000 });
// refresh faster than the page's own 15 s so the numbers visibly tick
await page.evaluate(() => { setInterval(() => { if (typeof load === "function") load(); }, 1500); });
const N = 120; const t0 = Date.now();
for (let i = 0; i < N; i++) { await page.screenshot({ path: `${dir}/f${String(i).padStart(4, "0")}.png` }); const wait = t0 + (i + 1) * 100 - Date.now(); if (wait > 0) await new Promise(r => setTimeout(r, wait)); }
await browser.close(); console.log(`dashboard: ${N} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
