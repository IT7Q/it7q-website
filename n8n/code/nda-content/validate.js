// nda-content, step 1 (§4.6): {token, division} or {token, action:"logout"}. No Turnstile here:
// the session token is the credential, re-checked in Postgres on every call.
const wh = $('Webhook').first().json;
const bad = checkEnvelope(wh);
if (bad) return reply(bad[0], bad[1]);
const b = wh.body;
if (Object.keys(b).some((k) => !['token', 'division', 'action'].includes(k))) return reply(400, { error: 'invalid' });
const meta = requestMeta(wh);
const token = typeof b.token === 'string' && b.token.length >= 20 && b.token.length <= 200 ? b.token : null;
if (b.action === 'logout') {
  if (!token) return reply(200, { ok: true });
  return next({ op: 'logout', db: { token_sha256: sha256hex(token), ip: meta.ip } });
}
if (b.action !== undefined || !(CFG.divisions.includes(b.division) || b.division === 'investors')) {
  return reply(400, { error: 'invalid' });
}
if (!token) return reply(401, { error: 'session' });
return next({ op: 'content', db: { token_sha256: sha256hex(token), division: b.division, ip: meta.ip } });
