// nda-submission, step 1 (§4.3): envelope, fields, honeypot/timing. The edge header was
// already checked by the Webhook node's Header Auth.
const wh = $('Webhook').first().json;
const bad = checkEnvelope(wh);
if (bad) return reply(bad[0], bad[1]);
if (validateForm('nda_request', wh.body)) return reply(400, { error: 'invalid' });
if (isBot(wh.body)) return reply(202, { ok: true });
return next(Object.assign({ turnstile: wh.body.turnstile, action: CFG.forms.nda_request.turnstile_action },
  requestMeta(wh)));
