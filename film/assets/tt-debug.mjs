import { chromium } from "/Users/crowelogic/Projects/crowe-logic-browser-extension/node_modules/playwright/index.mjs";
for (const mode of ["bundled", "chrome"]) {
  try {
    const opts = mode === "chrome" ? { executablePath: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", headless: true, args: ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"] } : { headless: true, args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"] };
    const b = await chromium.launch(opts); const p = await b.newPage({ viewport: { width: 640, height: 360 } });
    p.on("console", m => console.log(`[${mode} console]`, m.text().slice(0, 160))); p.on("pageerror", e => console.log(`[${mode} pageerror]`, e.message.slice(0, 160)));
    await p.goto("http://127.0.0.1:8090/cad-turntable.html"); await p.waitForTimeout(8000);
    const diag = await p.evaluate(() => { const c = document.createElement("canvas"); let gl = null, err = ""; try { gl = c.getContext("webgl2") || c.getContext("webgl"); } catch (e) { err = String(e); } return { three: typeof THREE, ready: window.ready, webgl: !!gl, err, renderer: gl ? gl.getParameter(gl.RENDERER) : null }; });
    console.log(mode, JSON.stringify(diag)); await b.close();
  } catch (e) { console.log(mode, "launch failed:", String(e).slice(0, 200)); }
}
