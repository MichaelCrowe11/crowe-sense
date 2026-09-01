// Render 240 turntable frames (8 s at 30 fps) of the enclosure with Playwright driving Chrome.
import { chromium } from "/Users/crowelogic/Projects/crowe-logic-browser-extension/node_modules/playwright/index.mjs";
import fs from "node:fs";
const dir = "/Users/crowelogic/crowe-sense/film/assets/turntable"; fs.mkdirSync(dir, { recursive: true });
const browser = await chromium.launch({ executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true,
  args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files", "--hide-scrollbars"] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on("console", m => console.log("[page]", m.text())); page.on("pageerror", e => console.log("[pageerror]", e.message)); await page.goto("http://127.0.0.1:8090/cad-turntable.html");
await page.waitForFunction(() => window.ready === true, null, { timeout: 120000 });
const N = 240; const t0 = Date.now();
for (let i = 0; i < N; i++) {
  await page.evaluate(({ i, N }) => window.frame(i, N), { i, N });
  await page.screenshot({ path: `${dir}/f${String(i).padStart(4, "0")}.png`, type: "png" });
  if (i % 40 === 0) console.log(`frame ${i}/${N} at ${((Date.now() - t0) / 1000).toFixed(0)}s`);
}
await browser.close(); console.log(`done ${N} frames in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
