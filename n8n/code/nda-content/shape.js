// nda-content, step 2: web.content_get's verdict -> the reply the front end expects (§4.12).
const r = $input.first().json.r;
if (r.status === 401) return reply(401, { error: 'session' });
if (r.status === 403) return reply(403, { error: 'scope' });
if (r.status === 429) return reply(429, { error: 'rate_limited' });
if (r.status !== 200) return reply(500, { error: 'server' });
if (r.division === 'investors') return reply(200, { division: r.division, viewer: r.viewer, sections: r.sections });
return reply(200, { division: r.division, viewer: r.viewer, projects: r.projects });
