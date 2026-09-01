// Local relay for demos and tests: the real handler (src/index.js) on node:http with the in-memory
// store and a stub bearer. The ingest path (signature, parse, store) is the production code.
import http from "node:http";
import { makeHandler } from "./src/index.js";
import { memoryStore } from "./src/store-memory.js";
const store = memoryStore();
const handle = makeHandler({ store, bearer: async (auth) => (auth === "Bearer demo" ? { email: "michael@crowelogic.com" } : null) });
const port = Number(process.env.PORT || 8787);
http.createServer(async (req, res) => {
  const chunks = []; for await (const c of req) chunks.push(c);
  const body = Buffer.concat(chunks);
  const r = await handle(new Request(`http://127.0.0.1:${port}${req.url}`, { method: req.method, headers: req.headers, body: body.length ? body : undefined }));
  const out = Buffer.from(await r.arrayBuffer());
  const stamp = new Date().toISOString().slice(11, 19);
  console.log(`${stamp} ${req.method} ${req.url} -> ${r.status}${req.url === "/v1/ingest" ? " " + out.toString().slice(0, 80) : ""}`);
  res.writeHead(r.status, Object.fromEntries(r.headers)); res.end(out);
}).listen(port, "127.0.0.1", () => console.log(`crowe-sense-relay (memory store) on http://127.0.0.1:${port}`));
