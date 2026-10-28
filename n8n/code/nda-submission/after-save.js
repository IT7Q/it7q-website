// nda-submission, step 3: the reply, plus the two emails for a new request (§4.3 steps 5-7).
// Duplicates get the same 202 as new requests and no email (no enumeration, §4.1).
const r = $input.first().json.r;
if (r.result === 'limited') return reply(429, { error: 'rate_limited' });
if (r.result !== 'created') return reply(202, { ok: true });
const c = $('Check').first().json;
const d = c.db;
const record = '<table style="border-collapse:collapse;margin:16px 0">'
  + row('Name', d.name) + row('Email', d.email) + row('Organisation', d.org || '-')
  + row('Signed (typed name)', d.signature) + row('Signed at', auDate(r.signed_at) + ' (Brisbane time)')
  + row('NDA version', d.nda_version) + row('NDA SHA-256', d.nda_sha256)
  + row('Investor area requested', d.wants_investor ? 'Yes' : 'No') + '</table>';
const nda = '<div style="border-top:1px solid #d5dbe1;margin-top:16px;padding-top:8px;font-size:14px">'
  + __NDA_HTML__ + '</div>';
const reviewLink = CFG.hook_base + '/nda-review?t=' + encodeURIComponent(c.review);
return next({
  signer: {
    to: d.email,
    subject: 'Your IT7Q NDA: copy for your records',
    html: emailHtml('Your IT7Q NDA',
      '<p>Hi ' + esc(d.name) + ',</p><p>Thanks for your request. This is your copy of the confidentiality '
      + 'agreement you accepted, with the acceptance record. Every request is reviewed by hand; if yours is '
      + 'approved, we\'ll email your login details. Nothing is unlocked until then.</p>' + record + nda),
  },
  chris: {
    to: CFG.mail.chris,
    subject: 'NDA request to review: ' + d.name + (d.org ? ' (' + d.org + ')' : ''),
    html: emailHtml('New NDA request',
      '<p><a href="' + esc(reviewLink) + '">Review this request</a> (link works once, for 7 days; '
      + 'Cloudflare Access login required).</p>' + record
      + '<p><strong>Reason:</strong><br>' + esc(d.reason) + '</p>' + nda),
  },
});
