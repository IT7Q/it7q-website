// nda-review GET, step 1 (§4.4): Cloudflare Access must have let Chris in. GET never changes anything.
const wh = $('Webhook GET').first().json;
const viewer = verifyAccess(wh, $input.first().json);
if (!viewer) return page(403, 'Not allowed', '<p class="msg err">This page needs a Cloudflare Access login.</p>');
const t = typeof wh.query.t === 'string' && wh.query.t.length <= 100 ? wh.query.t : '';
return next({ t, db: { review_sha256: t ? sha256hex(t) : '' } });
