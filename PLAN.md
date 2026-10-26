# IT7Q website rebuild — plan

Status: **plan only, nothing built yet.** v4, 26 Oct 2026. It folds in Chris's answers to Q1, Q2, Q12, Q13, Q16, Q23 and Q25, the domain/nameserver facts, portfolio consent, and the August build pack.
Target: `it7q.com.au`, pure HTML/CSS/JS, no frameworks, Australian English.

---

## 0. Bottom line

- **Multi-page static site** on **Cloudflare Pages (free plan)**. It uses the locked brand from the August build pack. Copy and layout ideas come from v2. The structure, forms and NDA gate are rebuilt.
- **Every project in every division gets a public card**: image + brief description + "why it's unique". Full detail sits behind the NDA wall. The inventory has about 50 projects so far (§2.1).
- **Gated detail never ships in the static site.** It lives server-side (Postgres, read by n8n) and only reaches the browser after an approved login. Any failure keeps the page locked.
- **No secrets in the site.** Protection comes from server-side checks in n8n, Turnstile, rate limits and a Cloudflare-injected edge header.
- **Four NDA webhooks** (approved): `nda-submission`, `nda-login`, `nda-content`, `nda-review`.
- **Gated detail is written at feature level only.** Even behind the NDA there are no internal ports, hostnames, IPs, repo URLs, WireGuard or infrastructure details (Q23).
- **Portfolio** = every site IT7Q has built, each on its own `pN.it7q.com.au` link. Consent covers all of them; p1–p7 are known (§2.2).
- **Private material stays out of this repo.** The build pack, business plan and the two transcripts with financials all live in `/srv/work/it7q-private` and are git-ignored. I work from them there and never copy them in. No financial figures appear anywhere in this repo.
- Server-side pieces (n8n workflows, SQL, Cloudflare steps, DNS list) are **files for Chris to review and deploy**. I don't touch n8n, Docker, Cloudflare or DNS.

---

## 1. Source material

| Source | Where | Role | Notes |
|---|---|---|---|
| `it7q-website-build-pack.md` (Aug 2026) | `/srv/work/it7q-private/` **only** (never committed) | **Primary**: brand (locked), NDA-wall pattern, full division/project map, portfolio p1–p4 | Newest source and the one that wins conflicts. Its "Detail (NDA)" blocks are rewritten at feature level for `gated/`, with infrastructure detail dropped (Q23, §4.9). It assumed deploying on Pantheon, which Q2 replaces. |
| `IT7Q_Complete_Business_Plan.docx` | `/srv/work/it7q-private/` **only** | **Secondary**: project discovery (TEMPESTAS tiers, whose shield names are now retired per Q25; PORTUS features, FABRICUS/DOMUS/MENTIS service lines) | Older: still has NEXUS, no OPUS. **Read in place; never copied, quoted for figures or committed.** |
| `_source/v2/` + zip (May 2026) | repo | Look, copy, layout; v2 product list (extra project names) | NDA and forms are mock only, and the NDA fails open (unlocks on tick). |
| Jan 2026 spec transcript | `/srv/work/it7q-private/` | Multi-page structure, policy page drafts | Moved out of the repo because it holds company financials. |
| Feb 2026 redesign transcript | `/srv/work/it7q-private/` | Feature list (blog, enquiries, Neo showcase, downloads, portals), home users first, Feb-era OPUS products | Moved out of the repo because it holds investor projections. Its WordPress pivot is superseded. |

**Brand (locked by the build pack, replaces v2's tokens)**
- Colours: navy `#0a1628`, cyan `#00b4cc`, lime `#7ec820`, purple `#8b5cf6`, orange `#f97316`
- Logo: four interlocking circles
- Fonts: Rajdhani (headings), Exo 2 (body)
- Tagline: *Smart Tech. Simple Terms. Serious Security.*
- Mission: *To make enterprise-grade technology accessible, affordable and understandable for homes, community organisations and small businesses across Queensland.*

Division accent colours from v2 stay as secondary accents, checked for WCAG AA contrast.

---

## 1a. Decisions so far

| Q | Decision |
|---|---|
| 1 | Yes to `nda-content` and `nda-review`. |
| 2 | Cloudflare Pages, free plan. Registrar is HostPapa; nameservers are already on Cloudflare (`morgan` / `megan.ns.cloudflare.com`), so Pages can serve the bare `it7q.com.au`. §6.1 lists what's needed; I plan no DNS changes. |
| 5 | Settled by the build pack: login + password emailed on manual approval. |
| 12 | Every IT7Q-built site gets a thumbnail + `pN.it7q.com.au` link. Consent covers **all** IT7Q-built sites. p1–p7 known (§2.2). |
| 25 | TEMPESTAS tiers (April 2026 line): **T1 Scout, T2 Sentinel, T3 Guard (hero), T4 Fortress, T5 Citadel**. T1–T4 on CM5, T5 on x86. Shield names (SCUTUM/PARMA/CLIPEUS/THUREOS/ASPIS) and the Jan-spec Buckler…Aegis names are retired. **SCUTUM** now means the MSP antivirus product only. Public tier cards: tier name, one-liner, who it's for. Prices and hardware specs are gated. |
| 23 | All gated "Detail (NDA)" text is rewritten at feature level: no internal ports, hostnames, IPs, repo URLs, WireGuard or infrastructure details. The build pack moves to `/srv/work/it7q-private` and is not committed. |
| 13 / 16 | Content source is the build pack (primary) + business plan (secondary, private). OPUS = software products, per the build pack. Every project gets a card; full info is gated. |
| 14 | Settled by the build pack: public card = image + one-line description + "why it's unique". No ports, source, schematics or security architecture. |
| Fonts/colours | Build pack brand replaces v2's (DM Sans → Exo 2, new palette). |

---

## 2. Site map and pages

Home users first, small business second, all in plain English.

```
/                         Home
/about/                   About + mission
/divisions/               All seven divisions (teaser cards → division pages)
/divisions/msp/           ┐
/divisions/opus/          │  Each page: division intro (public)
/divisions/mentis/        │  + grid of project cards (public: image, one-liner, why unique)
/divisions/tempestas/     │  + per-card "Full details" locked panel.
/divisions/portus/        │  Gated detail loads per project after an approved
/divisions/fabricus/      │  login (see §4).
/divisions/domus/         ┘
/portfolio/               Client websites, p1–p7 (every IT7Q-built site)
/services/                "How we can help": plain-English services + enquiry form (pick service & division)
/contact/                 Contact details, WhatsApp/Messenger, short form
/access/                  NDA: read, request access, log in, log out
/investors/               Investor & partner area: shell page, all content gated
/blog/  /blog/<slug>/     Blog/social hub (static posts, links out to socials/YouTube)
/downloads/               Recommended downloads
/legal/privacy/  /legal/cookies/  /legal/terms/  /legal/nda/
/404.html
```

**Page notes**
- **Home**: hero with the animated four-circle logo and a row of the seven division logos. Then the mission, a "how we help" strip (home → small business), a portfolio highlight, an investor/partner call to action to `/access/`, and contact.
- **Division pages**: one template. The cards are generated by `tools/build.py` from a public data file (`src/data/projects.json`: names, one-liners, why-unique, status, image id). Gated detail is **not** in that file. Each card has a status badge: *Developed · In development · In design · Documented*.
- **Services**: generic public services for home users. MSP specifics stay gated (Q15). The enquiry form has service and division selectors.
- **Portfolio**: §2.2.
- **Parked**: client portal dashboard, admin portal login, Neo evaluation workflow, WordPress (§9).

### 2.1 Project inventory (public card list)

Names and statuses come from the build pack unless marked otherwise. "Status" is my reading of the sources, and Chris confirms it before build. Items marked **?** need a placement or keep/drop decision (Q24). Each card gets an image ID `P-<div>-<nn>` (see §5).

**MSP — Managed Services**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MSP-01 | SCUTUM — managed antivirus/EDR (the name is now MSP-only, Q25) | In development | build pack |
| P-MSP-02 | MSP Companion App (one-click enrolment) | In development (pilot) | build pack |
| P-MSP-03 | Managed security monitoring (Wazuh SIEM) | Developed | build pack |
| P-MSP-04 | IT7Q Support Portal | In development | build pack, v2 |
| P-MSP-05 ? | IT7Q SysMon (server health monitoring) | ? | v2 only |

**OPUS — Software Products**
| ID | Project | Status | Source |
|---|---|---|---|
| P-OPUS-01 | Athena Browser | Developed | build pack, v2 |
| P-OPUS-02 | Hermes Mail | In development | build pack, v2 |
| P-OPUS-03 | Calendis (consumer calendar) / Calendi IT7Q (project scheduler) | In development | build pack, v2 |
| P-OPUS-04 | LexiScan (dyslexia/visual-stress screener) | In development | build pack |
| P-OPUS-05 | Nexus (secure messaging) | In development | build pack, v2 |
| P-OPUS-06 | Andromeda OS | In development | build pack |
| P-OPUS-07 | Paideia OS (safe computer for kids) | Developed | build pack |
| P-OPUS-08 | JANUS (one inbox for every channel) | In design | build pack, v2 |
| P-OPUS-09 | Project Silo (private Workspace alternative) | In design | build pack, v2 |
| P-OPUS-10 ? | Andromeda CE / Andromeda AI companion | ? | v2, Feb notes |
| P-OPUS-11 ? | Aegir — SecureStart (Windows privacy/setup tool) | ? | v2 only |
| P-OPUS-12 ? | FABRICUS App (offline order/catalogue PWA) | ? (OPUS or FABRICUS) | Feb notes |

**MENTIS — AI & Automation**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MEN-01 | Project Persephone (AI agent workforce) | Developed (partly live) | build pack, v2 |
| P-MEN-02 | MNEMOSYNE (AI memory layer) | In development | build pack |
| P-MEN-03 | Neo (AI website builder) | In development | build pack |
| P-MEN-04 ? | FORTUNA (investment-monitoring agent). Separate card, or inside Persephone? | ? | build pack (as agent), v2 (own card) |
| P-MEN-05 ? | COLLOQUIUM (business chat/AI assistant service) | ? | Feb notes |
| P-MEN-06 ? | v2 "AI Automations" set (patch mgmt, social pipeline, invoice/PABX, email triage, security alerting, compliance reporting). Cards, or a public services list? | ? | v2 |

**TEMPESTAS — Cybersecurity Hardware**
| ID | Project | Status | Source |
|---|---|---|---|
| P-TEM-01 | T1 Scout | In development | Chris (Q25), v2 |
| P-TEM-02 | T2 Sentinel | In development | Chris (Q25), v2 |
| P-TEM-03 | T3 Guard (**hero** product: featured card, first on the page and in the home hero row) | In development | Chris (Q25), v2 |
| P-TEM-04 | T4 Fortress | In development | Chris (Q25) |
| P-TEM-05 | T5 Citadel | In development | Chris (Q25) |
| P-TEM-06 | TEMPESTAS T3 carrier board (v2's "Custom PCB Design", assumed the same) | In design | build pack, v2 |

Tier statuses are my assumption; Chris to confirm. **Public tier cards show only the tier name, a one-liner and who it's for** (e.g. "for households", "for small offices"). Prices, hardware specs and the platform split (T1–T4 on CM5, T5 on x86) go in gated detail, kept at feature level per §4.9. The carrier board card stays generic in public ("our own Australian-designed board").

**PORTUS — Community Safety**
| ID | Project | Status | Source |
|---|---|---|---|
| P-POR-01 | PORTUS community safety network (absorbs K.I.T.S.) | In design | build pack, business plan |
| P-POR-02 ? | PORTUS App (separate card from the network?) | ? | v2 |
| P-POR-03 ? | PORTUS Jnr (child-safe version) | ? | v2 only |

**FABRICUS — Woodcraft & Digital Manufacturing**
| ID | Project | Status | Source |
|---|---|---|---|
| P-FAB-001 … P-FAB-019 | Product range F-001 → F-019 (19 cards; names, one-liners and photos needed, Q26) | In development | build pack |
| P-FAB-020 ? | TABULAE medal display boards (likely already within F-range) | ? | Feb notes, build pack |
| P-FAB-021 ? | FORMAE custom 3D prints | ? | Feb notes |
| P-FAB-022 ? | BIONICUS assistive body supports (Project Bionic) | ? | Feb notes |

**DOMUS — Smart Home**
| ID | Project | Status | Source |
|---|---|---|---|
| P-DOM-01 | Smart, segmented, private home setup | Documented / service | build pack, business plan |

Retired, so no card unless Chris says otherwise: original single-tenant Calendi for Pine Rivers RSL, and the NEXUS division (3CX/NBN), which was replaced by OPUS.

### 2.2 Portfolio

Consent is on file for **all** IT7Q-built sites.

| Label | Client | Link | Repo (Chris's GitHub) | Hosted where? |
|---|---|---|---|---|
| p1 | True Colours DSS | `p1.it7q.com.au` | `TCDSS_Website` | Q27 |
| p2 | Red Bird | `p2.it7q.com.au` | — | Q27 |
| p3 | Pine Rivers RSL | `p3.it7q.com.au` | `PRRSL_Website` | Q27 |
| p4 | The Artist Apron | `p4.it7q.com.au` | — | Q27 |
| p5 | Burpengary Jets | `p5.it7q.com.au` | — | Q27 |
| p6 | BlueVibes (display name to confirm, Q29) | `p6.it7q.com.au` | `BlueVibes_Website` | Q27 |
| p7 | AustPathClub (display name to confirm, Q29) | `p7.it7q.com.au` | `AustPathClub` | Q27 |

The cards show the client name, thumbnail and outbound `pN` link. Any future IT7Q-built site takes the next label (p8…). The `published` flag in `portfolio.json` stays, so a card can be held back (e.g. a site that's offline), and `tools/check.py` fails if an unpublished entry appears in `dist/`.

---

## 3. Reuse from v2 vs rebuild

| Area | Decision | Notes |
|---|---|---|
| Colours, fonts | **Replace** with the build-pack brand | Self-host Rajdhani + Exo 2 (woff2), no Google Fonts. |
| Hero copy, tagline | **Reuse** | Same tagline as the build pack. Use the build pack's mission text. Confirm stats (Q18). |
| Division card / portfolio card design, nav, scroll animations | **Reuse, refactor** | `addEventListener` instead of inline `onclick` (strict CSP). Respect `prefers-reduced-motion`. |
| v2 product list | **Mine for names only** | Folded into §2.1. Products tabs removed. Public detail is limited to the one-liner pattern. |
| NDA legal text | **Reuse as draft v1.0** | Needs review (Q10). |
| Cookie banner | **Simplify** | Privacy notice only if there are no tracking cookies (Q20). |
| NDA modal, contact form, `alert()` validation, emoji icons, modal a11y | **Rebuild** | As in v1 of this plan. |
| Jan spec portal dashboard | **Drop** | Advertises internal hostnames. |

**Repo layout**
```
src/                 page sources + partials
  data/projects.json public card data only (no gated detail)
  data/portfolio.json
  assets/css|js|fonts|img|video
tools/build.py       stdlib-only Python: partials + data → dist/ (Q21)
tools/check.py       links, HTML sanity, gated-content leak check, infrastructure-detail guard on gated/, unpublished-portfolio check, financial-figure guard
dist/                build output, the only thing deployed (git-ignored)
gated/               feature-level gated detail per project as JSON, NEVER in dist/ (§4.9)
n8n/workflows/       nda-submission, nda-login, nda-content, nda-review, website-enquiry
n8n/sql/             001_schema.sql, 002_seed_gated.sql (generated)
deploy/              Cloudflare Pages, DNS record list, n8n import, Postgres, env vars
docs/IMAGES.md       image checklist (mirrors §5)
```

`tools/check.py` also refuses to build if any `$`-amount next to revenue/projection-style words appears in `src/` or `gated/`. It's a cheap guard against investor figures creeping back in. A second guard (§4.9) does the same for infrastructure detail in `gated/`.

---

## 4. NDA flow design

Unchanged in principle from v1 of the plan. The changes: content is now **per project** rather than per division, and the build pack confirms the UX order (T&C tick → NDA modal + tick → email → emailed NDA copy → manual approval → emailed login + password → unlock).

### 4.1 Principles
1. **Fail closed.** Locked is the default markup. Detail renders only on a 200 + valid JSON from `nda-content`. Everything else stays locked.
2. **Signing grants nothing.** `nda-submission` only creates `pending`. Only `nda-review` approval enables login.
3. **No gated content in public files**: not hidden, simply absent.
4. **No secrets in the site.** Only the public Turnstile site key appears in it.
5. **The server re-checks everything on every request.** Revocation takes effect on the next call.
6. **No enumeration.** The same reply goes out for new, duplicate, rejected and unknown emails.

### 4.2 Protection layers (all public webhooks)
| Layer | What |
|---|---|
| Cloudflare edge header | A Transform Rule sets `X-IT7Q-Edge` on `hooks.nubius.com.au/webhook/*`, and n8n Header Auth checks it. This keeps the "header auth" rule with nothing secret in the site. |
| CORS | Allowed origin `https://it7q.com.au` (+ the Pages preview origin while testing). |
| Turnstile | Widget on forms. n8n verifies server-side (secret in an n8n credential) and checks hostname + action. Honeypot + min fill time as backup. |
| Rate limits | Cloudflare WAF rule where the free plan allows, plus Postgres-backed per-IP/per-email counters in n8n. Login lockout: 5 fails/15 min. |
| Validation | JSON only, ≤ 8 KB, strict allow-list, NDA version/hash must match. |
| Least-privilege DB | Separate `it7q_web` database/role. |
| No caching | Cloudflare bypass on `/webhook/*`; `Cache-Control: no-store`. |
| Audit | Every event logged in `nda_audit`. |

### 4.3 `nda-submission`
1. The visitor reads NDA v1.0 (the page embeds its SHA-256). They give name, email, org, reason, divisions of interest, typed signature, NDA tick, T&C tick and Turnstile, with a hidden honeypot + timestamp.
2. POST to `https://hooks.nubius.com.au/webhook/nda-submission`. Nothing unlocks.
3. n8n checks: edge header → size/schema → honeypot/timing → Turnstile → rate limits.
4. Upsert into `nda_requests` with status `pending`, server timestamp, IP, UA and NDA version/hash. No duplicate if one is already pending or approved.
5. Email the signer a copy of the agreed NDA + acceptance record ("reviewed manually").
6. Email **chris@it7q.com.au** a copy of the signed NDA + an approval alert with a Review link.
7. Reply `202` with a neutral message.

### 4.4 `nda-review`
- One-time token link (SHA-256 stored, 7-day expiry, single use). GET shows a confirm page; **only POST changes state**, so mail-scanner prefetch can't approve anyone.
- Recommended: Cloudflare Access on `/webhook/nda-review*` for Chris's email only (Q4).
- **Approve**: status `approved`, scope (Q6), `expires_at` = signed + NDA term. It generates a ≥ 16-char password, stores an scrypt hash only, and emails the login + `/access/` link.
- **Reject / revoke / reset**: the same workflow. Revoke kills sessions immediately.

### 4.5 `nda-login`
1. Email + password + Turnstile, POSTed via Cloudflare.
2. Edge header, Turnstile, lockout. Dummy scrypt for unknown emails. `timingSafeEqual`. Requires approved, not revoked, NDA not expired.
3. Session token = 32 random bytes. Only its SHA-256 is stored. 8 h absolute / 1 h idle (Q7).
4. One generic 401 for every failure.
5. The token lives in `sessionStorage` only.

### 4.6 `nda-content`
1. A division page loads public cards with locked panels.
2. With a token, one POST `{division}` returns the gated detail for **all granted projects in that division** (structured JSON, `no-store`). This avoids one call per card.
3. n8n re-checks the session, approval, revocation, NDA expiry and division scope.
4. Rendering uses DOM APIs only (no `innerHTML`), with a watermark: "Confidential — shared with <email> under NDA".
5. 401/403 → clear the token and re-lock. Network/5xx → stay locked, "try again". No cached fallback.
6. `{action:"logout"}` deletes the session server-side.

Honest limits: an approved viewer can still copy or screenshot. The NDA, watermark, audit log and revocation are the controls for that.

### 4.7 Data model (sketch)
```
nda_requests       id, email, name, org, reason, divisions[], nda_version, nda_sha256,
                   signature_text, signed_at, signed_ip, signed_ua, status, approved_at,
                   approved_divisions[], expires_at, password_hash, revoked_at, created_at
nda_review_tokens  token_sha256, request_id, expires_at, used_at
nda_sessions       token_sha256, request_id, created_at, last_seen_at, expires_at, ip, ua
nda_content        division, project_id, version, body jsonb, updated_at   -- seeded from gated/
nda_rate           key, window_start, count
nda_audit          id, at, event, request_id, ip, ua, detail jsonb
```

### 4.8 Chris's server-side setup (documented in `deploy/`, not done by me)
- n8n credentials, referenced by name only: `IT7Q Edge Header`, `Turnstile secret`, `Postgres it7q_web`, `Mail sender`. The build pack names **MXRoute** for mail; the from-address is still open (Q8).
- n8n env var `NODE_FUNCTION_ALLOW_BUILTIN=crypto` (compose change under `/opt/it7q`).
- Postgres `it7q_web` DB + role, then run the SQL.
- Cloudflare: Transform Rule, cache bypass, rate-limit rule, Turnstile widget, optional Access on `nda-review`.

### 4.9 Gated content rules (Q23)
Gated detail tells an approved reader **what** a project does, how it helps, where it's at and what's next. It never says **how it's wired up**.

| Allowed behind the NDA | Never, even behind the NDA |
|---|---|
| Features and capabilities in plain English | Ports, internal or external hostnames, IP addresses |
| Who it's for, the problem it solves, why it's different | Repo URLs, git hosts, package/apt repos |
| Status, milestones, roadmap in general terms | WireGuard, tunnels, VPN layout, network topology |
| General tech family where it helps understanding (e.g. "self-hosted", "runs on a Raspberry Pi compute module", "uses AI models") | Service/agent internals, enrolment mechanisms, auth tokens, retention/config values |
| Integrations by product name (e.g. "works with Athena and Nexus") | Exact software versions or security-tool placement that maps the attack surface |
| Pricing (TEMPESTAS tiers: gated, per Q25; others per Q28) | Anything from the business plan's financials |

Process: I write each project's gated text from the private build pack into `gated/<division>.json` with those rules applied, and Chris reviews it before it's seeded into Postgres. `tools/check.py` scans `gated/` and fails on:
- IPv4/IPv6 addresses
- `:<port>` patterns
- hostnames (`*.nubius.com.au`, `*.it7q.com.au` other than public `pN`/`www`/`downloads`)
- `git.`/`.git` URLs
- words like `WireGuard`, `wg0`, `tunnel`, `port`

---

## 5. Image and media list

Every image starts as a visible placeholder (`PLACEHOLDER <ID> — description (w×h)` + matching `alt`). **Public images must not reveal gated detail**: no schematics, board close-ups, admin screens or architecture diagrams.

**Site-wide**
| ID | Asset | Where | Size / format |
|---|---|---|---|
| IMG-01 | Animated four-circle logo (Elementals animation) | Home hero | webm + mp4 + poster |
| IMG-02 | Static logo | Header, footer | SVG |
| IMG-03 | Favicon set | All | SVG, 32 px, 180 px |
| IMG-04 | Open Graph share image | All | 1200×630 |
| IMG-05–11 | Division logos ×7 | Hero row, division pages | SVG |
| IMG-12–18 | Division header thumbnails ×7 | Divisions index, division pages | 1200×750 |
| IMG-29 | Photo of Chris | About | 800×800 |
| IMG-30 | Workshop/workspace photo (no gated detail visible) | About, Services | 1600×900 |
| IMG-31 | Helping a home user | Home, Services | 1600×900 |
| IMG-32 | Helping a small business | Services | 1600×900 |
| IMG-33 | Blog covers (one per post) | Blog | 1200×630 |
| IMG-34 | Tutorial video thumbnails | Blog | 1280×720 |

**Portfolio**
| ID | Asset | Size |
|---|---|---|
| IMG-19 | p1 True Colours DSS screenshot | 1600×1000 + mobile 750×1334 |
| IMG-20 | p2 Red Bird screenshot | as above |
| IMG-21 | p3 Pine Rivers RSL screenshot | as above |
| IMG-22 | p4 The Artist Apron screenshot | as above |
| IMG-23 | p5 Burpengary Jets screenshot | as above |
| IMG-35 | p6 BlueVibes screenshot | as above |
| IMG-36 | p7 AustPathClub screenshot | as above |
| IMG-24–28, IMG-37–38 | Client logos p1–p7 (if consent covers logos) | SVG/PNG |
| (later) | Screenshots for any future IT7Q-built sites (p8…) | as above |

**Project cards** (one public-safe image each, 800×500 WebP; render, photo, product shot or illustrative graphic)
| IDs | Count | Notes |
|---|---|---|
| P-MSP-01…05 | 4–5 | UI mock-ups or illustrative graphics, not real admin screens |
| P-OPUS-01…12 | 9–12 | App screenshots with dummy data |
| P-MEN-01…06 | 3–6 | Illustrative (agent "team" graphic etc.) |
| P-TEM-01…06 | 6 | One per tier (T3 Guard gets a larger hero image, 1600×1000) + carrier board. Enclosure/product photos OK; **no PCB/schematic close-ups or spec labels** |
| P-POR-01…03 | 1–3 | Concept art/signage, no real locations of people's homes |
| P-FAB-001…022 | 19–22 | Product photos of F-001–F-019 (+ TABULAE/FORMAE/BIONICUS if kept) |
| P-DOM-01 | 1 | Generic smart-home photo |

That's roughly **43–55 project images**, depending on Q24.

**Gated** (served only via `nda-content`, never in `dist/`): G-<project-id> detail images where useful, ≤ 300 KB each, as data URIs. Investor presentation assets: G-INV-xx.

---

## 6. Deployment approach

**Cloudflare Pages, free plan** (decided).
- Private repo → Pages builds with `python3 tools/build.py` → publishes `dist/` only. `gated/`, `n8n/`, `deploy/` and `_source/` never publish.
- `_headers`: strict CSP (`default-src 'self'`; scripts from self + `challenges.cloudflare.com`; `connect-src` self + `https://hooks.nubius.com.au`; `img-src 'self' data:`; `frame-ancestors 'none'`), HSTS, `nosniff`, `Referrer-Policy` and `Permissions-Policy`.
- Preview deploys on `<project>.pages.dev` for testing.
- Free-plan limits worth knowing: 500 builds/month and a 20,000-file limit. Neither is an issue at this size.
- Release flow: branch → PR → Chris reviews → merge to `main` → Pages deploys.

### 6.1 DNS: records needed (listed only; Chris decides and makes the changes)

Registrar: HostPapa. Nameservers: **already on Cloudflare** (`morgan.ns.cloudflare.com`, `megan.ns.cloudflare.com`), so the zone is managed in Cloudflare and Pages can serve the bare `it7q.com.au` directly. No nameserver change is needed.

Adding a custom domain in Pages → Custom domains creates the matching record in the zone for you. Chris does that step at go-live, after checking nothing already sits on those names.

| Record | Purpose | Points to | Notes |
|---|---|---|---|
| `it7q.com.au` (apex) | Main site | Pages project (`<project>.pages.dev`) | CNAME at the apex (Cloudflare flattens it). Replaces whatever the apex points at today, so check that first |
| `www.it7q.com.au` | Main site | CNAME `<project>.pages.dev` | Redirect www → apex via a Cloudflare redirect rule (or the reverse; Chris's pick) |
| `p1`–`p7.it7q.com.au` | Portfolio sites | Wherever each site is hosted | Hosting target for each still unknown (Q27). Old `tc/rb/pr/aa` names: keep, redirect to `pN`, or retire? |
| `downloads.it7q.com.au` | Existing (build pack) | unchanged | Confirm it stays |
| MX / SPF / DKIM / DMARC for the n8n sender | NDA emails deliverable | Mail provider (MXRoute per build pack) | Check SPF/DKIM cover the sending domain once Q8 is answered |
| `hooks.nubius.com.au` | Webhooks | Existing cloudflared tunnel | Different domain (`nubius.com.au`); no change |

Turnstile needs no DNS, just the widget's allowed hostnames (`it7q.com.au`, `www`, the preview origin).

### 6.2 Verification before go-live (fail-closed tests)
1. Submit the NDA → still locked; signer copy + Chris's alert both arrive.
2. Log in while pending → generic refusal.
3. Approve → login works, gated detail loads for granted divisions only.
4. Revoke → the next request locks.
5. Tampered or expired token → locked.
6. n8n down → locked, with a friendly error.
7. No Turnstile / not via Cloudflare → rejected.
8. Rate limits trigger and recover.
9. `tools/check.py`: no gated canary/text, no unpublished portfolio entry and no financial figures in `dist/`; no infrastructure detail in `gated/`. View-source spot checks.
10. Accessibility (axe/Lighthouse), links, mobile.

---

## 7. Build phases (one step at a time)

0. ✅ Repo, source, plan v1. ✅ Financials removed from repo + history (GitHub cache purge pending, §10). ✅ Plan v2.
1. Scaffold `src/`, build/check tools, brand tokens, base CSS, header/footer, placeholder component, Home.
2. Public pages: About, Divisions index + 7 division pages with project cards from `projects.json`, Portfolio, Services, Contact, Legal.
3. NDA front end (`/access/`, locked panels, renderer) against a local mock with failure simulation.
4. Gated content: feature-level `gated/` JSON (§4.9, Chris reviews), n8n workflows, SQL, `deploy/` docs for Chris to review.
5. Blog, Downloads, Investors shell.
6. QA (§6.2), preview deploy, Chris walk-through, DNS (Chris), go live.

---

## 8. Open questions for Chris

**Answered**: 1, 2, 12, 13, 16, 23, 25 (Chris); 5, 14 (settled by build pack). See §1a. Q27 is narrowed to hosting only.

**Still open from v1**
3. **Bot protection**: Cloudflare Turnstile OK, or in-house only?
4. **Approvals**: emailed review link behind Cloudflare Access (recommended), or in n8n over WireGuard only?
6. **Approval scope**: all seven divisions + investors, or picked per person?
7. **Sessions**: 8 h / 1 h idle, tab-only OK?
8. **Mail**: MXRoute per the build pack. Which from-address (e.g. `noreply@it7q.com.au`)?
9. **Signer's copy**: HTML email + HTML record, or PDF (needs a renderer container)?
10. **NDA text**: "Mutual" but one-way and investor-scoped. Review/reword? Term 3 years, with access ending when it lapses?
11. **Retention** of NDA records, IPs and audit logs?
15. **MSP + home users**: generic public Services page, with MSP specifics gated, OK?
17. **Launch scope**: blog + downloads in, portal logins parked?
18. **Facts**: hero stats, phone, `enquiries@` vs `info@`, and publishing the ABN + suburb.
19. **Enquiry form**: `website-enquiry` webhook with the same protections? Where should enquiries go?
20. **Analytics**: none, or cookieless Cloudflare Web Analytics?
21. **Build step**: stdlib-only Python build script OK?
22. **Logo files**: Elementals MP4 + division SVGs still around?

**New**
24. **Placement / keep-or-drop** for the **?** items in §2.1: IT7Q SysMon, Andromeda CE/companion, Aegir SecureStart, FABRICUS App, FORTUNA, COLLOQUIUM, v2 Automations, PORTUS App, PORTUS Jnr, TABULAE, FORMAE, BIONICUS. Also: do Persephone's named agents get their own cards?
26. **FABRICUS F-001–F-019**: names, one-liners and photos. Launch with placeholders for any not ready?
27. **Portfolio hosting**: where is each p1–p7 site hosted today (vps01, Pantheon, elsewhere)? Each `pN` record needs that target. And what happens to the old `tc/rb/pr/aa.it7q.com.au` names: keep, redirect to `pN`, or retire?
28. **Public prices (non-TEMPESTAS)**: TEMPESTAS prices are now gated (Q25). The build pack's SCUTUM teaser includes a "from" price. Show that one publicly, or gate all prices for consistency?
29. **p6/p7 display names**: how should BlueVibes and AustPathClub appear on their cards (full organisation names)? Is there a short one-liner for each?

---

## 9. Parked (pins)
- Client portal dashboard / SSO (Jan spec): needs its own auth design and shouldn't advertise internal hostnames.
- Admin portal login: better as a bookmark behind Cloudflare Access.
- Neo website-evaluation workflow.
- WordPress version: superseded.

---

## 10. Repo housekeeping log
- **26 Oct 2026: investor financials removed.**
  - The Jan spec and Feb redesign transcripts were moved to `/srv/work/it7q-private` and git-ignored.
  - History was rewritten (authorised one-off) and force-pushed. `main` now has no commit containing them.
  - A backup bundle of the old history is in `/srv/work/it7q-private` (contains financials; delete once you're happy).
  - The August build pack was moved to `/srv/work/it7q-private` and git-ignored. It was never committed, so no history change was needed.
  - **Pending (Chris):** GitHub still serves the old, now-unreferenced commit `b39954a` (and its parent) if fetched by exact SHA. Purging that needs a GitHub Support request (sensitive data removal: ask them to garbage-collect the repo and drop cached views). The alternative is deleting and recreating the repo, which needs the deploy key re-added.
