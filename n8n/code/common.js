// ---- common.js: shared by every IT7Q Code node (PLAN.md §4). tools/n8n_build.py pastes
// this above each step, with CFG filled in from deploy/config.json, src/data/forms.json and
// the NDA. Needs NODE_FUNCTION_ALLOW_BUILTIN=crypto on n8n (DEPLOY.md step 3).
const crypto = require('crypto');
const CFG = __CONFIG__;

// Every gate ends in one of these two. IF nodes route on `go`; the Reply node uses status + body.
function reply(status, body) { return [{ json: { go: false, status, body } }]; }
function next(data) { return [{ json: Object.assign({ go: true }, data) }]; }

function header(h, name) {
  const v = (h || {})[name];
  return Array.isArray(v) ? String(v[0] || '') : String(v || '');
}
function requestMeta(wh) {
  // cf-connecting-ip is trustworthy here: the edge header proves the request came through Cloudflare.
  return { ip: header(wh.headers, 'cf-connecting-ip'), ua: header(wh.headers, 'user-agent').slice(0, 400) };
}
function sha256hex(s) { return crypto.createHash('sha256').update(String(s)).digest('hex'); }
function randomToken() { return crypto.randomBytes(32).toString('base64url'); }
function clean(s) { return String(s == null ? '' : s).trim().replace(/\s+/g, ' '); }
function esc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
// Postgres sends timestamps with microseconds; trim to milliseconds before parsing.
function toDate(t) { return new Date(String(t).replace(/(\.\d{3})\d+/, '$1')); }
function isoZ(t) { return toDate(t).toISOString().replace(/\.\d{3}Z$/, 'Z'); }
function auDate(t) {
  return toDate(t).toLocaleString('en-AU', { timeZone: 'Australia/Brisbane', dateStyle: 'long', timeStyle: 'short' });
}

// JSON only, at most 8 KB, an object (§4.2 Validation). Returns [status, body] or null.
function checkEnvelope(wh) {
  const ct = header(wh.headers, 'content-type').split(';')[0].trim().toLowerCase();
  if (ct !== 'application/json') return [415, { error: 'json_only' }];
  if (parseInt(header(wh.headers, 'content-length') || '0', 10) > CFG.max_body) return [413, { error: 'too_large' }];
  const b = wh.body;
  if (!b || typeof b !== 'object' || Array.isArray(b)) return [400, { error: 'invalid' }];
  if (JSON.stringify(b).length > CFG.max_body) return [413, { error: 'too_large' }];
  return null;
}

// Mirrors tools/preview.py Mock.validate (the Turnstile token itself is checked by Cloudflare).
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const SYSTEM_FIELDS = ['turnstile', 'website', 'elapsed_ms'];
function validateForm(key, body) {
  const spec = CFG.forms[key];
  const fields = {};
  spec.fields.forEach((f) => { fields[f.name] = f; });
  const allowed = new Set(Object.keys(fields).concat(SYSTEM_FIELDS, spec.system || []));
  const extra = Object.keys(body).filter((k) => !allowed.has(k));
  if (extra.length) return 'unexpected field(s)';
  for (const name of Object.keys(fields)) {
    const f = fields[name];
    let v = body[name];
    if (f.type === 'checkbox') {
      if (typeof v !== 'boolean' || (f.required && v !== true)) return name;
      continue;
    }
    if (v == null) v = '';
    if (typeof v !== 'string') return name;
    if (f.required && !v.trim()) return name;
    if (v.length > (f.max || 10000)) return name;
    if (f.type === 'email' && v && !EMAIL.test(v)) return name;
    if (f.type === 'select' && !f.options.includes(v)) return name;
    if (f.match && clean(v).toLowerCase() !== clean(body[f.match]).toLowerCase()) return name;
  }
  if (key === 'nda_request' && (body.nda_version !== CFG.nda.version || body.nda_sha256 !== CFG.nda.sha256)) {
    return 'nda';
  }
  if (typeof body.turnstile !== 'string' || !body.turnstile || body.turnstile.length > 2048) return 'turnstile';
  return null;
}
// Honeypot filled or sent in under 3 s: a neutral 202, nothing stored or emailed (§4.12).
function isBot(body) {
  return Boolean(body.website) || typeof body.elapsed_ms !== 'number' || body.elapsed_ms < CFG.min_elapsed_ms;
}

// Turnstile siteverify result (§4.2): success, our hostname and this form's action.
// Cloudflare's documented dummy token only ever succeeds while the n8n credential holds the
// always-pass TEST secret (DEPLOY.md step 9); with the real secret it fails like any bad token.
const TURNSTILE_DUMMY_TOKEN = 'XXXX.DUMMY.TOKEN.XXXX';
function turnstileOk(res, token, action) {
  if (!res || res.success !== true) return false;
  if (token === TURNSTILE_DUMMY_TOKEN) return true;
  return CFG.turnstile_hostnames.includes(res.hostname) && res.action === action;
}

// Passwords (§4.4, §4.5): scrypt N=16384 r=8 p=1, 16-byte salt, 32-byte key.
const SCRYPT_OPTS = { N: 16384, r: 8, p: 1, maxmem: 64 * 1024 * 1024 };
function hashPassword(pw) {
  const salt = crypto.randomBytes(16);
  const key = crypto.scryptSync(pw, salt, 32, SCRYPT_OPTS);
  return ['scrypt', 16384, 8, 1, salt.toString('base64'), key.toString('base64')].join('$');
}
// Always does the full scrypt (a dummy hash for unknown emails), then a constant-time compare.
function verifyPassword(pw, stored) {
  let parts = String(stored || '').split('$');
  const real = parts.length === 6 && parts[0] === 'scrypt' && parts[1] === '16384';
  if (!real) parts = CFG.dummy_hash.split('$');
  const expected = Buffer.from(parts[5], 'base64');
  const key = crypto.scryptSync(String(pw), Buffer.from(parts[4], 'base64'), expected.length, SCRYPT_OPTS);
  return crypto.timingSafeEqual(key, expected) && real;
}
// 20 characters, no look-alikes (0/O, 1/l/I): about 113 bits.
function newPassword() {
  const abc = 'ABCDEFGHJKMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789';
  let out = '';
  for (let i = 0; i < 20; i += 1) out += abc[crypto.randomInt(abc.length)];
  return out;
}

// Cloudflare Access (§4.4): verify the Cf-Access-Jwt-Assertion header against the team's
// signing keys (fetched by the node before this one). Returns the viewer's email or null.
function verifyAccess(wh, certs) {
  const a = CFG.access;
  if (!a.team || a.team.startsWith('PLACEHOLDER') || !a.aud || a.aud.startsWith('PLACEHOLDER')) return null;
  const parts = header(wh.headers, 'cf-access-jwt-assertion').split('.');
  if (parts.length !== 3) return null;
  let head;
  let claims;
  try {
    head = JSON.parse(Buffer.from(parts[0], 'base64url').toString('utf8'));
    claims = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
  } catch (e) {
    return null;
  }
  if (head.alg !== 'RS256') return null;
  const jwk = ((certs && certs.keys) || []).find((k) => k.kid === head.kid);
  if (!jwk) return null;
  let good = false;
  try {
    const key = crypto.createPublicKey({ key: jwk, format: 'jwk' });
    good = crypto.verify('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]), key, Buffer.from(parts[2], 'base64url'));
  } catch (e) {
    return null;
  }
  const now = Date.now() / 1000;
  const aud = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
  if (!good || !aud.includes(a.aud) || claims.iss !== 'https://' + a.team + '.cloudflareaccess.com'
      || !(claims.exp > now) || (claims.nbf && claims.nbf > now + 60)) return null;
  const email = String(claims.email || '').toLowerCase();
  return a.allowed_emails.includes(email) ? email : null;
}

// Plain, inline-styled HTML email (no images, no tracking).
function emailHtml(title, inner) {
  return '<!doctype html><html lang="en-AU"><body style="margin:0;padding:24px;background:#f4f6f8;'
    + 'font-family:Arial,Helvetica,sans-serif;color:#14202b;line-height:1.5">'
    + '<div style="max-width:640px;margin:0 auto;background:#fff;padding:24px;border-radius:8px">'
    + '<h1 style="font-size:20px;margin:0 0 16px">' + esc(title) + '</h1>' + inner
    + '<p style="margin-top:24px;font-size:13px;color:#5b6772">IT7Q Cyber-Tech Services · ABN 43 922 878 001 · '
    + 'Kallangur QLD 4503</p></div></body></html>';
}
function row(label, value) {
  return '<tr><th align="left" style="padding:4px 12px 4px 0;vertical-align:top">' + esc(label)
    + '</th><td style="padding:4px 0">' + esc(value) + '</td></tr>';
}
// ---- end common.js
