// nda-submission, step 2: Turnstile verdict, then the row for web.submit_nda and a review token.
const v = $('Validate').first().json;
if (!turnstileOk($input.first().json, v.turnstile, v.action)) return reply(400, { error: 'invalid' });
const b = $('Webhook').first().json.body;
const review = randomToken();
return next({
  review,
  db: {
    name: clean(b.name), email: b.email.trim().toLowerCase(), org: clean(b.org), reason: b.reason.trim(),
    wants_investor: b.wants_investor === true, nda_version: b.nda_version, nda_sha256: b.nda_sha256,
    signature: clean(b.signature), ip: v.ip, ua: v.ua, review_sha256: sha256hex(review),
  },
});
