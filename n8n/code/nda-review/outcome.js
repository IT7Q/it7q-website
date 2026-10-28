// nda-review POST, step 2: the result page, and the email that goes with it (if any).
const r = $input.first().json.r;
const v = $('Verify POST').first().json;
if (!r.ok) return page(409, 'Not done', '<p class="msg err">' + esc(r.error) + '</p>');
const done = (text, mail) => {
  const out = page(200, 'Done', '<p class="msg">' + esc(text) + '</p>');
  out[0].json.go = Boolean(mail);
  out[0].json.mail = mail || null;
  return out;
};
const login = (heading, intro) => ({
  to: r.email,
  subject: heading,
  html: emailHtml(heading, '<p>Hi ' + esc(r.name) + ',</p><p>' + intro + '</p>'
    + '<table style="border-collapse:collapse;margin:16px 0">' + row('Login page', CFG.site_base + '/access/')
    + row('Email', r.email) + row('Password', v.password) + '</table>'
    + '<p>Please keep these details to yourself: access is personal under the NDA, and everything you view '
    + 'is marked with your email address.</p>'),
});
if (r.action === 'approve') {
  return done('Approved ' + r.email + ' (' + r.divisions.join(', ') + (r.investor ? ', investor area' : '')
    + '). Login details emailed. NDA term ends ' + auDate(r.expires_at) + '.',
  login('Your IT7Q access is approved', 'Your NDA request has been approved. You can now log in to see the '
    + 'confidential detail on the IT7Q website.'));
}
if (r.action === 'reset') {
  return done('New password emailed to ' + r.email + '. Their sessions were ended.',
    login('Your new IT7Q password', 'Here is a new password for the IT7Q website. The old one no longer works.'));
}
if (r.action === 'new_review_link') {
  const link = CFG.hook_base + '/nda-review?t=' + encodeURIComponent(v.review);
  return done('A new review link for ' + r.request.email + ' is on its way to ' + CFG.mail.chris + '.', {
    to: CFG.mail.chris,
    subject: 'NDA request to review: ' + r.request.name,
    html: emailHtml('NDA request to review', '<p><a href="' + esc(link) + '">Review this request</a> '
      + '(works once, for 7 days).</p><p>' + esc(r.request.name) + ' &lt;' + esc(r.request.email) + '&gt;</p>'),
  });
}
const said = { reject: 'Rejected', revoke: 'Revoked (sessions ended)', investor_on: 'Investor area added for',
  investor_off: 'Investor area removed for' };
return done(said[r.action] + ' ' + r.email + '.');
