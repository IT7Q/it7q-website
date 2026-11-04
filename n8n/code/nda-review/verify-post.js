// nda-review POST, step 1 (§4.4): Access login, same-origin form, then everything web.review_post
// needs: a password hash for approve/reset, a fresh token for "email me a review link".
const wh = $('Webhook POST').first().json;
const viewer = verifyAccess(wh, $input.first().json);
if (!viewer) return page(403, 'Not allowed', '<p class="msg err">This page needs a Cloudflare Access login.</p>');
// CSRF: the post must come from the review page itself. Normally Origin says so. Chrome sends
// Origin: null on a same-origin form post when it decides not to reveal the origin; then only the
// browser's own Sec-Fetch-* headers (which no page can set) count, and only for a top-level form
// navigation from this same origin. Both paths still need the Access login above and the page's
// form token below.
const origin = header(wh.headers, 'origin');
const sameOriginNav = origin === 'null' && header(wh.headers, 'sec-fetch-site') === 'same-origin'
  && header(wh.headers, 'sec-fetch-mode') === 'navigate';
if (origin === 'null' && !sameOriginNav) {
  return page(403, 'Not allowed', '<p class="msg err">Refused: the browser hid where this came from '
    + '(Origin: null, not a same-origin form). Check the page arrived with the IT7Q security policy and '
    + 'Referrer-Policy: same-origin (DEPLOY.md step 6g). Nothing was changed.</p>');
}
if (origin !== CFG.hook_origin && !sameOriginNav) {
  return page(403, 'Not allowed', '<p class="msg err">Changes can only be made from the review page itself.</p>');
}
const b = wh.body || {};
const one = (v) => (Array.isArray(v) ? String(v[0] || '') : String(v || ''));
if (!formTokenOk(wh, one(b.f))) {
  return page(403, 'Not allowed', '<p class="msg err">This page is out of date (or your Access login was renewed). '
    + 'Go back, reload it and try again. Nothing was changed.</p>');
}
const action = one(b.action);
const actions = ['approve', 'reject', 'revoke', 'reset', 'investor_on', 'investor_off', 'new_review_link'];
if (!actions.includes(action)) return page(400, 'Not done', '<p class="msg err">Unknown action.</p>');
const db = { action, actor: viewer, ip: requestMeta(wh).ip };
let password = '';
let review = '';
if (action === 'approve' || action === 'reject') {
  if (!one(b.t) || one(b.t).length > 100) return page(400, 'Not done', '<p class="msg err">Missing review link.</p>');
  db.review_sha256 = sha256hex(one(b.t));
} else {
  if (!/^\d{1,12}$/.test(one(b.request_id))) return page(400, 'Not done', '<p class="msg err">Missing request.</p>');
  db.request_id = Number(one(b.request_id));
}
if (action === 'approve') {
  db.divisions = CFG.divisions.filter((d) => one(b['div_' + d]) === '1');
  db.investor = one(b.investor) === '1';
}
if (action === 'approve' || action === 'reset') {
  password = newPassword();
  db.password_hash = hashPassword(password);
}
if (action === 'new_review_link') {
  review = randomToken();
  db.new_review_sha256 = sha256hex(review);
}
return next({ password, review, db });
