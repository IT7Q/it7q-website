// website-enquiry, step 3: email Chris, Reply-To the enquirer (§4.7).
const r = $input.first().json.r;
if (r.result === 'limited') return reply(429, { error: 'rate_limited' });
const d = $('Check').first().json.db;
const label = (key, value) => (CFG.labels[key] || {})[value] || value || '-';
return next({
  mail: {
    to: CFG.mail.chris,
    replyTo: d.email,
    subject: 'Website enquiry: ' + label('service', d.service) + ' (' + d.name + ')',
    html: emailHtml('Website enquiry',
      '<table style="border-collapse:collapse;margin:16px 0">' + row('Name', d.name) + row('Email', d.email)
      + row('Phone', d.phone || '-') + row('Service', label('service', d.service))
      + row('Division', label('division', d.division)) + '</table>'
      + '<p style="white-space:pre-wrap">' + esc(d.message) + '</p>'
      + '<p style="font-size:13px;color:#5b6772">Reply to this email to answer ' + esc(d.name) + ' directly.</p>'),
  },
});
