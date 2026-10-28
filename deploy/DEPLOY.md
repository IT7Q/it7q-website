# Deploying the website back end (Phase 4)

For Chris. This sets up the NDA and contact-form back end: one Postgres database, six n8n
workflows, two mailboxes and the Cloudflare side. I (Claude) can't touch n8n, Docker or
Cloudflare, so every step here is yours. Each step ends with a **Test**. Don't start the next
step until that test passes. If one fails, stop and send me the output.

Design: PLAN.md §4. The public site doesn't change in this phase; it keeps the switched-off
forms until Phase 6 (§7).

---

## What you'll need

| | Where it comes from | Where it goes | Ever in the repo or chat? |
|---|---|---|---|
| **S1** Postgres password for `it7q_web` | `openssl rand -base64 32` | psql `\password`, then the n8n credential | **No** |
| **S2** Edge header value | `openssl rand -hex 32` | n8n credential **and** the Cloudflare Transform Rule | **No** |
| **S3** Turnstile secret key | Cloudflare Turnstile | n8n credential (step 10) | **No** |
| **S4** SMTP password for `noreply@it7q.com.au` | MXRoute | n8n credential | **No** |
| Turnstile **site key** | Cloudflare Turnstile | `src/data/endpoints.json` at Phase 6 | Yes, it's public |
| Access **team name** + **AUD tag** | Cloudflare Zero Trust | `deploy/config.json` | Yes, not secret |

Keep S1–S4 in your password manager. Paste them straight from there into the place they go.
They never go in a file, a shell command line, the repo or a message to me.

Placeholders below: `<postgres>` and `<n8n>` are your container names (`docker ps`), and
`<pg-superuser>` is the superuser your Postgres container uses. Run the commands from your own
up-to-date clone of this repo (`git pull`).

**Versions**: written for a current n8n 1.x and Postgres 12 or newer. Check them first:
n8n → *Settings → About*, and `docker exec <postgres> psql -U <pg-superuser> -tc 'show server_version'`.
If n8n is older than about a year, tell me the version before importing anything.

**Order**: 1 mail → 2 database → 3 n8n setting → 4 Turnstile → 5 n8n credentials →
6 Cloudflare → 7 import workflows → 8 gated content → 9 contract test (test mode) →
10 real Turnstile secret → 11 retention.

---

## 1. Mailboxes (MXRoute)

1. Create `noreply@it7q.com.au` (sending only) and `info@it7q.com.au` if it doesn't exist yet.
   Generate **S4** for `noreply@`.
2. In Cloudflare DNS for `it7q.com.au`, check that the SPF, DKIM and DMARC records match what
   MXRoute's control panel lists for the domain. SPF must include MXRoute's sending hosts. The
   DKIM TXT record must be exactly MXRoute's. A starting DMARC of `v=DMARC1; p=quarantine; rua=mailto:info@it7q.com.au` is fine.
3. Note MXRoute's SMTP server name (in the welcome email or panel, `<something>.mxrouting.net`).

**Test**: send a message from `noreply@` (MXRoute webmail) to a Gmail address. In Gmail,
*Show original* must say `SPF: PASS`, `DKIM: PASS`, `DMARC: PASS`.

---

## 2. Database

The SQL makes two roles. `it7q_web_owner` owns everything and can't log in. `it7q_web` is what
n8n logs in as, and it can **only run nine functions**: no direct reading or writing of any
table (PLAN.md §4.2). The files:

- `deploy/sql/01-database.sql`: the roles, the database and the `web` schema. Run once.
- `deploy/sql/02-schema.sql`: the seven tables. Safe to re-run.
- `deploy/sql/03-functions.sql`: the functions and grants. Safe to re-run; this is what I'll
  change if the logic needs a fix.
- `deploy/sql/90-selftest.sql`: tests everything inside a transaction and rolls it back.

```
docker exec -i <postgres> psql -U <pg-superuser> -d postgres -v ON_ERROR_STOP=1 < deploy/sql/01-database.sql
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web -v ON_ERROR_STOP=1 < deploy/sql/02-schema.sql
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web -v ON_ERROR_STOP=1 < deploy/sql/03-functions.sql
```
Set the login password (**S1**). The `-it` matters: psql asks for it twice, and it's never
echoed or saved in your shell history:
```
docker exec -it <postgres> psql -U <pg-superuser> -d it7q_web -c '\password it7q_web'
```

**Test**:
```
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web -v ON_ERROR_STOP=1 < deploy/sql/90-selftest.sql
```
It must print `NOTICE:  self-test passed (functions, as it7q_web)`, then
`NOTICE:  self-test passed (retention: {...})`, then `ROLLBACK`. Anything else: send me the output.
This is the first time this SQL runs on a real Postgres (there isn't one I can use on
Pantheon), so a mistake here is mine, not yours.

---

## 3. n8n setting: allow `crypto` in Code nodes

The workflows hash passwords and tokens with Node's built-in `crypto` module. n8n blocks it
unless told otherwise. In the n8n service's environment in your compose file under
`/opt/it7q`, add:
```
NODE_FUNCTION_ALLOW_BUILTIN=crypto
```
If your setup runs Code nodes in a separate task-runner container (`N8N_RUNNERS_MODE=external`),
add it to that container too. Then `docker compose up -d` for n8n.

**Test**: in n8n, make a scratch workflow with one Code node:
`return [{ json: { ok: require('crypto').randomBytes(4).toString('hex') } }];`
Run it. You should get 8 hex characters. Delete the scratch workflow.

---

## 4. Turnstile widget

Cloudflare dashboard → *Turnstile* → *Add widget*:
- Name `IT7Q website`. Hostnames `it7q.com.au` and `www.it7q.com.au` (add the Pages preview
  hostname too while testing, e.g. `it7q-website.pages.dev`). Mode **Managed**.
- Keep the **site key** (public) for Phase 6. The **secret key** is **S3**: it goes into n8n
  at step 10, not before.

If you add a preview hostname, also add `https://<that hostname>` to `preview_origins` in
`deploy/config.json` (or tell me), and run `python3 tools/n8n_build.py` before step 7.

**Test**: the widget shows in the Turnstile list with both hostnames.

---

## 5. n8n credentials

n8n → *Credentials* → *Add credential*. The **names must match exactly**: the workflows find
their credentials by name.

| Name | Type | Fields |
|---|---|---|
| `IT7Q Edge Header` | Header Auth | Name: `X-IT7Q-Edge` · Value: **S2** |
| `Turnstile secret` | Custom Auth | JSON: `{"body": {"secret": "1x0000000000000000000000000000000AA"}}` |
| `Postgres it7q_web` | Postgres | Host: the Postgres container's name on n8n's Docker network (the same host n8n uses for its own DB) · Database `it7q_web` · User `it7q_web` · Password **S1** · SSL: disable (internal network only) |
| `Mail sender (noreply@)` | SMTP | User `noreply@it7q.com.au` · Password **S4** · Host: MXRoute's server from step 1 · Port `465` · SSL/TLS on |

`Turnstile secret` starts with Cloudflare's published **test** secret, which passes every
check, so step 9 can run the contract test from your terminal. It's not a secret: it's
printed in Cloudflare's docs. Step 10 swaps in the real one.

**Test**: *Test connection* on `Postgres it7q_web` must succeed. (SMTP is tested by real
email in step 9.)

---

## 6. Cloudflare: hostname, rules, Access

Everything here is on the `it7q.com.au` zone. The public webhook base becomes
`https://forms.it7q.com.au/webhook` (Q58). Only these paths are exposed:
`/webhook/nda-submission`, `nda-login`, `nda-content`, `website-enquiry`, `nda-review`.

**6a. Tunnel route.** Add `forms.it7q.com.au` to the existing tunnel, going to the same n8n
service as `hooks.nubius.com.au` today, **restricted by path**:
- Dashboard-managed tunnel: *Zero Trust → Networks → Tunnels → (tunnel) → Public hostname →
  Add*: subdomain `forms`, domain `it7q.com.au`, path
  `^/webhook/(nda-submission|nda-login|nda-content|website-enquiry|nda-review)$`, service the
  same as the existing hooks entry.
- `config.yml`-managed tunnel: add an ingress rule with the same `hostname`, `path` and
  `service` **above** the final catch-all `http_status:404` rule, then restart cloudflared.

**6b. Edge header (Transform Rule).** *Rules → Transform Rules → Modify Request Header →
Create*. Name `IT7Q edge header`. Custom filter expression:
```
(http.host eq "forms.it7q.com.au" and starts_with(http.request.uri.path, "/webhook/"))
```
Then: *Set static*, header `X-IT7Q-Edge`, value **S2**. "Set" overwrites anything a visitor
sends, so the header can't be faked from outside.

**6c. No caching.** *Rules → Cache Rules → Create*: same expression as 6b → *Bypass cache*.

**6d. Block everything else (WAF custom rule).** *Security → WAF → Custom rules → Create*,
name `forms: allow-list`, action **Block**:
```
(http.host eq "forms.it7q.com.au" and not (
  http.request.uri.path in {"/webhook/nda-submission" "/webhook/nda-login" "/webhook/nda-content" "/webhook/website-enquiry" "/webhook/nda-review"}
  and http.request.method in {"POST" "OPTIONS" "GET"}
))
```
(GET is only answered by `nda-review`; n8n returns 404 for GET on the others.)

**6e. Rate limit.** *Security → WAF → Rate limiting rules* (the free plan allows one):
name `forms: burst`, expression `(http.host eq "forms.it7q.com.au")`, counting by IP,
**20 requests per 10 seconds**, action Block for 10 seconds. The real limits (per email, per IP,
login lockout) are in Postgres. This only stops floods.

**6f. Cloudflare Access on the review page.** *Zero Trust → Access → Applications → Add →
Self-hosted*:
- Name `IT7Q NDA review`, domain `forms.it7q.com.au`, path `webhook/nda-review`.
- Policy `Chris only`: Action *Allow*, Include → *Emails* → `chris@it7q.com.au`. (If you log in
  to Access with a different address, use that, and change `access.allowed_emails` in
  `deploy/config.json` to match.)
- Session duration 24 hours.
- After saving, open the application and copy its **Application Audience (AUD) Tag**. Your
  **team name** is the `<team>` in `<team>.cloudflareaccess.com` (*Settings → Custom pages* or
  the login URL). Neither is secret.
- Put both in `deploy/config.json` → `access.team` and `access.aud` and run
  `python3 tools/n8n_build.py`, or send them to me and I'll commit the change. Until then the
  review page refuses everyone, on purpose.

**Test** (from any computer):
```
curl -si https://forms.it7q.com.au/ | head -1                       # 404 (path not routed)
curl -si https://forms.it7q.com.au/rest/login | head -1             # 403 or 404, never n8n's login
curl -si https://forms.it7q.com.au/webhook-test/nda-login | head -1 # 403 or 404
curl -si https://forms.it7q.com.au/webhook/nda-review | grep -i '^location'   # → ...cloudflareaccess.com/...
```

---

## 7. Import the workflows

The six files are in `n8n/workflows/`. They're generated from `n8n/code/` by
`tools/n8n_build.py`, so if you changed `deploy/config.json`, run that first.

For each of `nda-submission`, `nda-login`, `nda-content`, `website-enquiry`, `nda-review`,
`nda-retention`: n8n → *Workflows → Import from file* → open it, check that no node shows a red
credential warning (if one does, pick the credential with the matching name) → *Save* →
switch it **Active**.

If `hooks.nubius.com.au` has older workflows on the same paths (`nda-submission` etc.),
deactivate those first: n8n refuses two active webhooks on one path.

**Test 7a: the edge header is required.** From the box, straight to n8n (no Cloudflare,
so no header):
```
docker exec <n8n> wget -qSO- --header='Content-Type: application/json' --post-data='{}' http://localhost:5678/webhook/nda-content 2>&1 | head -1
```
Must show `403` (or `401`). Never `200` or `400`.

**Test 7b: the whole chain works** (Cloudflare → n8n → Postgres):
```
curl -si -X POST https://forms.it7q.com.au/webhook/nda-content -H 'Content-Type: application/json' -d '{"division":"msp","token":"not-a-real-token-but-long-enough-0000"}'
```
Must be `HTTP/2 401` with `{"error":"session"}` and `cache-control: no-store`.

**Test 7c: CORS.**
```
curl -si -X OPTIONS https://forms.it7q.com.au/webhook/nda-login -H 'Origin: https://it7q.com.au' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type' | grep -i '^access-control'
```
Must list `access-control-allow-origin: https://it7q.com.au`.

---

## 8. Gated content (after your review)

`gated/*.json` holds what approved viewers see: one entry per project, written from the
private build pack under the §4.9 rules (no hostnames, ports, versions, tunnels or internal tool
names; `tools/check.py` enforces that). Entries with a `notes` field are drafts where the build
pack had little or nothing; the notes say what's missing. Notes never reach the site.

1. Read each file. Edit it, or tell me what to change.
2. When a file is right, set `"reviewed": true` in it and commit.
3. Load it all (it replaces the whole table in one transaction):
```
python3 tools/gated_sql.py > /tmp/it7q-gated.sql
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web < /tmp/it7q-gated.sql
rm /tmp/it7q-gated.sql
```
`gated_sql.py` refuses to write anything while any file still says `"reviewed": false`.

**Test**: the output ends with a count per division (domus 1, fabricus 38, investors 1,
mentis 5, msp 6, opus 11, portus 3, tempestas 6), then `COMMIT`. You can do steps 9–11 before
this one: divisions just come back empty until the content is loaded.

---

## 9. Contract test (Turnstile still in test mode)

`tools/contract.py` sends the same requests the website does and checks every reply,
including the failure cases. It's the same script that tests the local mock on every build.
It needs only Python 3, with no packages.

**9a. Forms, refusals, lockout, and one real request + enquiry:**
```
python3 tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --email <your test address>
```
It must end in `PASSED`. Then check your inboxes:
- the test address: "Your IT7Q NDA: copy for your records", with the acceptance record and the full NDA text;
- `chris@`: "NDA request to review: Contract Test (IT7Q)", with a **Review this request** link;
- `chris@`: "Website enquiry: Something else (Contract Test)". Hitting Reply must address the test address.

All three must come from `noreply@it7q.com.au` and pass SPF/DKIM/DMARC as in step 1.

**9b. Approve, then log in:**
1. Click **Review this request**. Cloudflare Access asks you to log in, then the review page
   shows the request. Leave all seven divisions ticked and the investor box unticked →
   **Approve and email login**. The test address gets "Your IT7Q access is approved" with a password.
2. Run the logged-in checks (it asks for that password; nothing is saved):
```
python3 tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --login <your test address>
```
Must end in `PASSED`, including `investor area stays locked (403)`.

**9c. Change it from the list.** Open `https://forms.it7q.com.au/webhook/nda-review`:
- **Add investor area** on the test entry, then re-run 9b step 2: now `investor area unlocks`.
- **New password** (tick "sure"): a new password arrives and the old one gets a 401.
- **Revoke** (tick "sure"): re-running 9b step 2 now **fails** at `approved login works`. That's correct.
- Click the same review-email link again: it must say the link expired or was used.

**9d. The audit trail**:
```
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web -c "SELECT event, count(*) FROM web.nda_audit GROUP BY 1 ORDER BY 1"
```
You should see `nda_submitted`, `nda_duplicate`, `nda_approved`, `login_failed`, `login_ok`,
`content_view`, `nda_revoked` and the rest.

Each contract run uses up 5 failed logins for your IP. The IP limit is 20 per 15 minutes, so
if you run it more than 3 times in a row, wait 15 minutes.

---

## 10. Switch to the real Turnstile secret

Edit credential `Turnstile secret` → JSON `{"body": {"secret": "<S3>"}}` → Save.

**Test**:
```
python3 tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --prod
```
Must end in `PASSED`. The line `Turnstile dummy token is refused (test secret removed)` proves
the test secret is gone. From now on only the real website's widget can submit forms. The
website gets its site key and the new webhook base at Phase 6.

---

## 11. Retention job

`IT7Q nda-retention` runs daily at 03:15 Brisbane time (PLAN.md §4.10). Open it and click
*Execute workflow* once.

**Test**: the Retention node's output shows counts (mostly 0), and
```
docker exec -i <postgres> psql -U <pg-superuser> -d it7q_web -c "SELECT at, detail FROM web.nda_audit WHERE event = 'retention' ORDER BY at DESC LIMIT 1"
```
shows the same counts. The back-dated-rows check was already run by the self-test in step 2.

---

## Done

When 1–11 pass, the back end is live but nothing points at it yet. Phase 6 makes the site use
it: `src/data/endpoints.json` → `hooks` = `https://forms.it7q.com.au/webhook` and the
Turnstile site key, then the walk-through in PLAN.md §6.2.

## Undo

- Switch the six workflows to inactive (instant; the site fails closed, PLAN.md §4.1).
- Disable the Cloudflare rules from 6b–6e and remove the 6a public hostname.
- Database: `DROP DATABASE it7q_web; DROP ROLE it7q_web; DROP ROLE it7q_web_owner;` (as the
  superuser, connected to `postgres`). This deletes every NDA record, so export first if any are real.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| Import shows `?` nodes or "unknown node type" | n8n too old for these node versions: tell me the version |
| `Cannot find module 'crypto'` / "not allowed" | Step 3 not applied (or not on the task-runner container) |
| 500 "Error in workflow" on every call | Open the workflow's *Executions* (errors are kept for every workflow except `nda-login` and `nda-review`, which never store passwords) |
| 403 on everything via Cloudflare | The 6b header value doesn't match the credential, character for character |
| Postgres node: "invalid input syntax for type json" | n8n split the query parameter on commas; tell me your n8n version |
| `permission denied for function` | `03-functions.sql` not run after a change, or run as the wrong user |
| No `access-control-allow-origin` in 7c | Tell me the n8n version; I'll add the header to the Reply nodes instead |
| Review page: "needs a Cloudflare Access login" while logged in | `access.team` / `access.aud` in `deploy/config.json` not set, workflows not rebuilt and re-imported, or the Access email differs from `allowed_emails` |
| Emails missing | SMTP credential, then spam folders, then SPF/DKIM (step 1) |
