// nda-login, step 4: one 401 for every failure (§4.5); the token goes to the browser only here.
const r = $input.first().json.r;
if (r.result !== 'ok') return reply(401, { error: 'login_failed' });
return reply(200, { token: $('Verify').first().json.token, email: r.email, expires_at: isoZ(r.expires_at),
  investor: r.investor === true });
