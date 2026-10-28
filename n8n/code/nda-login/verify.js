// nda-login, step 3: locked out -> 429. Otherwise scrypt-check the password (against a dummy
// hash when there's no live NDA for that email, so every attempt takes as long) and mint a token.
const r = $input.first().json.r;
if (r.locked) return reply(429, { error: 'rate_limited' });
const v = $('Validate').first().json;
const ok = verifyPassword($('Webhook').first().json.body.password, r.password_hash);
const token = randomToken();
return next({
  token,
  db: { email: $('Check').first().json.db.email, ok, token_sha256: sha256hex(token), ip: v.ip, ua: v.ua },
});
