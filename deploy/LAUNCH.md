# Launching the website (Phase 6)

For Chris. This puts the site live on Cloudflare Pages at `it7q.com.au`, redirects `www` to the
apex, puts the footer's Staff link behind Cloudflare Access, and lists the checks to run after.
Each step ends with a **Test**. Don't start the next step until it passes. If one fails, stop and
send me the output. I don't deploy anything: every dashboard step is yours.

The step tags work the same as in DEPLOY.md: **[chris · sudo]** is your terminal on Pantheon,
**[claude]** is me (or you, with the `sudo -u claude` command as written), and **[browser]** is the
Cloudflare dashboard.

---

## Before you start

- **DEPLOY.md steps 1–7, 9, 10 and 11 pass.** That includes step 10, the real Turnstile secret,
  with `contract.py --prod` ending in `PASSED`. Step 8 (gated content) can come after launch;
  divisions show as empty to approved viewers until it's loaded.
- **Already done in the repo** (commit "Phase 6 prep"): `src/data/endpoints.json` points at
  `https://forms.it7q.com.au/webhook`, and `tools/check.py` now fails any build whose webhook
  base is on nubius.
- **Legal pages (decided 3 Nov).** The NDA, Privacy and Terms go live without the lawyer's review,
  and you approve NDA requests from launch. The review is planned **when funds allow** (PLAN.md
  §4.15). Until then, gated content stays at feature level (PLAN.md §4.9). After the review, a
  changed NDA becomes a new version and approved viewers re-accept it at their next login
  (PLAN.md §4.14). The pages show "Last updated" dates, not draft notes, and
  `tools/check.py --launch` fails if a draft note comes back.

## How it's hosted: Direct Upload (recommended), not Git integration

| | **Direct Upload** of `dist/` (recommended) | Git integration |
|---|---|---|
| What Cloudflare gets | Only the built public site (about 60 files, 3 MB) | Read access to the whole private repo: `gated/` (NDA-only content), `n8n/`, `deploy/`, the plan |
| Where it's built and checked | On Pantheon, by the same build and `check.py --launch` that the tests use, before anything leaves the box | On Cloudflare's build servers, with `pip install` of Pillow there and my checks running somewhere I can't see |
| What it needs | Nothing new: no API token on Pantheon, no Node or `wrangler`, no GitHub app | The Cloudflare GitHub app installed on the `IT7Q` org with access to this repo |
| Releasing | Rebuild, copy, drag the folder into the dashboard (steps 2–4, about 5 minutes) | Merge to `main` |
| Rollback | One click on an earlier deployment | Same |

Direct Upload keeps the gated content and the deploy notes off third-party build servers. Nothing
new gets installed on a box that's been compromised before, and what goes live is exactly what
passed the checks. The cost is that each release is a manual upload. For a site that changes a
few times a month, that's fine. Note: a Pages project made with Direct Upload can't be switched
to Git integration later; you'd make a new project. (I'll update PLAN.md §6, which assumed Git.)

The dashboard upload limits (1,000 files, 25 MB per file) are far above this site's size.

---

## 1. Turnstile site key  [browser → claude]

Cloudflare → *Turnstile* → `IT7Q website` → copy the **site key** (it starts `0x`; it's public,
so sending it in chat is fine. The **secret** key never goes in chat). Send it to me.

I put it in `src/data/endpoints.json` in place of `PLACEHOLDER-turnstile-site-key`, then build,
run `check.py --launch`, commit and push.

**Test**: I'll send you the commit and the `check passed: ... LAUNCH gates` line.

## 2. Build the release  [claude]

I normally do this and tell you when it's ready, or run:
```
sudo -u claude sh -c 'cd /srv/work/it7q-website && git status --short && .venv/bin/python tools/build.py && .venv/bin/python tools/check.py --launch && find dist -type f | wc -l'
```
**Test**: `git status --short` prints nothing (the build is of committed code), the build ends in
`check passed`, then `check passed: ... LAUNCH gates`, then a file count. Write the count down.

## 3. Copy the release to your home folder  [chris · sudo]

```
sudo sh -c 'rm -rf /home/chris/it7q-release && cp -r /srv/work/it7q-website/dist /home/chris/it7q-release && chown -R chris:chris /home/chris/it7q-release'
find /home/chris/it7q-release -type f | wc -l
ls -a /home/chris/it7q-release
```
**Test**: the count matches step 2, and the listing includes `_headers`, `index.html`, `404.html`
and `favicon.svg`. `_headers` carries the security headers, so it must be uploaded too. From
Windows the folder is `\\wsl$\<your distro>\home\chris\it7q-release`.

## 4. Create the Pages project and upload  [browser]

Cloudflare → *Workers & Pages* → *Create* → *Pages* → **Upload assets** (Direct Upload):
1. Project name `it7q-website`, then *Create project*.
2. Drag the **`it7q-release` folder** into the upload box (the folder itself, so `_headers` comes
   with it), then *Deploy site*.
3. Project → *Metrics* → **Web Analytics** → *Enable* (Q20). It's cookieless, and the site's CSP
   already allows its script.

**Test** (from any computer):
```
curl -sI https://it7q-website.pages.dev/ | grep -iE '^(HTTP|content-security-policy|strict-transport-security)'
curl -s -o /dev/null -w '%{http_code}\n' https://it7q-website.pages.dev/no-such-page/
```
The first must show `HTTP/2 200`, a CSP containing `connect-src 'self' https://forms.it7q.com.au`,
and HSTS. The second must print `404`. Click around `it7q-website.pages.dev` on your phone and
computer. The forms there will show their "can't send right now" message. That's expected:
Turnstile and the webhooks only accept `it7q.com.au` and `www`.

## 5. Attach `it7q.com.au` and `www`  [browser]

1. First see what the apex points at today: Cloudflare → `it7q.com.au` → *DNS → Records*, look
   for `A`, `AAAA` or `CNAME` records on `it7q.com.au` and `www`. If the old site is there, note
   the values (that's your way back) before the next step replaces them.
2. Project `it7q-website` → *Custom domains* → *Set up a custom domain* → `it7q.com.au` →
   *Continue* → *Activate domain*. Because the zone is on Cloudflare, Pages makes the DNS record
   itself (a CNAME to `it7q-website.pages.dev`, flattened at the apex). If it says a record
   already exists, delete that old record in *DNS* and try again.
3. Same again for `www.it7q.com.au`.
4. Wait until both show **Active** (usually a few minutes; certificates included).

**Test**:
```
curl -sI https://it7q.com.au/ | head -1        # HTTP/2 200
curl -sI https://www.it7q.com.au/ | head -1    # HTTP/2 200 for now; step 6 makes it 301
```

## 6. Redirect `www` to the apex  [browser]

Cloudflare → `it7q.com.au` → *Rules* → *Redirect Rules* → *Create rule* → *Single Redirect*:
- Name `www to apex`. Custom filter expression: `(http.host eq "www.it7q.com.au")`
- Then: *Dynamic*, expression `concat("https://it7q.com.au", http.request.uri.path)`, status
  **301**, **Preserve query string** on.

**Test**:
```
curl -sI 'https://www.it7q.com.au/about/?x=1' | grep -iE '^(HTTP|location)'
```
Must be `HTTP/2 301` and `location: https://it7q.com.au/about/?x=1`.

## 7. Staff link: `staff.it7q.com.au` behind Cloudflare Access  [browser, then chris · sudo]

The footer's "Staff" link goes to `https://staff.it7q.com.au` (Q52). Access needs something behind
it, so for now that's a one-page placeholder ("You're signed in. Staff tools will appear here."),
kept in `deploy/staff/` with strict headers and `noindex`. When real staff tools exist, they replace
it behind the same Access app.

**Access first, so the hostname is never open, even for a minute:**

7a. Zero Trust → *Access* → *Applications* → *Add an application* → *Self-hosted*:
- Name `IT7Q staff`. Destinations (add all three):
  `staff.it7q.com.au`, `it7q-staff.pages.dev`, `*.it7q-staff.pages.dev`.
  The two `pages.dev` names stop anyone going round Access via the project's own Cloudflare address.
- Policy `IT7Q staff`: Action *Allow*, Include → *Emails* → `chris@it7q.com.au`. Add staff
  emails here later. Login method: the default one-time PIN is fine.
- Session duration 24 hours. Save.

7b. Copy the placeholder to your home folder [chris · sudo]:
```
sudo sh -c 'rm -rf /home/chris/it7q-staff && cp -r /srv/work/it7q-website/deploy/staff /home/chris/it7q-staff && chown -R chris:chris /home/chris/it7q-staff'
ls -a /home/chris/it7q-staff     # _headers  index.html
```

7c. *Workers & Pages* → *Create* → *Pages* → *Upload assets* → project name **`it7q-staff`**
(it must match the Access destinations) → upload the `it7q-staff` folder → *Deploy site*.
Then *Custom domains* → `staff.it7q.com.au` → *Activate domain*, and wait for **Active**.

**Test**:
```
curl -sI https://staff.it7q.com.au/ | grep -iE '^(HTTP|location)'       # 302 → it7qqld.cloudflareaccess.com/...
curl -sI https://it7q-staff.pages.dev/ | grep -iE '^(HTTP|location)'    # 302 → it7qqld.cloudflareaccess.com/...
```
Neither may return `200`. Then in a browser, click **Staff** in the site footer, log in with the
one-time PIN, and you should see the placeholder page.

---

## 8. Post-launch checks

Run these once everything above is Active. Send me any output that doesn't match.

**8a. Headers and the webhook base** (any computer):
```
curl -sI https://it7q.com.au/ | grep -iE '^(content-security-policy|strict-transport-security|x-content-type-options|referrer-policy|permissions-policy|cross-origin-opener-policy)'
f=$(curl -s https://it7q.com.au/access/ | grep -oE 'config[.][0-9a-f]{10}[.]js'); curl -s "https://it7q.com.au/assets/js/$f"
```
All six headers present. The CSP's `connect-src` names `https://forms.it7q.com.au`. CSS and JS
files carry a content hash in their names (e.g. `config.0201723bc0.js`), so the second line finds
the current one from the page first. `config.js` shows `"hooks": "https://forms.it7q.com.au/webhook"`, `"mock": false` and your site key.

**8b. Live is exactly what passed the checks** (as `chris` on Pantheon, no sudo):
```
cd /home/chris/it7q-release && for f in assets/js/*.js assets/css/*.css; do
  a=$(curl -s "https://it7q.com.au/$f" | sha256sum | cut -c1-16); b=$(sha256sum "$f" | cut -c1-16)
  [ "$a" = "$b" ] && echo "same      $f" || echo "DIFFERENT $f"
done; cd
```
All seven CSS and JS files say `same`. (Pages aren't compared: Web Analytics can add its script to the live HTML.)

**8c. Pages and the 404:**
```
for p in / /about/ /contact/ /access/ /legal/nda/ /legal/privacy/ /legal/terms/ /portfolio/ /resources/ /no-such-page/; do
  curl -s -o /dev/null -w "%{http_code} $p\n" "https://it7q.com.au$p"
done
```
`200` for each, `404` for the last.

**8d. Nothing internal leaked:**
```
{ curl -s https://it7q.com.au/ https://it7q.com.au/access/
  for f in $(curl -s https://it7q.com.au/access/ | grep -oE '/assets/js/[a-z]+[.][0-9a-f]{10}[.]js'); do curl -s "https://it7q.com.au$f"; done
} | grep -ciE 'nubius|n8n|pantheon'
```
Must print `0`. (`check.py` already blocks these at build time; this proves the live copy matches.)

**8e. The back end still refuses fakes** [claude]: the production contract test, now with both
site origins:
```
sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/contract.py https://forms.it7q.com.au/webhook --origin https://it7q.com.au --prod
sudo -u claude /srv/work/it7q-website/.venv/bin/python /srv/work/it7q-website/tools/contract.py https://forms.it7q.com.au/webhook --origin https://www.it7q.com.au --prod
```
Both end in `PASSED`.

**8f. The real thing, in a browser** (PLAN.md §6.2), on `https://it7q.com.au`, using a test address:
1. *Contact*: send an enquiry. It arrives at `chris@` from `noreply@`, and Reply goes to the test address.
2. *Access*: request NDA access. The test address gets its NDA copy, and you get the review email.
3. Log in while it's still pending: generic refusal.
4. Approve it with the review link (Access login), with some divisions but not Investors. Log in on
   the site: those divisions open, the others and `/investors/` stay locked.
5. Revoke it from the review list: the next click on the site locks.
6. On your phone too: the Turnstile box appears and the forms work over mobile data.

**8g. Over the next day:** Cloudflare → *Turnstile* → `IT7Q website` shows solves from
`it7q.com.au`, *Web Analytics* shows visits, and `dmarc@` (forwarded to you) starts getting
reports with `noreply@` mail passing.

**8h. After every release (standing step)**, once the new deployment is live:

1. **Cache** (as `chris` on Pantheon, no sudo). Confirm the live pages point at this release's
   hashed CSS and JS, and the cache headers are right:
   ```
   a=$(curl -s https://it7q.com.au/access/ | grep -oE '[a-z]+[.][0-9a-f]{10}[.](css|js)' | sort | tr '\n' ' ')
   b=$(grep -oE '[a-z]+[.][0-9a-f]{10}[.](css|js)' /home/chris/it7q-release/access/index.html | sort | tr '\n' ' ')
   [ "$a" = "$b" ] && echo "live matches the release" || echo "STALE"
   curl -sI https://it7q.com.au/ | grep -i '^cache-control'
   curl -sI "https://it7q.com.au/assets/js/$(echo "$b" | grep -oE 'site[.][0-9a-f]{10}[.]js')" | grep -i '^cache-control'
   ```
   Expect `live matches the release`, then `max-age=0, must-revalidate` for the page (Pages'
   default for HTML), then `max-age=31536000, immutable` for the script. If it says `STALE`:
   Cloudflare → `it7q.com.au` → *Caching* → *Configuration* → **Purge Everything**, wait a
   minute and run it again. A changed CSS or JS file always gets a new name, so a stale page is
   the only thing a purge can fix; the old hashed files are harmless.
2. **Real browser** on `https://it7q.com.au` (not `pages.dev`), with a test address:
   - *Contact*: send an enquiry. It arrives at `chris@` from `noreply@`.
   - *Access*: request NDA access. The test address gets its NDA copy, and you get the review email.
   - Log in with the test address: a generic refusal while it's pending (or the approved
     divisions open, if you approve it first). Revoke or reject the test request afterwards.

   Check both emails actually arrived (not in spam). If any step fails, roll back
   (*Undo* below) and send me what you saw.

---

## Releasing changes later

1. I make the change, the tests pass, and I push. Then step 2 (build) and step 3 (copy).
2. Project `it7q-website` → *Deployments* → *Create deployment* → **Production** → upload the
   `it7q-release` folder → *Save and deploy*.
3. 8a–8d again, then **8h** (cache check and the real-browser enquiry, NDA request and login).

## Undo

- **Bad release**: *Deployments* → the previous good one → *⋯* → **Rollback to this deployment**.
  It's instant.
- **Take the site off the domain**: *Custom domains* → remove `it7q.com.au` and `www`, then put back
  the old DNS records you noted in step 5.1. Delete the step 6 redirect rule.
- **Staff**: remove the custom domain from `it7q-staff`. Leave the Access app in place; it does no harm.
- The NDA back end is separate: DEPLOY.md's Undo.
- `sudo rm -r /home/chris/it7q-release /home/chris/it7q-staff` [chris · sudo] whenever you like;
  they're copies.

## If something goes wrong

| Symptom | Likely cause |
|---|---|
| `check.py --launch` fails on `turnstile_site_key` | Step 1 not done yet, or the key isn't the `0x...` site key |
| `check.py --launch` fails on "legal draft", "Last updated" or "How access works" | A legal page lost its date or box, or a draft note was added back; tell me |
| No CSP or HSTS header live | `_headers` wasn't in the upload: drag the folder, not its contents, and check `ls -a` in step 3 |
| Forms say they can't send, on `it7q.com.au` | Turnstile widget hostnames (DEPLOY.md step 4), the real secret (step 10), or the workflows unpublished. Run 8e |
| Forms fail only on `www` | The step 6 redirect isn't on, so `www` serves the site directly; it still should work (both origins are allowed). Run 8e with the `www` origin |
| Custom domain stuck on "Verifying" | An old `A`/`AAAA`/`CNAME` record on that name; delete it (after noting it) |
| `staff.it7q.com.au` shows the page without a login | The Access app's destinations don't include that host: fix 7a before anything else |
