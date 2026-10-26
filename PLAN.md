# IT7Q website rebuild — plan

Status: **plan only, nothing built yet.** v6, 27 Oct 2026. It adds the `_brand/` colour check (§1b, which found a conflict for Chris to decide: Q37), the FABRICUS register F-001–F-035, the Q32 answer and the completed GitHub purge.
Target: `it7q.com.au`, pure HTML/CSS/JS, no frameworks, Australian English.

---

## 0. Bottom line

- **Multi-page static site** on **Cloudflare Pages (free plan)**. Brand = the **April 2026 business-card set** (§1). **The `_brand/` packs use a different palette, navy and taglines from the card** (§1b), so which one wins is Chris's call (Q37) before Phase 1. Copy and layout ideas come from v2. The structure, forms and NDA gate are rebuilt.
- **Every project in every division gets a public card**: image + brief description + "why it's unique". Full detail sits behind the NDA wall. The inventory is **69 cards** (§2.1), 38 of them FABRICUS.
- **Gated detail never ships in the static site.** It lives server-side (Postgres, read by n8n) and only reaches the browser after an approved login. Any failure keeps the page locked.
- **No secrets in the site.** Protection comes from server-side checks in n8n, Turnstile, rate limits and a Cloudflare-injected edge header.
- **Five webhooks**: four NDA (`nda-submission`, `nda-login`, `nda-content`, `nda-review`) + `website-enquiry` (Q19). All have the same protections. Review links sit behind Cloudflare Access.
- **Mail goes out from a dedicated `noreply@it7q.com.au` MXRoute mailbox.** n8n never holds Chris's own credentials (Q8).
- **Gated detail is written at feature level only.** Even behind the NDA there are no internal ports, hostnames, IPs, repo URLs, WireGuard or infrastructure details (Q23).
- **Portfolio** = every IT7Q-built site, each a **static snapshot on its own Cloudflare Pages project** at `pN.it7q.com.au`. Old `tc/rb/pr/aa` names redirect (§6.3). No DNS changes yet.
- **Private material stays out of this repo.** The build pack, business plan and the two transcripts with financials all live in `/srv/work/it7q-private` and are git-ignored. No financial figures appear anywhere in this repo. The only public price is SCUTUM's "from" price (Q28).
- Server-side pieces (n8n workflows, SQL, Cloudflare steps, DNS list) are **files for Chris to review and deploy**. I don't touch n8n, Docker, Cloudflare or DNS.

---

## 1. Source material

| Source | Where | Role | Notes |
|---|---|---|---|
| **Business card (Apr 2026)** | Chris (values in this plan) | **Brand**: colours, tagline, badge names | Wins over the build pack on brand. Conflicts with the `_brand/` packs (§1b, Q37). |
| **`_brand/` packs (Oct 2026)** | `_brand/` (IT7Q master + six division zips; **no separate MSP pack**, the master covers "Group & Managed Services"), git-ignored | **Logo artwork**: SVG logo + emblem ×5 variants, PNGs, favicons, 3D plaques per pack | Extracted 27 Oct into scratch folders outside the repo; all SVGs pass the safety scan. Same README in all seven. |
| FABRICUS register (Jul 2026 plan-sheet handover) | Chris (names in §2.1) | F-001–F-035 product names | Shop jigs/tools excluded (not retail). |
| `it7q-website-build-pack.md` (Aug 2026) | `/srv/work/it7q-private/` **only** (never committed) | **Primary for content**: NDA-wall pattern, division/project map, portfolio p1–p4 | Its "Detail (NDA)" blocks are rewritten at feature level for `gated/`, with infrastructure detail dropped (§4.9). Its brand block (navy `#0a1628`, title-case tagline) is superseded by the business card. |
| `IT7Q_Complete_Business_Plan.docx` | `/srv/work/it7q-private/` **only** | **Secondary**: project discovery | Older: still has NEXUS, no OPUS. **Read in place; never copied, quoted for figures or committed.** |
| `_source/v2/` + zip (May 2026) | repo | Look, copy, layout; v2 product list | NDA and forms are mock only, and the NDA fails open. v2 has **no per-division colours** (only navy/cyan/amber/green/purple/red tokens). |
| Jan 2026 spec transcript | `/srv/work/it7q-private/` | Multi-page structure, policy page drafts | Holds company financials. |
| Feb 2026 redesign transcript | `/srv/work/it7q-private/` | Feature list, home users first, Feb-era OPUS products | Holds investor projections. Its WordPress pivot is superseded. |

**Brand (April 2026 business card, replaces the build pack's brand block)**
- Master mark: **four interlocking circles**, cyan `#00B4CC`, lime `#7EC820`, purple `#8B5CF6`, orange `#F97316`, on dark navy **`#0D1B2A`** (was `#0a1628` in the build pack).
- Tagline: ***Smart tech. Simple terms. Serious security.*** (sentence case, as on the card).
- Fonts: Rajdhani (headings), Exo 2 (body). Unchanged.
- Mission: *To make enterprise-grade technology accessible, affordable and understandable for homes, community organisations and small businesses across Queensland.*

**Division badges (business-card style): Latin name + translation, each in its own colour**

| Division | Badge translation | Colour (card) | Pack colours (light · mid · deep) | Match? | Page subtitle (descriptive) |
|---|---|---|---|---|---|
| MSP | Managed Services | blue | no MSP pack; master = gold `#EAAE40` · orange `#DF6D2E` · crimson `#BB2949` | ❌ | Managed IT, plain English |
| OPUS | Works & Projects | orange | gold `#F2C14E` · teal `#22A89C` · deep teal `#0E7470` | ❌ | Software products |
| MENTIS | Mind & Intelligence | purple | cyan `#3FC8DB` · pink `#D5479F` · purple `#7A2AC8` | ⚠️ partly | AI & automation |
| TEMPESTAS | Storm & Hardware | cyan | sky `#7FB8EA` · blue `#3A86CF` · deep blue `#1C4F9C` | ❌ blue, not cyan | Cybersecurity hardware |
| PORTUS | Harbour & Gateway | lavender/violet (not teal) | lavender `#C3A6EC` · violet `#8B5CC9` · deep violet `#5E3496` | ✅ | Community safety |
| FABRICUS | Craft & Making | amber | amber `#E8B04A` · copper `#C8662A` · brown `#8A3B12` | ✅ | Woodcraft & digital manufacturing |
| DOMUS | Home & Dwelling | green | light green `#A6D86E` · green `#43A867` · deep green `#22704A` | ✅ | Smart home |

### 1b. Brand colour check (27 Oct, against the extracted packs)

**Bottom line: the packs are a different colour system from the business card.** The emblem shape is the same family: four interlocking circles, one navy plus three accents, inside a navy ring with the name arched on top and a tagline arched below. But the master's colours, the navy, every tagline, and three of the seven division colours don't match the card. Only PORTUS, FABRICUS and DOMUS line up.

**Mismatches**

| # | Item | Business card | `_brand/` packs | Notes |
|---|---|---|---|---|
| 1 | **Master circles** | cyan `#00B4CC`, lime `#7EC820`, purple `#8B5CF6`, orange `#F97316` (four colours) | navy `#0E1326` + gold `#EAAE40`, orange `#DF6D2E`, crimson `#BB2949` | Different palette. None of the card's four colours appears in any pack. |
| 2 | **Navy** | `#0D1B2A` | `#0E1326` (all seven packs) | Close to the eye (both very dark) but not the same hex. The build pack had a third value, `#0a1628`. |
| 3 | **Master tagline** | "Smart tech. Simple terms. Serious security." | "CYBER - TECH SERVICES" arched in the logo | The card line can still sit beside the logo as text. |
| 4 | **Division taglines** | Latin translation (Works & Projects, Storm & Hardware…) | English descriptor (SOFTWARE STUDIO, CYBER SECURITY, COMMUNITY SAFETY, WOODCRAFT & MAKING, SMART HOME, ARTIFICIAL INTELLIGENCE) | The pack README marks OPUS's and FABRICUS's as placeholders. The badge row can put the card translation in HTML under the **emblem** (which has no text) and sidestep this. |
| 5 | **MSP** | blue | no MSP pack; the README says the master pack is "Group & Managed Services" (warm palette) | MSP has no blue artwork anywhere. |
| 6 | **OPUS** | orange | teal + gold | This is the teal in the family, not PORTUS. |
| 7 | **TEMPESTAS** | cyan | blues | Card MSP = blue and TEMPESTAS = cyan; the packs have TEMPESTAS blue. |
| 8 | **MENTIS** | purple | purple deep accent, but with cyan and pink | Purple carries the name and tagline, so it reads purple-ish overall. |
| 9 | PORTUS | lavender/violet | lavender/violet | ✅ |
| 10 | FABRICUS | amber | amber/copper/brown | ✅ |
| 11 | DOMUS | green | greens | ✅ |

**Colour contrast** (as text or thin line on the card navy `#0D1B2A`; AA needs 4.5 for body text, 3.0 for large text and UI):
- Every pack's **light** accent passes easily (8.2–10.5).
- **Mid** accents mostly pass at 4.3–5.9. PORTUS `#8B5CC9` is 3.7, so it's large text only.
- **Deep** accents fail on navy (2.0–3.1). They suit white backgrounds; on dark, the badge row uses the reverse-on-dark artwork.
- Card master colours: 4.1–8.4. Purple `#8B5CF6` is 4.1, large text only.

**Safety scan**: all 70 SVGs are clean (no `<script>`, `on*` handlers, `<foreignObject>`, external or `data:` references, DOCTYPE or entities). Each zip was extracted with path-traversal and symlink checks into its own scratch folder. Nothing has been copied into the repo yet; only SVGs actually used get copied into `src/assets/img/brand/` in Phase 1. The zips stay git-ignored. The 3D plaque files and PNGs aren't needed for the site.

**Ways to settle it (Q37)** — my recommendation is the first:
1. **Packs win for artwork, card wins for words.** Use the pack SVGs as-is and take the site palette from them (navy `#0E1326`, each division's mid accent as its colour). Keep the card's tagline and Latin translations as HTML text under the emblems. MSP uses the master emblem. Fastest, and the logo on the site matches what's printed and 3D-plaqued.
2. **Card wins everywhere.** The packs get recoloured to the card palette (new SVGs from Chris or the designer). An MSP pack and new taglines would be needed. Slower.
3. **Mix**: pack artwork, but recolour only the mismatched divisions (master, MSP, OPUS, TEMPESTAS).

---

## 1a. Decisions so far

| Q | Decision |
|---|---|
| 1 | Yes to `nda-content` and `nda-review`. |
| 2 | Cloudflare Pages, free plan. Registrar HostPapa; nameservers already on Cloudflare (`morgan` / `megan.ns.cloudflare.com`). |
| 3 | **Cloudflare Turnstile**: yes. |
| 4 | **Approvals**: emailed one-time review link, with `/webhook/nda-review*` behind **Cloudflare Access** (Chris's email only). |
| 5 | Login + password emailed on manual approval (build pack). |
| 6 | **Scope**: approval grants **all seven divisions by default**. **Investors** access is granted **per person**, as a separate tick at approval. |
| 7 | **Sessions**: 8 h absolute / 1 h idle, `sessionStorage` (tab-only). |
| 8 | **Mail**: dedicated **`noreply@it7q.com.au`** mailbox on **MXRoute**, used only for sending (Chris creates it). n8n's `Mail sender` credential is that mailbox. **Never chris@ credentials in n8n.** |
| 9 | **Signer's copy**: HTML email + HTML record. **No PDF**, so no renderer container. |
| 10 | **NDA**: **one-way** (IT7Q discloses), **3-year term**, access ends when it lapses. Draft rewording in `docs/nda-draft.md` for Chris's review; Chris gets it checked before launch. |
| 11 | **Retention**: NDA records for **the term + 2 years**. **IPs and audit logs: 12 months.** (§4.10) |
| 12 | Every IT7Q-built site gets a thumbnail + `pN.it7q.com.au` link. Consent covers all. |
| 13 / 16 | Content: build pack (primary) + business plan (secondary, private). Every project gets a card; full info gated. |
| 14 | Public card = image + one-liner + "why it's unique" (build pack). |
| 15 | **Public plain-English Services page.** Internal tooling (what IT7Q runs behind the scenes) stays gated. |
| 17 | **Blog + Downloads launch only if 2–3 blog posts are ready at launch.** Otherwise both wait for a later release. Portal logins parked. |
| 18 | **Public facts**: phone **0411 753 366**, ABN **43 922 878 001**, **Kallangur QLD 4503**, contact **info@it7q.com.au** (Chris creates it). **No numeric hero stats** until Chris supplies ones that are true today. |
| 19 | **Enquiry form** → `website-enquiry` webhook, same protections as the NDA hooks, emails **chris@it7q.com.au** (sent from noreply@). |
| 20 | **Cloudflare Web Analytics** (cookieless). **No cookie banner.** |
| 21 | Stdlib-only Python build: yes. |
| 22 | Logos from `_brand/` (§1). The Elementals MP4 is gone; the hero logo is an **animated SVG**. |
| 23 | Gated text at feature level only (§4.9). |
| 24 | Every project placed (§2.1). |
| 25 | TEMPESTAS tiers T1 Scout → T5 Citadel; prices/specs gated; SCUTUM = MSP antivirus only. |
| 26 | **FABRICUS**: launch with names/one-liners + **photo placeholders**. |
| 27 | **Portfolio**: each `pN` site becomes a **static snapshot on its own Pages project**. WordPress sites get exported to static HTML first. Old `tc/rb/pr/aa` names **redirect** to `pN`. Steps in §6.3; no DNS changes yet. |
| 28 | **SCUTUM's "from" price is public.** Every other product/hardware price is gated. |
| 31 | **FABRICUS register**: F-001–F-035 from the July 2026 plan-sheet handover. I write the public one-liners. F-016 is the TABULAE medal board. F-020–F-023 and F-031 are marked **to verify** (F-031 may duplicate F-020). Shop-use jigs and tools are excluded (not retail). |
| 32 | Requests that never become an NDA (pending too long, or rejected) are kept **12 months**. |

---

## 2. Site map and pages

Home users first, small business second, all in plain English.

```
/                         Home
/about/                   About + mission
/divisions/               All seven divisions (badge cards → division pages)
/divisions/msp/           ┐
/divisions/opus/          │  Each page: division intro (public)
/divisions/mentis/        │  + grid of project cards (public: image, one-liner, why unique)
/divisions/tempestas/     │  + per-card "Full details" locked panel.
/divisions/portus/        │  Gated detail loads per division after an approved
/divisions/fabricus/      │  login (see §4).
/divisions/domus/         ┘
/portfolio/               Client websites, p1–p7 (every IT7Q-built site)
/services/                "How we can help": plain-English services + enquiry form
/contact/                 Phone, info@, WhatsApp/Messenger, short form
/access/                  NDA: read, request access, log in, log out
/investors/               Investor & partner area: shell page, all content gated (per-person access)
/blog/  /blog/<slug>/     Only if 2–3 posts are ready at launch (Q17)
/downloads/               Ships with the blog, or waits with it (Q17)
/legal/privacy/  /legal/terms/  /legal/nda/
/404.html
```

`/legal/cookies/` is dropped as a separate page. The privacy page states that the site sets no cookies and uses cookieless Cloudflare Web Analytics (Q20). Session tokens sit in `sessionStorage`, not cookies.

**Page notes**
- **Home**:
  1. Hero: the **animated master logo** (inline SVG, CSS animation of the four circles; static under `prefers-reduced-motion`) + tagline. **No numeric stats** until Chris supplies true ones (Q18).
  2. **Badge row**: seven division badges in business-card style, each in its colour, with the Latin name and translation under it (MSP Managed Services · OPUS Works & Projects · MENTIS Mind & Intelligence · TEMPESTAS Storm & Hardware · PORTUS Harbour & Gateway · FABRICUS Craft & Making · DOMUS Home & Dwelling). Each badge links to its division page.
  3. Then mission, a "how we help" strip (home → small business), a T3 Guard feature, a portfolio highlight, an investor/partner call to action to `/access/`, and contact.
- **Division pages**: one template. Header = the division badge + descriptive subtitle (§1). Cards come from `src/data/projects.json` via `tools/build.py`. Gated detail is **not** in that file. Status badge per card: *Developed · In development · In design · Documented*.
- **MENTIS page** also carries a plain-English **"AI automations we can set up"** services list (from v2: patch management, social media pipeline, invoice/phone-system automation, email triage, security alerting, compliance reporting). It's a list, not cards (Q24).
- **Services**: plain-English public services for homes and small business. How IT7Q delivers them internally (tooling, stack) is gated (Q15). The enquiry form has service and division selectors.
- **Contact / footer**: phone 0411 753 366, info@it7q.com.au, ABN 43 922 878 001, Kallangur QLD 4503.
- **Portfolio**: §2.2.
- **Parked**: client portal dashboard, admin portal login, Neo evaluation workflow, WordPress (§9).

### 2.1 Project inventory (public card list)

Names and statuses come from the build pack unless marked otherwise. "Status" is my reading of the sources; Chris confirms before build (**TBC** = no source gives one). Each card gets an image ID `P-<div>-<nn>` (§5).

**MSP — Managed Services**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MSP-01 | SCUTUM — managed antivirus/EDR. **Public "from" price shown** (Q28) | In development | build pack |
| P-MSP-02 | MSP Companion App (one-click enrolment) | In development (pilot) | build pack |
| P-MSP-03 | Managed security monitoring | Developed | build pack |
| P-MSP-04 | IT7Q Support Portal | In development | build pack, v2 |
| P-MSP-05 | IT7Q SysMon (server health monitoring) | TBC | v2 |

**OPUS — Works & Projects (software products)**
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
| P-OPUS-10 | Andromeda CE / Andromeda AI companion | TBC | v2, Feb notes |
| P-OPUS-11 | Aegir — SecureStart (Windows privacy/setup tool) | TBC | v2 |

**MENTIS — Mind & Intelligence (AI & automation)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MEN-01 | Project Persephone (AI agent workforce). Its named agents appear **only in Persephone's gated detail**, with no cards of their own | Developed (partly live) | build pack, v2 |
| P-MEN-02 | MNEMOSYNE (AI memory layer) | In development | build pack |
| P-MEN-03 | Neo (AI website builder) | In development | build pack |
| P-MEN-04 | FORTUNA (investment-monitoring agent). Own card, labelled **"Part of Persephone"** | TBC | build pack, v2 |
| P-MEN-05 | COLLOQUIUM (business chat/AI assistant service) | TBC | Feb notes |
| — | v2 "AI Automations" → **services list on the MENTIS page**, not cards | — | v2 |

**TEMPESTAS — Storm & Hardware (cybersecurity hardware)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-TEM-01 | T1 Scout | In development | Chris (Q25), v2 |
| P-TEM-02 | T2 Sentinel | In development | Chris (Q25), v2 |
| P-TEM-03 | T3 Guard (**hero**: featured card, first on the page, featured on Home) | In development | Chris (Q25), v2 |
| P-TEM-04 | T4 Fortress | In development | Chris (Q25) |
| P-TEM-05 | T5 Citadel | In development | Chris (Q25) |
| P-TEM-06 | TEMPESTAS T3 carrier board | In design | build pack, v2 |

Public tier cards show only the tier name, a one-liner and who it's for. Prices, hardware specs and the CM5/x86 split are gated, at feature level (§4.9). The carrier board card stays generic in public ("our own Australian-designed board").

**PORTUS — Harbour & Gateway (community safety)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-POR-01 | PORTUS community safety network (absorbs K.I.T.S.) | In design | build pack, business plan |
| P-POR-02 | PORTUS App | TBC | v2 |
| P-POR-03 | PORTUS Jnr (child-safe version) | TBC | v2 |

**FABRICUS — Craft & Making (woodcraft & digital manufacturing)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-FAB-101 | FABRICUS App (offline order/catalogue PWA) | TBC | Feb notes |
| P-FAB-102 | FORMAE custom 3D prints | TBC | Feb notes |
| P-FAB-103 | BIONICUS assistive body supports (Project Bionic) | TBC | Feb notes |

**FABRICUS product range** (Q31). Source: July 2026 plan-sheet handover. Card ID = `P-FAB-` + the F-number (e.g. F-007 → `P-FAB-007`). Status for all: In development. All launch with photo placeholders (Q26). Public one-liners are mine, in plain English, and Chris checks them. **To verify** items are held out of the public build until Chris confirms them (Q38); `tools/check.py` fails if a `verify: true` card reaches `dist/`.

| F-no. | Name | Public one-liner (draft) | Note |
|---|---|---|---|
| F-001 | Toilet roll holder with shelf & planter nook | A toilet roll holder with a handy shelf on top and a little nook for a plant. | |
| F-002 | Towel rail with shelf | A wall towel rail with a shelf above for the bits you reach for every day. | |
| F-003 | Tea-towel ladder rack with roll holder | A ladder-style rack for tea towels, with a paper-towel roll built in. | |
| F-004 | L-shape spice rack with paper towel holder | A corner-friendly spice rack that keeps the paper towel within reach too. | |
| F-005 | Wall pantry rack with paper towel holder | Wall-mounted pantry shelving that frees up bench space, with a paper towel holder. | |
| F-006 | Bathroom cubby unit (3 x 3) | Nine open cubbies to keep towels, toiletries and bits sorted. | |
| F-007 | Rustic mini wall dresser, 2 drawers | A small rustic dresser that hangs on the wall, with two drawers for odds and ends. | |
| F-008 | Spice cabinet with towel rail, curved legs | A free-standing spice cabinet on curved legs, with a towel rail on the side. | |
| F-009 | Slatted arch mail & key holder | An arched, slatted organiser by the door for mail and keys. | |
| F-010 | Shield key holder with shelf & peg keyrings | A shield-shaped key holder with a small shelf and matching peg keyrings. | |
| F-011 | Horse planter | A horse-shaped planter that brings a bit of character to the garden or veranda. | |
| F-012 | Market cart / flower wagon planter | A little market-cart planter for flowers, herbs or a front-porch display. | |
| F-013 | Heart phone stand | A heart-shaped stand that holds your phone upright on a desk or bedside. | |
| F-014 | Automotive wall clock | A wall clock with a motoring theme, for the garage, shed or games room. | |
| F-015 | LED-lit sign plaque (custom text) | A personalised sign plaque with your own text, softly lit by LEDs. | |
| F-016 | Medal display shadow box with photo | A shadow box that displays medals alongside a photo, made to honour service and achievement. | **TABULAE** medal board |
| F-017 | Solid timber TV entertainment unit | A solid timber entertainment unit for the TV and everything that goes with it. | |
| F-018 | LED TV feature wall with slats & shelves | A slatted TV feature wall with shelves and LED accent lighting. | |
| F-019 | Simple workbench | A sturdy, no-fuss workbench for the shed or garage. | |
| F-020 | Stepped bedside table with asymmetric hutch | A bedside table with stepped levels and an off-centre hutch for books and bits. | **to verify** |
| F-021 | House-shaped wall key holders (3 variants) | Little house-shaped key holders for the wall, in three styles. | **to verify** |
| F-022 | Illuminated shadow-box frame planters | Shadow-box frames that double as planters, with built-in lighting. | **to verify** |
| F-023 | Serving trays (standard & elevated) | Timber serving trays, flat or raised, for entertaining. | **to verify** |
| F-024 | Cap display rack | A wall rack that shows off a cap collection neatly. | |
| F-025 | LED wall clock with shelf | A wall clock with LED lighting and a small display shelf. | |
| F-026 | Honeycomb hex shelf | Hexagon shelves that fit together in a honeycomb on the wall. | |
| F-027 | Kids' tree bookshelf | A tree-shaped bookshelf that makes kids' books part of the room. | |
| F-028 | Diagonal mug shelf | A diagonal wall shelf that shows off a mug collection. | |
| F-029 | Live-edge wine rack | A wine rack cut from live-edge timber, so each piece is one of a kind. | |
| F-030 | Bedside valet / dock | A bedside tidy for your phone, watch, wallet and keys. | |
| F-031 | Nightstand with hutch | A nightstand with a hutch on top for a lamp, books and the alarm clock. | **to verify** (may duplicate F-020) |
| F-032 | Standing bird table | A free-standing bird table for the backyard. | |
| F-033 | Asymmetric geometric wall shelf | A geometric wall shelf with an off-beat, modern shape. | |
| F-034 | Arched slat-panel shelf | An arched shelf with a slatted back panel, for display or storage. | |
| F-035 | Guitar stand & media station | A stand for your guitar with room for the amp, music and gear. | |

Shared "why it's unique" for the range (from the build pack): *bespoke, maker's-marked, made in-house on IT7Q's own CNC and 3D printer.* TABULAE is no longer a separate project name in the inventory; it's F-016.

**DOMUS — Home & Dwelling (smart home)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-DOM-01 | Smart, segmented, private home setup | Documented / service | build pack, business plan |

**Totals**: MSP 5 · OPUS 11 · MENTIS 5 · TEMPESTAS 6 · PORTUS 3 · FABRICUS 38 (35 range + 3) · DOMUS 1 = **69 cards**. 64 of them are public at launch while the 5 to-verify items are held back (Q38).

Retired, so no card: original single-tenant Calendi for Pine Rivers RSL, and the NEXUS division (3CX/NBN), replaced by OPUS.

### 2.2 Portfolio

Consent is on file for **all** IT7Q-built sites.

| Label | Client | Link | Old name (redirects) | Repo (Chris's GitHub) |
|---|---|---|---|---|
| p1 | True Colours DSS | `p1.it7q.com.au` | `tc.it7q.com.au` | `TCDSS_Website` |
| p2 | Red Bird | `p2.it7q.com.au` | `rb.it7q.com.au` | — |
| p3 | Pine Rivers RSL | `p3.it7q.com.au` | `pr.it7q.com.au` | `PRRSL_Website` |
| p4 | The Artist Apron | `p4.it7q.com.au` | `aa.it7q.com.au` | — |
| p5 | Burpengary Jets | `p5.it7q.com.au` | — | — |
| p6 | BlueVibes (placeholder name, Q29) | `p6.it7q.com.au` | — | `BlueVibes_Website` |
| p7 | AustPathClub (placeholder name, Q29) | `p7.it7q.com.au` | — | `AustPathClub` |

The cards show client name, thumbnail and outbound `pN` link. Future sites take p8…. The `published` flag in `portfolio.json` stays, and `tools/check.py` fails if an unpublished entry appears in `dist/`. Hosting steps: §6.3.

---

## 3. Reuse from v2 vs rebuild

| Area | Decision | Notes |
|---|---|---|
| Colours, fonts, logo | **Replace** with the business-card brand + `_brand/` SVGs | Self-host Rajdhani + Exo 2 (woff2), no Google Fonts. |
| Hero copy, tagline | **Reuse, re-case** | Card's sentence-case tagline + build pack mission. **No stats** (Q18). |
| Division card / portfolio card design, nav, scroll animations | **Reuse, refactor** | `addEventListener` instead of inline `onclick` (strict CSP). Respect `prefers-reduced-motion`. |
| v2 product list | **Mine for names only** | Folded into §2.1. v2 automations become the MENTIS services list. |
| NDA legal text | **Rewrite** | One-way, 3-year draft in `docs/nda-draft.md` (Q10). |
| Cookie banner | **Drop** | No cookies; cookieless analytics (Q20). |
| NDA modal, contact form, `alert()` validation, emoji icons, modal a11y | **Rebuild** | |
| Jan spec portal dashboard | **Drop** | Advertises internal hostnames. |

**Repo layout**
```
src/                 page sources + partials
  data/projects.json public card data only (no gated detail)
  data/portfolio.json
  assets/css|js|fonts|img
  assets/img/brand/  sanitised SVGs from _brand/ (only those used)
tools/build.py       stdlib-only Python: partials + data → dist/ (Q21)
tools/check.py       links, HTML sanity, gated-content leak check, infrastructure guard on gated/,
                     unpublished-portfolio check, financial-figure guard, price guard, SVG sanitiser check
dist/                build output, the only thing deployed (git-ignored)
gated/               feature-level gated detail per division as JSON, NEVER in dist/ (§4.9)
n8n/workflows/       nda-submission, nda-login, nda-content, nda-review, website-enquiry, nda-retention (scheduled)
n8n/sql/             001_schema.sql, 002_seed_gated.sql (generated)
deploy/              Cloudflare Pages, DNS record list, portfolio snapshots, n8n import, Postgres, env vars
docs/IMAGES.md       image checklist (mirrors §5)
docs/nda-draft.md    NDA rewording for Chris's review (Q10)
_brand/              brand pack zips (git-ignored)
```

`tools/check.py` guards:
- **Financial guard**: refuses to build if a `$` amount sits next to revenue/projection-style words in `src/` or `gated/`.
- **Price guard** (Q28): the only `$` amount allowed in public files is SCUTUM's "from" price, kept as one named field in `projects.json`. Any other price in `src/` fails.
- **Infrastructure guard** (§4.9) on `gated/`.
- **SVG check**: no `<script>`, `on*` attributes, `<foreignObject>` or external references in any committed SVG.

---

## 4. NDA flow design

Unchanged in principle. Content is **per project**, delivered per division. UX order: T&C tick → NDA modal + tick → email → emailed NDA copy → manual approval → emailed login + password → unlock.

### 4.1 Principles
1. **Fail closed.** Locked is the default markup. Detail renders only on a 200 + valid JSON from `nda-content`. Everything else stays locked.
2. **Signing grants nothing.** `nda-submission` only creates `pending`. Only `nda-review` approval enables login.
3. **No gated content in public files**: not hidden, simply absent.
4. **No secrets in the site.** Only the public Turnstile site key appears in it.
5. **The server re-checks everything on every request.** Revocation and NDA expiry take effect on the next call.
6. **No enumeration.** The same reply goes out for new, duplicate, rejected and unknown emails.

### 4.2 Protection layers (all five public webhooks)
| Layer | What |
|---|---|
| Cloudflare edge header | A Transform Rule sets `X-IT7Q-Edge` on `hooks.nubius.com.au/webhook/*`; n8n Header Auth checks it. |
| CORS | Allowed origin `https://it7q.com.au` (+ the Pages preview origin while testing). |
| Turnstile | Widget on every form (NDA, login, enquiry). n8n verifies server-side and checks hostname + action. Honeypot + min fill time as backup. |
| Rate limits | Cloudflare WAF rule where the free plan allows, plus Postgres-backed per-IP/per-email counters in n8n. Login lockout: 5 fails/15 min. |
| Validation | JSON only, ≤ 8 KB, strict allow-list, NDA version/hash must match. |
| Least-privilege DB | Separate `it7q_web` database/role. |
| No caching | Cloudflare bypass on `/webhook/*`; `Cache-Control: no-store`. |
| Cloudflare Access | On `/webhook/nda-review*` only, Chris's email only (Q4). |
| Audit | Every event logged in `nda_audit` (kept 12 months, §4.10). |

### 4.3 `nda-submission`
1. The visitor reads the NDA (the page embeds its version + SHA-256). They give name, email, org, reason, typed signature, NDA tick, T&C tick and Turnstile, plus a hidden honeypot + timestamp. They can tick **"I'm an investor or potential partner"** to request Investors access (Q6).
2. POST to `https://hooks.nubius.com.au/webhook/nda-submission`. Nothing unlocks.
3. n8n checks: edge header → size/schema → honeypot/timing → Turnstile → rate limits.
4. Upsert into `nda_requests` with status `pending`, server timestamp, IP, UA and NDA version/hash. No duplicate if one is already pending or approved.
5. Email the signer (from `noreply@`, Reply-To `info@`) an **HTML copy** of the agreed NDA + the acceptance record (name, email, time, version, hash), saying it's reviewed manually. No PDF (Q9).
6. Email **chris@it7q.com.au** the same HTML record + an approval alert with a Review link.
7. Reply `202` with a neutral message.

### 4.4 `nda-review`
- One-time token link (SHA-256 stored, 7-day expiry, single use), behind **Cloudflare Access** (Q4). GET shows a confirm page; **only POST changes state**, so mail-scanner prefetch can't approve anyone.
- **Approve**: status `approved`, **all seven divisions** granted by default, plus an **Investors** tick (off by default, pre-filled from the signer's request; Chris decides) (Q6). `expires_at` = signed + 3 years (Q10). It generates a ≥ 16-char password, stores an scrypt hash only, and emails the login + `/access/` link.
- **Reject / revoke / reset / toggle Investors**: the same workflow. Revoke kills sessions immediately.

### 4.5 `nda-login`
1. Email + password + Turnstile, POSTed via Cloudflare.
2. Edge header, Turnstile, lockout. Dummy scrypt for unknown emails. `timingSafeEqual`. Requires approved, not revoked, NDA not expired.
3. Session token = 32 random bytes. Only its SHA-256 is stored. **8 h absolute / 1 h idle** (Q7).
4. One generic 401 for every failure.
5. The token lives in `sessionStorage` only (tab-only).

### 4.6 `nda-content`
1. A division page loads public cards with locked panels.
2. With a token, one POST `{division}` returns the gated detail for every project in that division (structured JSON, `no-store`). `/investors/` posts `{division:"investors"}`.
3. n8n re-checks the session, approval, revocation, NDA expiry and scope (`investors` needs `investor_access`).
4. Rendering uses DOM APIs only (no `innerHTML`), with a watermark: "Confidential — shared with <email> under NDA".
5. 401/403 → clear the token and re-lock. Network/5xx → stay locked, "try again". No cached fallback.
6. `{action:"logout"}` deletes the session server-side.

Honest limits: an approved viewer can still copy or screenshot. The NDA, watermark, audit log and revocation are the controls for that.

### 4.7 `website-enquiry` (Q19)
- Name, email, phone (optional), service, division, message, Turnstile, honeypot + timing.
- Same edge header, CORS, Turnstile, rate-limit and validation layers as the NDA hooks.
- Emails **chris@it7q.com.au** from `noreply@`, with Reply-To set to the enquirer. Neutral `202` reply.
- Logged in `enquiries` (kept 12 months). Nothing else is stored.

### 4.8 Data model (sketch)
```
nda_requests       id, email, name, org, reason, wants_investor, nda_version, nda_sha256,
                   signature_text, signed_at, signed_ip, signed_ua, status, approved_at,
                   approved_divisions[] (default all 7), investor_access (default false),
                   expires_at, password_hash, revoked_at, created_at, purge_after
nda_review_tokens  token_sha256, request_id, expires_at, used_at
nda_sessions       token_sha256, request_id, created_at, last_seen_at, expires_at, ip, ua
nda_content        division, project_id, version, body jsonb, updated_at   -- seeded from gated/
nda_rate           key, window_start, count
nda_audit          id, at, event, request_id, ip, ua, detail jsonb
enquiries          id, at, name, email, phone, service, division, message, ip
```

### 4.9 Gated content rules (Q23)
Gated detail tells an approved reader **what** a project does, how it helps, where it's at and what's next. It never says **how it's wired up**.

| Allowed behind the NDA | Never, even behind the NDA |
|---|---|
| Features and capabilities in plain English | Ports, internal or external hostnames, IP addresses |
| Who it's for, the problem it solves, why it's different | Repo URLs, git hosts, package/apt repos |
| Status, milestones, roadmap in general terms | WireGuard, tunnels, VPN layout, network topology |
| General tech family where it helps (e.g. "self-hosted", "runs on a Raspberry Pi compute module", "uses AI models") | Service/agent internals, enrolment mechanisms, auth tokens, retention/config values |
| Integrations by product name (e.g. "works with Athena and Nexus"); Persephone's agents by name (Q24) | Exact software versions or security-tool placement that maps the attack surface |
| Prices (all except SCUTUM's public "from" price, Q28) | Anything from the business plan's financials |

Process: I write each project's gated text from the private build pack into `gated/<division>.json` with those rules applied. Chris reviews it before it's seeded into Postgres. `tools/check.py` scans `gated/` and fails on IPv4/IPv6 addresses, `:<port>` patterns, hostnames (`*.nubius.com.au`, `*.it7q.com.au` other than public `pN`/`www`/`downloads`), `git.`/`.git` URLs and words like `WireGuard`, `wg0`, `tunnel`, `port`.

### 4.10 Retention (Q11)
A scheduled n8n workflow, `nda-retention` (daily, not a webhook), handles it:

| Data | Kept for | Then |
|---|---|---|
| Approved NDA records (`nda_requests`) | NDA term (3 years) **+ 2 years** from signing | Row deleted |
| `signed_ip`, `signed_ua` on NDA records | **12 months** | Set to null; the rest of the record stays |
| `nda_audit`, `nda_rate`, `enquiries` | **12 months** | Deleted |
| `nda_sessions` | Until expiry | Deleted |
| `nda_review_tokens` | Until used or expired | Deleted |
| Pending/rejected requests that never became an NDA | **12 months** (Q32) | Deleted |

Trade-off: once the IP is nulled at 12 months, the record still holds name, email, typed signature, time, version and hash, but not the IP. Chris chose this; the privacy page states all of these periods.

### 4.11 Chris's server-side setup (documented in `deploy/`, not done by me)
- Mailboxes: **`noreply@it7q.com.au`** (MXRoute, sending only) and **`info@it7q.com.au`**. SPF/DKIM/DMARC for `it7q.com.au` must cover MXRoute.
- n8n credentials, referenced by name only: `IT7Q Edge Header`, `Turnstile secret`, `Postgres it7q_web`, `Mail sender (noreply@)`.
- n8n env var `NODE_FUNCTION_ALLOW_BUILTIN=crypto` (compose change under `/opt/it7q`).
- Postgres `it7q_web` DB + role, then run the SQL.
- Cloudflare: Transform Rule, cache bypass, rate-limit rule, Turnstile widget, **Access on `nda-review`**, Web Analytics on the Pages project.

---

## 5. Image and media list

Every image starts as a visible placeholder (`PLACEHOLDER <ID> — description (w×h)` + matching `alt`). **Public images must not reveal gated detail**: no schematics, board close-ups, admin screens or architecture diagrams.

**Site-wide**
| ID | Asset | Where | Size / format |
|---|---|---|---|
| IMG-01 | **Animated master logo**: inline SVG from the IT7Q master pack (`IT7Q_logo_reverse-on-dark.svg`, or the emblem), animated with CSS on the four circle paths (static when reduced motion is on) | Home hero | SVG |
| IMG-02 | Static master logo | Header, footer | SVG (`_brand/`) |
| IMG-03 | Favicon set | All | From the pack: `favicon.ico`, 32 px, 180 px, 192/512 px |
| IMG-04 | Open Graph share image | All | 1200×630 |
| IMG-05–11 | Division badges ×7: pack **emblem** (reverse-on-dark) + Latin name and translation as HTML text | Home badge row, divisions index, division pages | SVG (`_brand/` division packs; MSP uses the master, Q37) |
| IMG-12–18 | Division header thumbnails ×7 | Divisions index, division pages | 1200×750 |
| IMG-29 | Photo of Chris | About | 800×800 |
| IMG-30 | Workshop/workspace photo (no gated detail visible) | About, Services | 1600×900 |
| IMG-31 | Helping a home user | Home, Services | 1600×900 |
| IMG-32 | Helping a small business | Services | 1600×900 |
| IMG-33 | Blog covers (one per post, if the blog ships) | Blog | 1200×630 |
| IMG-34 | Tutorial video thumbnails (if the blog ships) | Blog | 1280×720 |

**Portfolio**
| ID | Asset | Size |
|---|---|---|
| IMG-19 | p1 True Colours DSS screenshot | 1600×1000 + mobile 750×1334 |
| IMG-20 | p2 Red Bird screenshot | as above |
| IMG-21 | p3 Pine Rivers RSL screenshot | as above |
| IMG-22 | p4 The Artist Apron screenshot | as above |
| IMG-23 | p5 Burpengary Jets screenshot | as above |
| IMG-35 | p6 screenshot | as above |
| IMG-36 | p7 screenshot | as above |
| IMG-24–28, IMG-37–38 | Client logos p1–p7 (if consent covers logos) | SVG/PNG |

Screenshots are taken from the static snapshots (§6.3), so they match what the link shows.

**Project cards** (one public-safe image each, 800×500 WebP; render, photo, product shot or illustrative graphic)
| IDs | Count | Notes |
|---|---|---|
| P-MSP-01…05 | 5 | UI mock-ups or illustrative graphics, not real admin screens |
| P-OPUS-01…11 | 11 | App screenshots with dummy data |
| P-MEN-01…05 | 5 | Illustrative (agent "team" graphic etc.) |
| P-TEM-01…06 | 6 | One per tier (T3 Guard gets a larger hero image, 1600×1000) + carrier board. **No PCB/schematic close-ups or spec labels** |
| P-POR-01…03 | 3 | Concept art/signage, no real locations of people's homes |
| P-FAB-001…035, P-FAB-101…103 | 38 | F-001–F-035 product photos (placeholders at launch, Q26) + FABRICUS App, FORMAE, BIONICUS |
| P-DOM-01 | 1 | Generic smart-home photo |

That's **69 project images** (64 needed for launch while the 5 to-verify items are held back).

**Gated** (served only via `nda-content`, never in `dist/`): G-<project-id> detail images where useful, ≤ 300 KB each, as data URIs. Investor presentation assets: G-INV-xx.

---

## 6. Deployment approach

**Cloudflare Pages, free plan.**
- Private repo → Pages builds with `python3 tools/build.py` → publishes `dist/` only. `gated/`, `n8n/`, `deploy/`, `_brand/` and `_source/` never publish.
- `_headers`: strict CSP (`default-src 'self'`; `script-src` self + `challenges.cloudflare.com` + `static.cloudflareinsights.com`; `connect-src` self + `https://hooks.nubius.com.au` + `https://cloudflareinsights.com`; `frame-src challenges.cloudflare.com`; `img-src 'self' data:`; `frame-ancestors 'none'`), HSTS, `nosniff`, `Referrer-Policy`, `Permissions-Policy`.
- **Cloudflare Web Analytics** (Q20): enabled on the Pages project. Cookieless, so no banner.
- Preview deploys on `<project>.pages.dev` for testing.
- Free-plan limits: 500 builds/month, 20,000 files. Neither is an issue here.
- Release flow: branch → PR → Chris reviews → merge to `main` → Pages deploys.

### 6.1 DNS: records needed (listed only; Chris decides and makes the changes)

Nameservers are already on Cloudflare, so the zone is managed there. Adding a custom domain in Pages creates the matching record. Chris does that at go-live, after checking nothing already sits on those names.

| Record | Purpose | Points to | Notes |
|---|---|---|---|
| `it7q.com.au` (apex) | Main site | Pages project | CNAME at the apex (Cloudflare flattens it). Check what the apex points at today first |
| `www.it7q.com.au` | Main site | Pages project | Redirect www → apex (or the reverse; Chris's pick) |
| `p1`–`p7.it7q.com.au` | Portfolio snapshots | One Pages project each (§6.3) | Created by Pages → Custom domains |
| `tc` / `rb` / `pr` / `aa.it7q.com.au` | Old portfolio names | Proxied placeholder record + redirect rule → `p1`–`p4` | §6.3 step 7 |
| `downloads.it7q.com.au` | Existing (build pack) | unchanged | Confirm it stays |
| MX / SPF / DKIM / DMARC | noreply@ and info@ on MXRoute | MXRoute | Check SPF/DKIM cover MXRoute's sending hosts |
| `hooks.nubius.com.au` | Webhooks | Existing cloudflared tunnel | Different domain; no change |

Turnstile needs no DNS, just the widget's allowed hostnames (`it7q.com.au`, `www`, the preview origin).

### 6.2 Verification before go-live (fail-closed tests)
1. Submit the NDA → still locked; signer's HTML copy + Chris's alert both arrive, from `noreply@`.
2. Log in while pending → generic refusal.
3. Approve without Investors → all seven divisions load, `/investors/` stays locked. Tick Investors → it loads.
4. Revoke → the next request locks.
5. Tampered or expired token, idle > 1 h, session > 8 h → locked.
6. NDA past `expires_at` → login refused.
7. n8n down → locked, with a friendly error.
8. No Turnstile / not via Cloudflare → rejected (all five hooks).
9. Review link without Cloudflare Access login → blocked.
10. Rate limits trigger and recover.
11. `nda-retention` on a test DB with back-dated rows → correct rows nulled/deleted.
12. `tools/check.py`: no gated canary/text, no unpublished portfolio entry, no financial figures, no price other than SCUTUM's in `dist/`; no infrastructure detail in `gated/`; SVGs clean. View-source spot checks.
13. Accessibility (axe/Lighthouse, including badge colour contrast), links, mobile.

### 6.3 Portfolio snapshots on Pages (Q27, plan only)

Each `pN` site becomes a frozen static copy on its own Pages project. Steps, one site at a time, starting with p1:

1. **Inventory** (me, read-only, with Chris): for each site, record the current host, whether it's WordPress or already static, and any dynamic bits a snapshot will break (contact forms, search, logins, booking/calendar widgets).
2. **Export** (WordPress sites): mirror the live site to static HTML with `wget --mirror --convert-links --adjust-extension --page-requisites --no-parent`. That's in-house, with nothing installed on the client's WordPress. Then strip `wp-json`, `xmlrpc`, `?ver=` query strings, oEmbed and login links. Already-static sites (likely the ones with GitHub repos: p1, p3, p6, p7) skip this step if their repo matches what's live.
3. **Fix dynamic bits**: forms become a `mailto:` link or are removed (Q33). No external form services.
4. **Repo per snapshot**: a private repo per site (e.g. `IT7Q/p1-snapshot`), or the existing repo where it's already static. No build command; output directory is the site root. Add a `_headers` with a basic CSP and `X-Robots-Tag` if needed (Q33).
5. **Pages project** `it7q-pN` (Chris creates it), connected to that repo. Check it on `it7q-pN.pages.dev`: pages, images, links, mobile.
6. **Custom domain** `pN.it7q.com.au` added in Pages (Chris, at go-live). Pages creates the DNS record.
7. **Old names** (`tc`→p1, `rb`→p2, `pr`→p3, `aa`→p4): keep a proxied DNS record on each old name, and add one Cloudflare **Single Redirect** rule per name: `301` to `https://pN.it7q.com.au` with path and query kept. Test with `curl -I` on a few deep links.
8. **Retire old hosting** for each site once its `pN` and redirect are verified (Chris).
9. **Screenshots** for IMG-19–23/35–36 are taken from the snapshots.

Nothing in §6.3 touches DNS until Chris does steps 6–8.

---

## 7. Build phases (one step at a time)

0. ✅ Repo, source, plan v1. ✅ Financials removed from repo + history, GitHub purge done (§10). ✅ Plans v2–v6. ✅ NDA draft for review. ✅ Brand packs extracted and checked.
1. Scaffold `src/`, build/check tools, brand tokens, base CSS, header/footer, placeholder component, Home (animated logo + badge row). **Needs the brand decision first (Q37).**
2. Public pages: About, Divisions index + 7 division pages with cards from `projects.json`, MENTIS services list, Portfolio, Services, Contact, Legal.
3. NDA front end (`/access/`, locked panels, renderer) and enquiry form against a local mock with failure simulation.
4. Gated content: feature-level `gated/` JSON (§4.9, Chris reviews), the n8n workflows (five webhooks + `nda-retention`), SQL, `deploy/` docs for Chris to review.
5. Investors shell; Blog + Downloads only if 2–3 posts are ready (Q17).
6. QA (§6.2), preview deploy, Chris walk-through, DNS (Chris), go live.
7. Portfolio snapshots (§6.3), one site at a time. This can run alongside phases 2–6.

---

## 8. Open questions for Chris

**Answered**: 1–28 except 29; 30 (packs supplied); 31 (FABRICUS register); 32 (12 months). See §1a.

**Still open**
29. **p6/p7 display names**: how should BlueVibes and AustPathClub appear on their cards? Is there a one-liner for each? Placeholders stay until then.
33. **Snapshot details (§6.3)**: (a) which p1–p7 sites are WordPress and where each is hosted today; (b) do any clients still edit their site? A frozen snapshot would stop that; (c) are any `pN` sites copies of a client's own live domain? If so, the snapshot should carry `noindex` or a canonical link to avoid duplicate-content issues; (d) are forms on snapshots dropped, or replaced with a `mailto:` link?
34. **Hero stats**: none at launch. Send the true-today numbers whenever you want them added.
35. **Project statuses** marked TBC in §2.1 (SysMon, Andromeda CE, Aegir, FORTUNA, COLLOQUIUM, PORTUS App/Jnr, FABRICUS App, FORMAE, BIONICUS), and a quick confirm of the rest.
36. **NDA draft** (`docs/nda-draft.md`): your review, then a legal check. The reviewer should look at the flagged points in its notes, especially whether confidentiality should outlast the 3-year term.

**New**
37. **Brand conflict (blocks Phase 1)**: the packs don't match the business card on master colours, navy, taglines, MSP, OPUS or TEMPESTAS (§1b). Pick one:
    1. pack artwork + pack palette, card words as HTML text (recommended);
    2. card wins, packs get recoloured;
    3. pack artwork with only the mismatched divisions recoloured.

    Also: is there meant to be a separate **MSP** pack, or does MSP use the IT7Q master?
38. **To-verify FABRICUS items** (F-020–F-023, F-031): hold them out of the public build until verified (my default), or show them now? And is F-031 a duplicate of F-020?
39. **FABRICUS one-liners** (§2.1): check my drafts. They're kept to what the names say, with no materials, sizes or prices assumed.

---

## 9. Parked (pins)
- Client portal dashboard / SSO (Jan spec): needs its own auth design and shouldn't advertise internal hostnames.
- Admin portal login: better as a bookmark behind Cloudflare Access.
- Neo website-evaluation workflow.
- WordPress version: superseded.
- Blog + Downloads, if fewer than 2–3 posts are ready at launch (Q17).

---

## 10. Repo housekeeping log
- **26 Oct 2026: investor financials removed.**
  - The Jan spec and Feb redesign transcripts were moved to `/srv/work/it7q-private` and git-ignored.
  - History was rewritten (authorised one-off) and force-pushed. `main` now has no commit containing them.
  - A backup bundle of the old history is in `/srv/work/it7q-private` (contains financials; delete once you're happy).
  - The August build pack was moved to `/srv/work/it7q-private` and git-ignored. It was never committed.
  - **GitHub purge done (26 Oct, Chris):** the repo was deleted and recreated. Fetching `b39954a` by SHA now returns "not our ref". Nothing pending.
- **26 Oct 2026: plan v5.** `_brand/` zips git-ignored.
- **27 Oct 2026: plan v6.** Brand packs extracted (outside the repo) and colour-checked. FABRICUS register F-001–F-035 added.
