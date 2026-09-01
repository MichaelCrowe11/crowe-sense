# Web: crowelogic.com/app reads Crowe Sense through the edge

The web app is the desktop renderer served by the Worker in `~/crowe-logic-web` (no git).
The desktop branch's `web-bridge.js` calls `/app/sense/v1/nodes/<node>/health`; this patch
teaches the edge to forward `/app/sense/*` to the relay with the signed-in user's own
Crowe ID access token, exactly the way `/app/gw/*` reaches the model gateway.

Applied 2026-09-01 to `~/crowe-logic-web/src/index.js` and `wrangler.jsonc` (var
`SENSE_RELAY`), backups at `*.bak-pre-sense`, `node --check` clean. The diff is
`crowe-logic-web-sense.patch` beside this file.

Not deployed: `wrangler deploy` is Michael's (the auto-mode classifier blocks it for
Claude every time). The line:

    cd ~/crowe-logic-web && env -u CLOUDFLARE_API_TOKEN npx wrangler deploy

Verify with a signed-in browser, not a curl: `/app/sense/v1/nodes` returns `{"nodes":[]}`
(or the paired nodes), and an anonymous `curl -i https://crowelogic.com/app/sense/v1/nodes`
returns the 401 sign-in JSON. Then carry the desktop branch's renderer files into
`public/app/renderer/` the usual way (patch the source in the desktop repo, `cp` the four
changed files, redeploy).

Free tiers are allowed through here on purpose: a grower on the free plan may read their
own node. The relay enforces ownership; the plan gate stays on the model gateway.
