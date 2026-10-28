// ---- nda-review/_page.js: HTML for the review pages (pasted after common.js in this workflow).
// The Page node sends these with a CSP of default-src 'none', no-store and no-referrer.
const REVIEW_URL = CFG.hook_base + '/nda-review';
function page(status, title, inner) {
  return [{ json: { go: false, status, html: '<!doctype html><html lang="en-AU"><head><meta charset="utf-8">'
    + '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex">'
    + '<title>' + esc(title) + '</title><style>'
    + 'body{font-family:system-ui,Arial,sans-serif;margin:0;padding:16px;background:#f4f6f8;color:#14202b;line-height:1.5}'
    + 'main{max-width:960px;margin:0 auto;background:#fff;padding:20px;border-radius:8px}'
    + 'table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid #e1e5e9;vertical-align:top}'
    + 'button{font:inherit;padding:6px 12px;margin:2px;border-radius:4px;border:1px solid #1c3b57;background:#1c3b57;color:#fff;cursor:pointer}'
    + 'button.alt{background:#fff;color:#1c3b57}button.danger{background:#a4262c;border-color:#a4262c}'
    + 'fieldset{border:1px solid #d5dbe1;border-radius:6px;margin:12px 0}label{display:block;margin:4px 0}'
    + '.pill{display:inline-block;padding:0 8px;border-radius:10px;background:#e1e5e9;font-size:13px}'
    + '.msg{padding:12px;border-radius:6px;background:#eef6ee}.err{background:#fbeaea}form.inline{display:inline}'
    + '</style></head><body><main><h1>' + esc(title) + '</h1>' + inner
    + '<p><a href="' + esc(REVIEW_URL) + '">All requests</a></p></main></body></html>' } }];
}
function divisionBoxes(selected) {
  // One field per division (div_msp=1, ...), so it doesn't matter how n8n parses repeated names.
  return CFG.divisions.map((d) => '<label><input type="checkbox" name="div_' + esc(d) + '" value="1"'
    + (selected.includes(d) ? ' checked' : '') + '> ' + esc(d.toUpperCase()) + '</label>').join('');
}
function requestTable(q) {
  return '<table>'
    + [['Name', q.name], ['Email', q.email], ['Organisation', q.org || '-'], ['Reason', q.reason],
      ['Investor area requested', q.wants_investor ? 'Yes' : 'No'], ['NDA version', q.nda_version],
      ['Signed', auDate(q.signed_at)], ['Status', q.status]]
      .map((r) => '<tr><th>' + esc(r[0]) + '</th><td>' + esc(r[1]) + '</td></tr>').join('') + '</table>';
}
// ---- end _page.js
