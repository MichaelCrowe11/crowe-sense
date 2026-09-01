// Ed25519 batch signatures (node -> relay) and Crowe ID bearer tokens (app -> relay).

const b64 = {
  decode(s) {
    const clean = s.replace(/-/g, "+").replace(/_/g, "/");
    const bin = atob(clean + "=".repeat((4 - (clean.length % 4)) % 4));
    const out = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  },
};

/** Verify `signatureB64` over `bodyBytes` with a base64 raw 32-byte Ed25519 public key. */
export async function verifyBatch(publicKeyB64, signatureB64, bodyBytes) {
  let key;
  try {
    const raw = b64.decode(publicKeyB64);
    if (raw.length !== 32) return false;
    key = await crypto.subtle.importKey("raw", raw, { name: "Ed25519" }, false, ["verify"]);
  } catch { return false; }
  let sig;
  try { sig = b64.decode(signatureB64); } catch { return false; }
  if (sig.length !== 64) return false;
  try { return await crypto.subtle.verify({ name: "Ed25519" }, key, sig, bodyBytes); } catch { return false; }
}

// --- Crowe ID (Keycloak realm crowe) RS256 bearer -------------------------------------
let jwksCache = { at: 0, keys: new Map() };
const JWKS_TTL_MS = 10 * 60 * 1000;

async function jwks(issuer) {
  if (Date.now() - jwksCache.at < JWKS_TTL_MS && jwksCache.keys.size) return jwksCache.keys;
  const r = await fetch(`${issuer}/protocol/openid-connect/certs`, { cf: { cacheTtl: 0 } });
  if (!r.ok) throw new Error(`jwks ${r.status}`);
  const { keys } = await r.json();
  const m = new Map();
  for (const k of keys) {
    if (k.kty !== "RSA" || (k.use && k.use !== "sig")) continue;
    m.set(k.kid, await crypto.subtle.importKey("jwk", k, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]));
  }
  jwksCache = { at: Date.now(), keys: m };
  return m;
}

/** Returns {email} for a valid Crowe ID access token, else null. */
export async function verifyBearer(authorization, issuer) {
  const m = /^Bearer\s+(.+)$/i.exec(authorization || "");
  if (!m) return null;
  const parts = m[1].split(".");
  if (parts.length !== 3) return null;
  let header, payload;
  try {
    header = JSON.parse(new TextDecoder().decode(b64.decode(parts[0])));
    payload = JSON.parse(new TextDecoder().decode(b64.decode(parts[1])));
  } catch { return null; }
  if (header.alg !== "RS256" || !header.kid) return null;
  if (payload.iss !== issuer) return null;
  if (typeof payload.exp !== "number" || payload.exp * 1000 < Date.now()) return null;
  const key = (await jwks(issuer)).get(header.kid);
  if (!key) return null;
  const data = new TextEncoder().encode(`${parts[0]}.${parts[1]}`);
  const ok = await crypto.subtle.verify({ name: "RSASSA-PKCS1-v1_5" }, key, b64.decode(parts[2]), data);
  if (!ok) return null;
  const email = payload.email || payload.preferred_username;
  if (!email) return null;
  return { email: String(email).toLowerCase(), tier: payload.crowe_tier || payload.tier || "" };
}
