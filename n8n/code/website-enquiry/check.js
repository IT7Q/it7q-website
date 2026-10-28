// website-enquiry, step 2: Turnstile verdict, then the row for web.enquiry_add.
const v = $('Validate').first().json;
if (!turnstileOk($input.first().json, v.turnstile, v.action)) return reply(400, { error: 'invalid' });
const b = $('Webhook').first().json.body;
return next({
  db: {
    name: clean(b.name), email: b.email.trim().toLowerCase(), phone: clean(b.phone), service: b.service,
    division: b.division || '', message: String(b.message).trim(), ip: v.ip,
  },
});
