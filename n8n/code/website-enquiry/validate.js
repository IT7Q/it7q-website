// website-enquiry, step 1 (§4.7): envelope, fields, honeypot/timing.
const wh = $('Webhook').first().json;
const bad = checkEnvelope(wh);
if (bad) return reply(bad[0], bad[1]);
if (validateForm('enquiry', wh.body)) return reply(400, { error: 'invalid' });
if (isBot(wh.body)) return reply(202, { ok: true });
return next(Object.assign({ turnstile: wh.body.turnstile, action: CFG.forms.enquiry.turnstile_action },
  requestMeta(wh)));
