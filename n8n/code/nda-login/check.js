// nda-login, step 2: Turnstile verdict, then ask web.login_begin for lockout state and the hash.
const v = $('Validate').first().json;
if (!turnstileOk($input.first().json, v.turnstile, v.action)) return reply(400, { error: 'invalid' });
return next({ db: { email: $('Webhook').first().json.body.email.trim().toLowerCase(), ip: v.ip } });
