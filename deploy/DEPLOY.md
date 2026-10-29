# Deploying the website back end (Phase 4)

For Chris. This sets up the NDA and contact-form back end: one Postgres database, six n8n
workflows, the mailboxes and the Cloudflare side. Each step ends with a **Test**. Don't start the
next step until that test passes. If one fails, stop and send me the output.

Design: PLAN.md §4. The public site doesn't change in this phase; it keeps the switched-off
forms until Phase 6 (§7).

---

## Who runs what

Every step is tagged:

| Tag | Who | Where |
|---|---|---|
| **[chris · sudo]** | you, as `chris` | a terminal on Pantheon. Docker and psql need `sudo`. |
| **[claude]** | the `claude` user | Pantheon. Either ask me in a Claude session, or run the command yourself exactly as written: it starts with `sudo -u claude`. |
| **[browser]** | you | the n8n, Cloudflare and MXRoute web pages |

The repo lives at `/srv/work/it7q-website` and only `claude` can read it. You never need your
own copy:
- SQL files go straight from the repo into psql: `sudo cat <file> | sudo docker exec -i postgres psql ...`.
- Workflow files are copied to your home folder for importing (step 7).
- The scripts (`n8n_build.py`, `gated_sql.py`, `contract.py`) run as `claude`.

Pantheon's containers: `postgres` (superuser `it7q`), `n8n`, `n8n-runners` (the external task
runner that runs Code nodes) and `cloudflared`.

**Versions** (Q65): n8n **2.40.7** and Postgres **17.11**. I checked every node type and version
in the workflows against the n8n 2.40.7 source, and all of them are supported there:

| Node | Version used | Notes |
|---|---|---|
| Webhook | 2 | |
| Code | 2 | Runs in `n8n-runners` |
| IF | 2 | |
| HTTP Request | 4.2 | |
| Postgres | 2.5 | The query parameter is passed as an array, so n8n never splits it on commas |
| Send Email (SMTP) | 2.1 | |
| Respond to Webhook | 1.1 | |
| Schedule Trigger | 1.2 | |

The code avoids everything n8n 2.0 locked down: `$env`, `process`, `$evaluateExpression` and
unlisted modules. The one 2.x change that matters is that n8n now puts its own sandbox
security policy on every webhook reply. That breaks the review page's forms, and step 6g fixes
it at Cloudflare. If you upgrade n8n past 2.40.x, tell me first.

---

## What you'll need

| | Where it comes from | Where it goes | Ever in the repo or chat? |
|---|---|---|---|
| **S1** Postgres password for `it7q_web` | your password manager's generator (32+ chars) | psql `\password`, then the n8n credential | **No** |
| **S2** Edge header value | your password manager's generator (64 hex chars, or 40+ letters and digits) | n8n credential **and** the Cloudflare Transform Rule | **No** |
| **S3** Turnstile secret key | Cloudflare Turnstile | n8n credential (step 10) | **No** |
| **S4** SMTP password for `noreply@it7q.com.au` | MXRoute | n8n credential | **No** |
| Turnstile **site key** | Cloudflare Turnstile | `src/data/endpoints.json` at Phase 6 | Yes, it's public |
| Access **team name** + **AUD tag** | Cloudflare Zero Trust | `deploy/config.json` | Yes, not secret |

Keep S1–S4 in your password manager. Paste them straight from there into the place they go.
They never go in a file, a shell command line, the repo or a message to me.

**Order**: 1 mail → 2 database → 3 n8n runner check → 4 Turnstile → 5 n8n credentials →
6 Cloudflare → 7 import workflows → 8 gated content → 9 contract test (test mode) →
10 real Turnstile secret → 11 retention.

---

## 1. Mailboxes and DNS  [browser]

1. In MXRoute, create `noreply@it7q.com.au` (sending only) and `info@it7q.com.au` if it doesn't
   exist yet. Generate **S4** for `noreply@`.
2. Create `dmarc@it7q.com.au` as a **forwarder** to `chris@it7q.com.au`. DMARC reports land there.
3. In Cloudflare DNS for `it7q.com.au`:
   - **SPF**: one TXT record on `it7q.com.au` that includes what MXRoute's panel lists for sending.
   - **DKIM**: MXRoute signs with selector **`x`**, so the record that counts is the TXT
     record on **`x._domainkey`**, exactly as MXRoute's panel shows it. The old
     `it7q2026._domainkey` record is the wrong selector and nothing signs with it. It does no
     harm, but delete it once the test below passes, to avoid confusion later.
   - **DMARC**: TXT on `_dmarc`, `v=DMARC1; p=quarantine; rua=mailto:dmarc@it7q.com.au`.
     Keep `rua` on `dmarc@`, not your own address, so the forwarder decides where the reports go.
4. Note MXRoute's SMTP server name (in the welcome email or panel, `<something>.mxrouting.net`).

**Test**:
- On Pantheon (no sudo needed): `dig +short TXT x._domainkey.it7q.com.au` prints
  `"v=DKIM1; k=rsa; p=..."`, and `dig +short TXT _dmarc.it7q.com.au` shows `rua=mailto:dmarc@it7q.com.au`.
- [browser] Send a message from `noreply@` (MXRoute webmail) to a Gmail address. In Gmail,
  *Show original* must say `SPF: PASS`, `DKIM: PASS with domain it7q.com.au`, `DMARC: PASS`. In the
  raw headers, the `DKIM-Signature:` line must contain `d=it7q.com.au` and `s=x`.

---

## 2. Database  [chris · sudo]

The SQL makes two roles. `it7q_web_owner` owns everything and can't log in. `it7q_web` is what
n8n logs in as, and it can **only run nine functions**: no direct reading or writing of any
table (PLAN.md §4.2). The files:

- `deploy/sql/01-database.sql`: the roles, the database and the `web` schema. Run once.
- `deploy/sql/02-schema.sql`: the seven tables. Safe to re-run.
- `deploy/sql/03-functions.sql`: the functions and grants. Safe to re-run. When I fix the logic,
  this is the file that changes, and you re-run just this line.
- `deploy/sql/90-selftest.sql`: tests everything inside a transaction and rolls it back.

Each file is read by `sudo cat`, because only root and `claude` can read the repo, and piped
into psql inside the `postgres` container. Nothing is copied anywhere:
```
sudo cat /srv/work/it7q-website/deploy/sql/01-database.sql | sudo docker exec -i postgres psql -U it7q -d postgres -v ON_ERROR_STOP=1
sudo cat /srv/work/it7q-website/deploy/sql/02-schema.sql | sudo docker exec -i postgres psql -U it7q -d it7q_web -v ON_ERROR_STOP=1
sudo cat /srv/work/it7q-website/deploy/sql/03-functions.sql | sudo docker exec -i postgres psql -U it7q -d it7q_web -v ON_ERROR_STOP=1
```
To read a file before running it: `sudo less /srv/work/it7q-website/deploy/sql/01-database.sql`.

Set the login password (**S1**). The `-it` matters: psql asks for it twice, and it's never
echoed or saved in your shell history:
```
sudo docker exec -it postgres psql -U it7q -d it7q_web -c '\password it7q_web'
```

**Test**:
```
sudo cat /srv/work/it7q-website/deploy/sql/90-selftest.sql | sudo docker exec -i postgres psql -U it7q -d it7q_web -v ON_ERROR_STOP=1
```
It must print `NOTICE:  self-test passed (functions, as it7q_web)`, then
`NOTICE:  self-test passed (retention: {...})`, then `ROLLBACK`. Anything else: send me the output.
This is the first time this SQL runs on a real Postgres (there isn't one I can use on
Pantheon), so a mistake here is mine, not yours.

---

## 3. n8n task runner: allow `crypto` in Code nodes  [chris · sudo]

The workflows hash passwords and tokens with Node's built-in `crypto` module. In your setup the
Code nodes run in the **`n8n-runners`** container, not in `n8n`, so that's where `crypto` must be
allowed. In n8n 2.x the main `n8n` container doesn't need the setting.

What I found in n8n 2.40.7: **the stock `n8nio/runners` image already allows `crypto`.**
Its launcher config, `/etc/n8n-task-runners.json` inside the image, sets
`NODE_FUNCTION_ALLOW_BUILTIN=crypto` for the JavaScript runner. The launcher only passes a short
list of variables through to the runner, and `NODE_FUNCTION_ALLOW_BUILTIN` isn't one of them, so
**adding it to the container's environment in compose does nothing**. Don't add it there.

So this step is usually a check with nothing to change and **no restart**:

1. Confirm the runner is the stock image at the same version as n8n:
   ```
   sudo docker inspect n8n-runners --format '{{.Config.Image}}'
   ```
   Expect `n8nio/runners:2.40.7`, or `n8nio/runners` with a digest. The runner version must
   match n8n's.
2. Check for a custom launcher config mounted over the stock one:
   ```
   sudo docker inspect n8n-runners --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
   ```
   If nothing ends in `-> /etc/n8n-task-runners.json`, you're on the stock config, so skip to
   the **Test**.
3. Only if such a mount exists: open that host file (the left-hand path) with
   `sudo nano <path>`. In the `"javascript"` runner's `"env-overrides"`, make sure there's
   `"NODE_FUNCTION_ALLOW_BUILTIN": "crypto"`. If it lists other modules already, add
   `crypto` to the comma-separated list. Then restart just the runner. Find its compose file and
   service name with:
   ```
   sudo docker inspect n8n-runners --format '{{index .Config.Labels "com.docker.compose.project.config_files"}}  service: {{index .Config.Labels "com.docker.compose.service"}}'
   sudo docker compose -f <that compose file> restart <that service>
   ```
   **This causes a short outage for client webhooks.** For the few seconds the runner is
   restarting, any client workflow that reaches a Code node fails, and webhooks without Code
   nodes keep working. Pick a quiet time. Don't restart `n8n` itself for this: that takes every
   client webhook down for longer, and isn't needed.

**Test** [browser]: in n8n, make a scratch workflow with a Manual Trigger and one Code node:
`return [{ json: { ok: require('crypto').randomBytes(4).toString('hex') } }];`
Click *Execute workflow*. You should get 8 hex characters. Delete the scratch workflow.
If it says `Module 'crypto' is disallowed`, send me the output of the two commands in 1 and 2.

---

## 4. Turnstile widget  [browser]

Cloudflare dashboard → *Turnstile* → *Add widget*:
- Name `IT7Q website`. Hostnames `it7q.com.au` and `www.it7q.com.au`. While testing, add the
  Pages preview hostname too, e.g. `it7q-website.pages.dev`. Mode **Managed**.
- Keep the **site key** (public) for Phase 6. The **secret key** is **S3**: it goes into n8n
  at step 10, not before.

If you add a preview hostname, send it to me. I add `https://<that hostname>` to
`preview_origins` in `deploy/config.json`, rebuild the workflows and push, all before step 7.

**Test**: the widget shows in the Turnstile list with both hostnames.

---

## 5. n8n credentials  [browser]

n8n → *Credentials* → *Add credential*. The **names must match exactly**: the workflows find
their credentials by name.

| Name | Type | Fields |
|---|---|---|
| `IT7Q Edge Header` | Header Auth | Name: `X-IT7Q-Edge` · Value: **S2** |
| `Turnstile secret` | Custom Auth | JSON: `{"body": {"secret": "1x0000000000000000000000000000000AA"}}` |
| `Postgres it7q_web` | Postgres | Host `postgres` (the container name; n8n reaches it the same way for its own database) · Port `5432` · Database `it7q_web` · User `it7q_web` · Password **S1** · SSL: disable (internal Docker network only) |
| `Mail sender (noreply@)` | SMTP | User `noreply@it7q.com.au` · Password **S4** · Host: MXRoute's server from step 1 · Port `465` · SSL/TLS on |

`Turnstile secret` starts with Cloudflare's published **test** secret, which passes every
check, so step 9 can run the contract test from Pantheon. It's not a secret: it's printed in
Cloudflare's docs. Step 10 swaps in the real one.

**Test**: *Test connection* (or *Save*, which tests it) on `Postgres it7q_web` must succeed. SMTP is
tested by real email in step 9.

---

## 6. Cloudflare: hostname, rules, Access  [browser]

Everything here is on the `it7q.com.au` zone. The public webhook base becomes
`https://forms.it7q.com.au/webhook` (Q58). Only these paths are exposed:
`/webhook/nda-submission`, `nda-login`, `nda-content`, `website-enquiry`, `nda-review`.

**6a. Tunnel route.** Add `forms.it7q.com.au` to the existing tunnel, going to the same n8n
service as `hooks.nubius.com.au` today, **restricted by path**:
- Dashboard-managed tunnel: *Zero Trust → Networks → Tunnels → (tunnel) → Public hostname →
  Add*: subdomain `forms`, domain `it7q.com.au`, path
  `^/webhook/(nda-submission|nda-login|nda-content|website-enquiry|nda-review)$`. Use the same
  service as the existing hooks entry (normally `http://n8n:5678`). No restart needed.
- `config.yml`-managed tunnel: add an ingress rule with the same `hostname`, `path` and
  `service` **above** the final catch-all `http_status:404` rule, then
  `sudo docker restart cloudflared` [chris · sudo]. **That drops every client webhook for a few
  seconds** while the tunnel reconnects, so do it at a quiet time.

**6b. Edge header (request Transform Rule).** *Rules → Transform Rules → Modify Request Header →
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
GET is only answered by `nda-review`; n8n returns 404 for GET on the others.

**6e. Rate limit.** *Security → WAF → Rate limiting rules* (the free plan allows one):
name `forms: burst`, expression `(http.host eq "forms.it7q.com.au")`, counting by IP,
**20 requests per 10 seconds**, action Block for 10 seconds. The real limits (per email, per IP,
login lockout) are in Postgres. This only stops floods.

**6f. Cloudflare Access on the review page.** *Zero Trust → Access → Applications → Add →
Self-hosted*:
- Name `IT7Q NDA review`, domain `forms.it7q.com.au`, path `webhook/nda-review`.
- Policy `Chris only`: Action *Allow*, Include → *Emails* → `chris@it7q.com.au`. If you log in
  to Access with a different address, use that, and tell me so `access.allowed_emails` in
  `deploy/config.json` matches.
- Session duration 24 hours.
- After saving, open the application and copy its **Application Audience (AUD) Tag**. Your
  **team name** is the `<team>` in `<team>.cloudflareaccess.com` (*Settings → Custom pages* or
  the login URL). Neither is secret. Send both to me (Q64): I put them in
  `deploy/config.json`, rebuild the workflows, test, commit and push. Until then the review page
  refuses everyone, on purpose.

**6g. Review page security policy (response Transform Rule).** n8n 2.x puts its own
`Content-Security-Policy: sandbox ...` on every webhook reply and overwrites ours. That sandbox
gives the page no origin, so the browser sends `Origin: null` with the review forms. The
workflow refuses those (on purpose: it can't tell them from a forged post), and Access's
cookie may not be sent either. Cloudflare puts the right policy back on the way out:
*Rules → Transform Rules → Modify Response Header → Create*. Name `IT7Q review CSP`. Custom filter
expression:
```
(http.host eq "forms.it7q.com.au" and http.request.uri.path eq "/webhook/nda-review")
```
Then: *Set static*, header `Content-Security-Policy`, value (one line, exactly):
```
default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'; sandbox allow-forms allow-same-origin
```
This is stricter than n8n's sandbox: no scripts at all, and nothing loads from anywhere. It
only covers this one path, and it changes nothing for your other n8n workflows.

**Test** (from any computer):
```
curl -si https://forms.it7q.com.au/ | head -1                       # 403 or 404 (path not routed)
curl -si https://forms.it7q.com.au/rest/login | head -1             # 403 or 404, never n8n's login
curl -si https://forms.it7q.com.au/webhook-test/nda-login | head -1 # 403 or 404
curl -si https://forms.it7q.com.au/webhook/nda-review | grep -i '^location'   # → ...cloudflareaccess.com/...
```
The 6g rule is checked in step 9b, once the review page can show something.

---

## 7. Import the workflows

The six files are in `n8n/workflows/`. I generate them from `n8n/code/` with
`tools/n8n_build.py` and push them. You don't run the generator.

**7.0 [claude]: rebuild check.** Only needed if `deploy/config.json` changed since my last push.
I normally do this before telling you a build is ready:
```
sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/n8n_build.py --check
```
It must say `n8n workflows up to date: 6`. If it says `out of date`, ask me to rebuild and push.
Don't rebuild them yourself, because the change has to be committed.

**7.1 [chris · sudo]: copy them to your home folder.** The workflow files hold no secrets. They
contain public settings and the public NDA text.
```
sudo sh -c 'install -d -o chris -g chris -m 0755 /home/chris/it7q-import && install -o chris -g chris -m 0644 /srv/work/it7q-website/n8n/workflows/*.json /home/chris/it7q-import/'
ls /home/chris/it7q-import
```
That should list the six files. From Windows they're at `\\wsl$\<your distro>\home\chris\it7q-import`.
Alternatively, download them from GitHub (`n8n/workflows/`).

**7.2 [browser]: import and publish.** For each of `nda-submission`, `nda-login`,
`nda-content`, `website-enquiry`, `nda-review`, `nda-retention`:
1. n8n → *Create workflow* → *⋯* → *Import from File*, and choose the file.
2. Check that no node shows a red credential warning. If one does, pick the credential with
   the matching name.
3. *Save*.
4. **Publish**. In n8n 2.x, *Publish* replaces the old *Active* switch, and saving alone doesn't
   make webhooks live.

If `hooks.nubius.com.au` has older workflows on the same paths (`nda-submission` etc.),
unpublish those first: n8n refuses two live webhooks on one path.

When I send a changed workflow later, re-import it the same way. Open the existing workflow →
*⋯* → *Import from File* replaces its contents. Then *Save* and *Publish* again.

**Test 7a [chris · sudo]: the edge header is required.** This calls n8n directly, with no
Cloudflare and so no header. The n8n 2.x image doesn't reliably include `wget` or `curl`, but
it always has `node`, so use that:
```
sudo docker exec n8n node -e "fetch('http://127.0.0.1:5678/webhook/nda-content',{method:'POST',headers:{'content-type':'application/json'},body:'{}'}).then(r=>console.log(r.status),e=>console.log('ERR',e.message))"
```
It must print `403` (or `401`). Never `200` or `400`. `ERR` means n8n isn't listening on 5678
inside its container, so send me the output.
Fallback if that fails: run `sudo docker port n8n`. If it shows `5678/tcp -> 127.0.0.1:5678`,
the port is published to the rig, and you can run this from Pantheon itself (no sudo):
```
curl -s -o /dev/null -w '%{http_code}\n' -X POST http://127.0.0.1:5678/webhook/nda-content -H 'Content-Type: application/json' -d '{}'
```
This can't be tested through Cloudflare by leaving the header out, because 6b always adds it.
That's the point of 6b. The next test proves the other half: a faked header sent through
Cloudflare gets overwritten.

**Test 7b: the whole chain works** (Cloudflare → n8n → Postgres), from any computer. The fake
`X-IT7Q-Edge` header is there on purpose:
```
curl -si -X POST https://forms.it7q.com.au/webhook/nda-content -H 'Content-Type: application/json' -H 'X-IT7Q-Edge: fake' -d '{"division":"msp","token":"not-a-real-token-but-long-enough-0000"}'
```
Must be `HTTP/2 401` with `{"error":"session"}` and `cache-control: no-store`. A 403 means
Cloudflare didn't replace the header: check that 6b uses *Set*, and that S2 matches the credential.

**Test 7c: CORS.**
```
curl -si -X OPTIONS https://forms.it7q.com.au/webhook/nda-login -H 'Origin: https://it7q.com.au' -H 'Access-Control-Request-Method: POST' -H 'Access-Control-Request-Headers: content-type' | grep -i '^access-control'
```
Must list `access-control-allow-origin: https://it7q.com.au`.

---

## 8. Gated content (after your review)

`gated/*.json` holds what approved viewers see: one entry per project, written from the
private build pack under the §4.9 rules. That means no hostnames, ports, versions, tunnels or
internal tool names, and `tools/check.py` enforces it. Entries with a `notes` field are drafts
where the build pack had little or nothing, and the notes say what's missing. Notes never reach
the site.

1. [chris · sudo] Read each file, e.g. `sudo less /srv/work/it7q-website/gated/msp.json`, or on
   GitHub. Tell me what to change (Q63).
2. [claude] When a file is right, I set `"reviewed": true` in it and commit.
3. [chris · sudo] Load it all. It replaces the whole table in one transaction.

   The SQL is generated as `claude` and piped straight into psql. It never touches the disk, so
   there's no copy of the gated text left in `/tmp` or your home folder:
   ```
   sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/gated_sql.py | sudo docker exec -i postgres psql -U it7q -d it7q_web -v ON_ERROR_STOP=1
   ```
   `gated_sql.py` refuses to write anything while any file still says `"reviewed": false`. Then
   it prints why, and psql receives nothing and changes nothing.

**Test**: the output ends with a count per division (domus 1, fabricus 38, investors 1,
mentis 5, msp 6, opus 11, portus 3, tempestas 6), then `COMMIT`. You can do steps 9–11 before
this one: divisions just come back empty until the content is loaded.

---

## 9. Contract test (Turnstile still in test mode)

`tools/contract.py` sends the same requests the website does and checks every reply,
including the failure cases. It's the same script that tests the local mock on every build.
It runs as `claude` on Pantheon and only talks to `https://forms.it7q.com.au` through
Cloudflare.

**9a [claude]: forms, refusals, lockout, and one real request + enquiry.** I can run this one
for you, or you run:
```
sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --email <your test address>
```
It must end in `PASSED`. Then check your inboxes:
- the test address: "Your IT7Q NDA: copy for your records", with the acceptance record and the full NDA text;
- `chris@`: "NDA request to review: Contract Test (IT7Q)", with a **Review this request** link;
- `chris@`: "Website enquiry: Something else (Contract Test)". Hitting Reply must address the test address.

All three must come from `noreply@it7q.com.au` and pass SPF/DKIM/DMARC as in step 1 (`s=x`).

**9b: approve, then log in.**
1. [browser] Click **Review this request**. Cloudflare Access asks you to log in, then the review
   page shows the request.
   - **Check 6g first.** Open the browser's developer tools → *Network* → reload → click the
     `nda-review` request → *Response headers*. `content-security-policy` must start with
     `default-src 'none'`. If it starts with `sandbox allow-downloads`, the 6g rule isn't
     applied, and the Approve button will be refused.
   - Leave all seven divisions ticked and the investor box unticked → **Approve and email
     login**. The test address gets "Your IT7Q access is approved" with a password.
2. [claude, run by you] Run the logged-in checks. This one has to be you, because only you
   have the password. Run these three lines as they are. `read -rs` asks for the password
   without echoing it. It goes to the script on its standard input, never on a command line, and
   it isn't saved in your shell history or anywhere else:
   ```
   read -rsp 'Password: ' IT7Q_PW; echo
   printf '%s\n' "$IT7Q_PW" | sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --login <your test address> --password-stdin
   unset IT7Q_PW
   ```
   It must end in `PASSED`, including `investor area stays locked (403)`.

**9c [browser]: change it from the list.** Open `https://forms.it7q.com.au/webhook/nda-review`:
- **Add investor area** on the test entry, then re-run 9b step 2: now `investor area unlocks`.
- **New password** (tick "sure"): a new password arrives and the old one gets a 401.
- **Revoke** (tick "sure"): re-running 9b step 2 now **fails** at `approved login works`. That's correct.
- Click the same review-email link again: it must say the link expired or was used.

**9d [chris · sudo]: the audit trail.**
```
sudo docker exec postgres psql -U it7q -d it7q_web -c "SELECT event, count(*) FROM web.nda_audit GROUP BY 1 ORDER BY 1"
```
You should see `nda_submitted`, `nda_duplicate`, `nda_approved`, `login_failed`, `login_ok`,
`content_view`, `nda_revoked` and the rest.

Each contract run uses up 5 failed logins for Pantheon's IP. The IP limit is 20 per 15
minutes, so if you run it more than 3 times in a row, wait 15 minutes.

---

## 10. Switch to the real Turnstile secret

[browser] Edit credential `Turnstile secret` → JSON `{"body": {"secret": "<S3>"}}` → Save.

**Test** [claude]. I can run this, or you run:
```
sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --prod
```
Must end in `PASSED`. The line `Turnstile dummy token is refused (test secret removed)` proves
the test secret is gone. From now on only the real website's widget can submit forms. The
website gets its site key and the new webhook base at Phase 6.

---

## 11. Retention job

[browser] `IT7Q nda-retention` runs daily at 03:15 Brisbane time (PLAN.md §4.10) once it's
published. Open it and click *Execute workflow* once.

**Test**: the Retention node's output shows counts (mostly 0), and [chris · sudo]
```
sudo docker exec postgres psql -U it7q -d it7q_web -c "SELECT at, detail FROM web.nda_audit WHERE event = 'retention' ORDER BY at DESC LIMIT 1"
```
shows the same counts. The back-dated-rows check was already run by the self-test in step 2.

---

## Done

When 1–11 pass, the back end is live but nothing points at it yet. Phase 6 makes the site use
it: `src/data/endpoints.json` → `hooks` = `https://forms.it7q.com.au/webhook` and the
Turnstile site key, then the walk-through in PLAN.md §6.2.

## Undo

- [browser] Unpublish the six workflows. It's instant, and the site fails closed (PLAN.md §4.1).
- [browser] Disable the Cloudflare rules from 6b–6e and 6g, and remove the 6a public hostname.
- [chris · sudo] Database. This deletes every NDA record, so export first if any are real:
  ```
  sudo docker exec postgres psql -U it7q -d postgres -c 'DROP DATABASE it7q_web' -c 'DROP ROLE it7q_web' -c 'DROP ROLE it7q_web_owner'
  ```
- [chris · sudo] `sudo rm -r /home/chris/it7q-import` once the workflows are imported.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| Import shows `?` nodes or "unknown node type" | Shouldn't happen on 2.40.7 (versions checked above). Send me the n8n version and the node name. |
| `Module 'crypto' is disallowed` | Step 3: a custom runner config without `crypto`, or the runner image doesn't match n8n's version |
| Code node times out or "no runner available" | `n8n-runners` is down or can't reach n8n. `sudo docker logs --tail 50 n8n-runners` |
| 500 "Error in workflow" on every call | Open the workflow's *Executions*. Errors are kept for every workflow except `nda-login` and `nda-review`, which never store passwords |
| 403 on everything via Cloudflare | The 6b header value doesn't match the credential, character for character |
| Webhook 404 through Cloudflare, but the tunnel route is fine | The workflow is saved but not **published** (step 7.2) |
| Postgres credential: `no pg_hba.conf entry` or `password authentication failed` | S1 typed differently in psql and n8n, or the `postgres` container only accepts local logins. Send me the error text (no password) |
| Postgres node: "invalid input syntax for type json" | Send me the n8n version and the execution error |
| `permission denied for function` | `03-functions.sql` not re-run after a change, or run against the wrong database |
| No `access-control-allow-origin` in 7c | Send me the 7c output. I'll add the header to the Reply nodes instead |
| Review page: "needs a Cloudflare Access login" while logged in | `access.team` / `access.aud` not set yet (Q64), the updated workflow not re-imported, or the Access email differs from `allowed_emails` |
| Review page: "arrived without the IT7Q security policy" | The 6g rule is missing, or its path or host doesn't match |
| Emails missing | SMTP credential, then spam folders, then SPF/DKIM (step 1, selector `x`) |
| `sudo: unable to change directory` or `could not change to directory` warnings with `sudo -u claude` | Harmless. Or `cd /` first |
