// nda-review POST, step 1 (§4.4): Access login, same-origin form, then everything web.review_post
// needs: a password hash for approve/reset, a fresh token for "email me a review link".
const wh = $('Webhook POST').first().json;
const viewer = verifyAccess(wh, $input.first().json);
if (!viewer) return page(403, 'Not allowed', '<p class="msg err">This page needs a Cloudflare Access login.</p>');
const origin = header(wh.headers, 'origin');
if (origin === 'null') {  // n8n's own sandbox CSP reached the browser: the step 6g Cloudflare rule is missing
  return page(403, 'Not allowed', '<p class="msg err">Refused: the page arrived without the IT7Q security policy '
    + '(DEPLOY.md step 6g). Nothing was changed.</p>');
}
if (origin !== CFG.hook_origin) {
  return page(403, 'Not allowed', '<p class="msg err">Changes can only be made from the review page itself.</p>');
}
const b = wh.body || {};
const one = (v) => (Array.isArray(v) ? String(v[0] || '') : String(v || ''));
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
