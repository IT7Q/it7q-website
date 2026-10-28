// nda-review GET, step 2: one request (from the email's one-time link) or the full list.
const r = $input.first().json.r;
const t = $('Verify GET').first().json.t;
if (r.mode === 'invalid') {
  return page(410, 'Link expired', '<p class="msg err">This review link has expired or was already used. '
    + 'Find the request in the list below to send yourself a new one.</p>');
}
if (r.mode === 'request') {
  const q = r.request;
  return page(200, 'Review NDA request', requestTable(q)
    + '<form method="post" action="' + esc(REVIEW_URL) + '"><input type="hidden" name="t" value="' + esc(t) + '">'
    + '<fieldset><legend>Divisions to unlock</legend>' + divisionBoxes(CFG.divisions) + '</fieldset>'
    + '<fieldset><legend>Investor area</legend><label><input type="checkbox" name="investor" value="1"'
    + (q.wants_investor ? ' checked' : '') + '> Give access to the investor area</label></fieldset>'
    + '<button name="action" value="approve">Approve and email login</button> '
    + '<button class="danger" name="action" value="reject">Reject</button></form>'
    + '<p>Approving creates a password and emails it with the login link. The NDA term ends 3 years after signing.</p>');
}
const rows = r.requests.map((q) => {
  const btn = (action, label, cls) => '<form class="inline" method="post" action="' + esc(REVIEW_URL) + '">'
    + '<input type="hidden" name="request_id" value="' + esc(q.id) + '">'
    + (action === 'revoke' || action === 'reset'
      ? '<label><input type="checkbox" name="confirm" value="1" required> sure</label>' : '')
    + '<button class="' + cls + '" name="action" value="' + action + '">' + esc(label) + '</button></form>';
  let actions = '';
  if (q.status === 'pending') actions = btn('new_review_link', 'Email me a review link', 'alt');
  if (q.status === 'approved') {
    actions = btn(q.investor_access ? 'investor_off' : 'investor_on',
      q.investor_access ? 'Remove investor area' : 'Add investor area', 'alt')
      + btn('reset', 'New password', 'alt') + btn('revoke', 'Revoke', 'danger');
  }
  return '<tr><td>' + esc(q.name) + '<br><small>' + esc(q.email) + '</small></td>'
    + '<td><span class="pill">' + esc(q.status) + '</span>' + (q.investor_access ? ' <span class="pill">investor</span>' : '')
    + (q.active_sessions ? ' <span class="pill">' + esc(q.active_sessions) + ' session(s)</span>' : '') + '</td>'
    + '<td>' + esc(auDate(q.signed_at)) + (q.expires_at ? '<br><small>ends ' + esc(auDate(q.expires_at)) + '</small>' : '')
    + '</td><td>' + actions + '</td></tr>';
}).join('');
return page(200, 'NDA requests', rows
  ? '<table><tr><th>Who</th><th>Status</th><th>Signed</th><th>Actions</th></tr>' + rows + '</table>'
  : '<p>No requests yet.</p>');
