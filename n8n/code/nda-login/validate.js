// nda-login, step 1 (§4.5): envelope and fields.
const wh = $('Webhook').first().json;
const bad = checkEnvelope(wh);
if (bad) return reply(bad[0], bad[1]);
if (validateForm('nda_login', wh.body)) return reply(400, { error: 'invalid' });
return next(Object.assign({ turnstile: wh.body.turnstile, action: CFG.forms.nda_login.turnstile_action },
  requestMeta(wh)));
