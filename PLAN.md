# IT7Q website rebuild — plan

Status: **v12, 29 Oct 2026. Phases 1–3 and 3b built.** v12 folds in Chris's answers to Q61 (About overlap) and the rest of Q54 (social URLs); Q60 is Chris's click-test, Q53 and Q59 still to come. The site changes they need are queued as Phase 3c (§7). v11 folds in Chris's answers to Q51, Q52, Q54, Q55, Q57 and Q58 (Q53 and Q56 later). v10 adds Chris's 29 Oct scope: Shop (MERCATOR, inside MSP), Resources + Guides, Media, News (HERALD), Credentials, Athena CE download page, footer Staff + social links, and discreet PORTUS wording. The MERCATOR store, video/podcast hosting and the HERALD app are **separate future builds**, not part of this site's launch (§2.6). v9 built Phase 3 (About, Contact with the enquiry form, Legal pages, the NDA front end and a local mock of the webhooks; §4.12). v8 folds in Chris's answers to Q40–Q43: Pillow allowed for JPEG/WebP watermarking, TTF fonts in place, provisional division colours kept, portfolio details (current clients are only Niuleaf and Pro Energy Solutions). It also adds a consent-checked Testimonials section.
Target: `it7q.com.au`, pure HTML/CSS/JS, no frameworks, Australian English.

---

## 0. Bottom line

- **Multi-page static site** on **Cloudflare Pages (free plan)**. Brand = the **April 2026 business card** (Q37): four circles in cyan/lime/purple/orange on navy `#0D1B2A`. The circle **shapes** come from the `_brand/` pack emblem; **none of the pack colours are used**. Copy and layout ideas come from v2. The structure, forms and NDA gate are rebuilt.
- **Every project in every division gets a public card**: image + brief description + "why it's unique". Full detail sits behind the NDA wall. The inventory is **71 cards** (§2.1), all public, 38 of them FABRICUS. IT7Q stays at **seven divisions**: MERCATOR is a section of MSP, not a division.
- **Coming-soon pages, no back ends** (29 Oct): Shop (MERCATOR), Media, News (HERALD) and the Athena CE download page are placeholders on this site. The store, the video/podcast platform and the HERALD app are separate projects (§2.6).
- **Every raster image is watermarked at build time** with the master mark (§5.1): PNG, JPEG and WebP. Sources stay clean; `tools/check.py` fails on any unmarked image in `dist/`. Pillow is the build's one pinned dependency, needed only for JPEG/WebP (Q43).
- **Gated detail never ships in the static site.** It lives server-side (Postgres, read by n8n) and only reaches the browser after an approved login. Any failure keeps the page locked.
- **No secrets in the site.** Protection comes from server-side checks in n8n, Turnstile, rate limits and a Cloudflare-injected edge header.
- **Five webhooks**: four NDA (`nda-submission`, `nda-login`, `nda-content`, `nda-review`) + `website-enquiry` (Q19). All have the same protections. Review links sit behind Cloudflare Access.
- **Mail goes out from a dedicated `noreply@it7q.com.au` MXRoute mailbox.** n8n never holds Chris's own credentials (Q8).
- **Gated detail is written at feature level only.** Even behind the NDA there are no internal ports, hostnames, IPs, repo URLs, WireGuard or infrastructure details (Q23).
- **Portfolio**: p1–p7 are **past clients (archives)**, each a noindex **static snapshot on its own Cloudflare Pages project** at `pN.it7q.com.au` with forms disabled and a "Portfolio snapshot built by IT7Q" banner. The **only current clients** are p8 Niuleaf (links to `https://niuleaf.au`, card shows "Coming soon") and p9 Pro Energy Solutions (reserved and unpublished). Old `tc/rb/pr/aa` names redirect (§6.3). No DNS changes yet.
- **Testimonials** come only from `src/data/testimonials.json`, with consent recorded per entry. The Home section appears only when there's at least one approved entry, and `tools/check.py` fails on any entry without recorded consent (§2.3).
- **Private material stays out of this repo.** The build pack, business plan and the two transcripts with financials all live in `/srv/work/it7q-private` and are git-ignored. No financial figures appear anywhere in this repo. The only public price is SCUTUM's "from" price (Q28).
- Server-side pieces (n8n workflows, SQL, Cloudflare steps, DNS list) are **files for Chris to review and deploy**. I don't touch n8n, Docker, Cloudflare or DNS.

---

## 1. Source material

| Source | Where | Role | Notes |
|---|---|---|---|
| **Business card (Apr 2026)** | Chris (values in this plan) | **Brand**: colours, tagline, badge names | **Wins on brand** (Q37). |
| **`_brand/` packs (Oct 2026)** | `_brand/` (IT7Q master + six division zips; no MSP pack exists, the master covers MSP), git-ignored | **Circle shapes only**: the four traced circle paths from the IT7Q emblem | Pack colours, navy, ring, wordmark and taglines are **not used** (Q37). |
| FABRICUS register (Jul 2026 plan-sheet handover) | Chris (names in §2.1) | F-001–F-035 product names | Shop jigs/tools excluded (not retail). |
| `it7q-website-build-pack.md` (Aug 2026) | `/srv/work/it7q-private/` **only** (never committed) | **Primary for content**: NDA-wall pattern, division/project map, portfolio p1–p4 | Its "Detail (NDA)" blocks are rewritten at feature level for `gated/`, with infrastructure detail dropped (§4.9). Its brand block (navy `#0a1628`, title-case tagline) is superseded by the business card. |
| `IT7Q_Complete_Business_Plan.docx` | `/srv/work/it7q-private/` **only** | **Secondary**: project discovery | Older: still has NEXUS, no OPUS. **Read in place; never copied, quoted for figures or committed.** |
| `_source/v2/` + zip (May 2026) | repo | Look, copy, layout; v2 product list | NDA and forms are mock only, and the NDA fails open. v2 has **no per-division colours** (only navy/cyan/amber/green/purple/red tokens). |
| Jan 2026 spec transcript | `/srv/work/it7q-private/` | Multi-page structure, policy page drafts | Holds company financials. |
| Feb 2026 redesign transcript | `/srv/work/it7q-private/` | Feature list, home users first, Feb-era OPUS products | Holds investor projections. Its WordPress pivot is superseded. |

**Brand (April 2026 business card, decided Q37)**
- Master mark: **four interlocking circles**, cyan `#00B4CC`, lime `#7EC820`, purple `#8B5CF6`, orange `#F97316`, on dark navy **`#0D1B2A`**. The circle shapes are the four traced paths from the pack's IT7Q emblem (simplified by `tools/brand_mark.py` into `src/assets/img/brand/mark.svg`), coloured cyan (top-left), lime (top-right), purple (bottom-left) and orange (bottom-right).
- **No pack colours anywhere** (no `#0E1326` navy, gold, crimson or pack orange); `tools/check.py` fails if any appears in `src/` or `dist/`.
- Tagline: ***Smart tech. Simple terms. Serious security.***
- Fonts: Rajdhani (headings: Medium 500, SemiBold 600, Bold 700) and Exo 2 (body: variable weight, upright + italic), **self-hosted TTF** with each family's OFL licence beside it in `src/assets/fonts/` (Q40). Only the faces the CSS uses are shipped, and `tools/check.py` fails if a shipped font has no licence file next to it.
- Mission: *To make enterprise-grade technology accessible, affordable and understandable for homes, community organisations and small businesses across Queensland.*

**Division badges**: the same four circle shapes in the division colour (two tones, so the interlock still reads), with the Latin name and translation under each. MSP uses the master shapes too; there's no separate MSP artwork.

| Division | Badge translation | Card colour | Hex used | On navy | Page subtitle (descriptive) |
|---|---|---|---|---|---|
| MSP | Managed Services | blue | `#4F8EF7` (provisional) | 5.4 | Managed IT, plain English |
| OPUS | Works & Projects | orange | `#F97316` (master orange) | 6.2 | Software products |
| MENTIS | Mind & Intelligence | purple | `#8B5CF6` (master purple); text tint `#A98BFA` | 4.1 / 6.4 | AI & automation |
| TEMPESTAS | Storm & Hardware | cyan | `#00B4CC` (master cyan) | 7.0 | Cybersecurity hardware |
| PORTUS | Harbour & Gateway | lavender/violet | `#C4A7F5` (provisional) | 8.4 | Community safety |
| FABRICUS | Craft & Making | amber | `#F5B53D` (provisional) | 9.6 | Woodcraft & digital manufacturing |
| DOMUS | Home & Dwelling | green | `#3FBF5F` (provisional) | 7.3 | Smart home |

The card names a colour for each division, but only the four master colours came with hex values. I picked the four **provisional** ones to be clearly distinct from each other and from the master colours, all ≥ 4.5 contrast on navy. **Chris keeps them for now and fine-tunes from the preview later (Q41).** They live in one place: `src/assets/css/tokens.css`.

### 1b. Brand colour check (27 Oct) — resolved by Q37

Kept for the record. The packs used a different palette from the card; Chris chose the card. Pack shapes are used, pack colours aren't.

**Mismatches found**

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

**Contrast**: card master colours on navy are 4.1–8.4. Purple `#8B5CF6` (4.1) is used for shapes and large text only; small purple text uses the `#A98BFA` tint.

**Safety scan**: all 70 pack SVGs are clean (no `<script>`, `on*` handlers, `<foreignObject>`, external or `data:` references, DOCTYPE or entities). Each zip was extracted with path-traversal and symlink checks into its own scratch folder outside the repo. Only the derived, colourless `mark.svg` is committed. The zips stay git-ignored.

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
| 18 / 34 | **Public facts**: phone **0411 753 366**, ABN **43 922 878 001**, **Kallangur QLD 4503**, contact **info@it7q.com.au**. **Hero stats** (Chris, Q34): **"7 divisions"**, **"50+ projects"**, **"Australian owned & operated"**, **"Est. 2020"**. Any other stat is proposed for approval first, never published straight off (§2, "Proposed stats"). |
| 19 | **Enquiry form** → `website-enquiry` webhook, same protections as the NDA hooks, emails **chris@it7q.com.au** (sent from noreply@). |
| 20 | **Cloudflare Web Analytics** (cookieless). **No cookie banner.** |
| 21 / 43 | Stdlib-only Python build, **plus one pinned dependency: Pillow** (`requirements.txt`), used only to decode/encode JPEG and WebP for the watermark step. PNG stays pure stdlib, and so does `tools/check.py` (§5.1). |
| 22 / 37 | **Brand = business card.** Circle shapes from the `_brand/` emblem, recoloured; no pack colours anywhere. No MSP pack exists; MSP uses the master shapes. The hero logo is an **animated SVG**. |
| 23 | Gated text at feature level only (§4.9). |
| 24 | Every project placed (§2.1). |
| 25 | TEMPESTAS tiers T1 Scout → T5 Citadel; prices/specs gated; SCUTUM = MSP antivirus only. |
| 26 | **FABRICUS**: launch with names/one-liners + **photo placeholders**. Real photos arrive the week of 2 Nov 2026. |
| 27 / 33 | **Portfolio**: p1–p7 are archives, each a **static snapshot on its own Pages project**: noindex, forms disabled with a short "portfolio copy" note, and a small "Portfolio snapshot built by IT7Q" banner. WordPress sites to export: **True Colours (p1), Redbird Studio (p2), The Artist Apron (p4), Aussie Pathtag Club (p7)**. **p8 = Niuleaf**, linking straight to `https://niuleaf.au` (no snapshot). **p9 = Pro Energy Solutions**, reserved and unpublished until Chris says it's live. p8 and p9 are the **only current clients**; p1–p7 are past clients (Q42). Old `tc/rb/pr/aa` names **redirect** to `pN`. Steps in §6.3; no DNS changes yet. |
| 28 | **SCUTUM's "from" price is public.** Every other product/hardware price is gated. |
| 29 | **p6 = "BlueVibes Music"**, **p7 = "Aussie Pathtag Club"**. One-liners in §2.2. |
| 31 | **FABRICUS register**: F-001–F-035 from the July 2026 plan-sheet handover. I write the public one-liners. F-016 is the TABULAE medal board. Shop-use jigs and tools are excluded (not retail). |
| 32 | Requests that never become an NDA (pending too long, or rejected) are kept **12 months**. |
| 35 / 38 | **Statuses**: every FABRICUS item is public with status **In development**. F-031 is a separate product from F-020; nothing is held back. Every former TBC project shows **In development** (table in §2.1 for Chris to correct later). |
| 36 | **NDA**: confidentiality **survives** the 3-year term: indefinitely for trade secrets, otherwise for a set period after it ends. Still needs a legal check before launch. |
| 39 | Chris checks the FABRICUS one-liners in the preview. (They first appear on the FABRICUS page in Phase 2.) |
| 40 | **Fonts**: TTF files plus their OFL licence files, supplied by Chris (28 Oct) and now in `src/assets/fonts/`. |
| 41 | **Division colours**: keep the provisional picks for now; Chris fine-tunes them from the preview later. |
| 42 | **Portfolio** details and one-liners (§2.2). p2 is **Redbird Studio** (was "Red Bird"). Niuleaf's one-liner stays a placeholder for Chris to supply. |
| 43 | **Pillow** allowed as one pinned build dependency so photos can be JPEG/WebP. The watermark step and its check work for all three formats (§5.1). |
| 47 | **Version pin is enough for now.** Full hash pinning (`--require-hashes`) at launch; Chris generates the hashes on his Mac. |
| — | **Watermark**: every raster image on the site (photos, thumbnails, portfolio screenshots) gets a subtle master-mark watermark, applied by `tools/build.py`. Sources stay unwatermarked outside `dist/`; `tools/check.py` fails on any unmarked image (§5.1). |
| — | **Coming soon (MSP)**: "AI-powered security hardening for your small business and home". A card on the MSP page plus a teaser on Home. Public wording follows §4.9 (no WireGuard, tunnels, Agent Smith or internal tooling). |
| — | **Testimonials** (28 Oct): a Home section driven by `src/data/testimonials.json`, consent recorded per entry, shown only when there are approved entries (§2.3). Chris fills in the real quotes; I never write any. |
| — | **T3 Guard images** come from earlier marketing renders (Chris). Placeholder until then. |
| 48 / 51 | **About page approved** (29 Oct). Chris's paragraph (founded 2020 by Chris Lord, Kallangur, four kids, diploma in IT Systems Administration) replaces the placeholder **word for word** (Q51). |
| — | **Staff link** (29 Oct): one small "Staff" link in the footer only, pointing to a single URL that will sit behind Cloudflare Access. URL: **`https://staff.it7q.com.au`** (Q52), behind Cloudflare Access, set up by Chris at launch. The link text is just "Staff": no internal hostnames, service names or tool names anywhere on the public site. |
| — | **MERCATOR** (29 Oct): **not a new division**; IT7Q stays at seven (the "7" in the name). MERCATOR is MSP's **"Parts, Sales & Service"** section: a featured **Coming soon** card on the MSP page (P-MSP-07) and a **Shop** page in the main nav. Store: `shop.it7q.com.au` (separate build, §2.6). Launch categories: Networking, Office Peripherals, Storage Solutions, plus **"Supply + Install"** bundles. **No supplier names, prices or margins.** |
| — | **Resources** (29 Oct): recommended FOSS software (15 entries) + the **Guides** section (IT7Q Client Education Series + device-hardening manuals). Download buttons go to each project's **official** download page; IT7Q never hosts binaries (§2.4). |
| — | **Media** (IT7Q's own self-hosted video channel + podcast) and **News** (**HERALD**, IT7Q's own tech-news and updates feed): **Coming soon** placeholder pages only (§2.6). |
| — | **Credentials** page: Chris's qualifications and certifications, from a list he supplies; **no individual unit details** (Q53). |
| 61 | **About overlap** (29 Oct): drop the two older About lines that repeat "started in 2020 in Kallangur" and "seven divisions". Chris's paragraph stands alone; the **Credentials** link stays. |
| 54 | **Footer social links** (29 Oct), shown in this order with these URLs:<br>Instagram `https://www.instagram.com/it7q_qld/` · X `https://x.com/it7qqld` · YouTube `https://www.youtube.com/@IT7Q-KITS` · LinkedIn `https://www.linkedin.com/in/chris-lord-b53731102/` (labelled **"Chris's LinkedIn"**; an IT7Q company page comes later) · Facebook `https://www.facebook.com/InfiniteQld`.<br>**Google Business**: hidden until Chris sends the profile share link. **No Reddit or Etsy.** TikTok wasn't in the list: hidden until Chris confirms (Q62). Plus the WhatsApp button. |
| — | **Athena Browser Customer Edition**: a **Coming soon** download page. |
| — | **PORTUS public wording**: presented as a **community safety tool**. Any domestic-violence use case is **gated detail only**, so the public card never puts a user at risk (§2.5). |

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
/portfolio/               Client websites: p1–p7 past clients (snapshots) + p8 Niuleaf (current); p9 reserved
/services/                "How we can help": plain-English services + enquiry form
/shop/                    MERCATOR (MSP Parts, Sales & Service): Coming soon        [main nav]
/resources/               Recommended FOSS software + Guides (§2.4)               [main nav]
/resources/guides/<slug>/ One guide: view in browser + PDF download
/media/                   Video channel + podcast: Coming soon                     [footer]
/news/                    HERALD tech news and updates: Coming soon                [footer]
/credentials/             Chris's qualifications and certifications              [footer + About]
/athena/                  Athena Browser Customer Edition download: Coming soon     [OPUS card + footer]
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
  1. Hero: the **animated master logo** (inline SVG, CSS animation of the four circles; static under `prefers-reduced-motion`) + tagline + the four **hero stats**: 7 divisions · 50+ projects · Australian owned & operated · Est. 2020 (Q34).
  2. **Badge row**: seven division badges in business-card style, each in its colour, with the Latin name and translation under it (MSP Managed Services · OPUS Works & Projects · MENTIS Mind & Intelligence · TEMPESTAS Storm & Hardware · PORTUS Harbour & Gateway · FABRICUS Craft & Making · DOMUS Home & Dwelling). Each badge links to its division page.
  3. **Coming-soon teaser**: "AI-powered security hardening for your small business and home", linking to the MSP page.
  4. Then mission, a "how we help" strip (home → small business), a T3 Guard feature, a portfolio highlight, **testimonials** (only when approved entries exist, §2.3), an investor/partner call to action to `/access/`, and contact.

**Proposed stats (for Chris's approval; not published)**. Each is verifiable from the sources and true today:

| Stat | Source |
|---|---|
| "8 client websites built" | Portfolio p1–p8 (p9 not live yet) |
| "35 handmade product designs" | FABRICUS register F-001–F-035 |
| "5 security appliance tiers" | TEMPESTAS T1–T5 (Q25) |
| "21 AI agents in our back office" | Build pack's public Persephone teaser ("21 specialised agents") |
| "Based in Kallangur, QLD" | Q18 public facts |
- **Division pages**: one template. Header = the division badge + descriptive subtitle (§1). Cards come from `src/data/projects.json` via `tools/build.py`. Gated detail is **not** in that file. Each card: image placeholder, status badge (*Developed · In development · In design · Documented · Coming soon*), name, one-liner, "Why it's unique" (or "Who it's for" on TEMPESTAS tiers), and a "Full details under NDA" line linking to `/access/`. Featured cards (T3 Guard, the coming-soon MSP service) sit first and span the grid.
- **MENTIS page** also carries a plain-English **"AI automations we can set up"** services list (from v2: patch management, social media pipeline, invoice/phone-system automation, email triage, security alerting, compliance reporting). It's a list, not cards (Q24).
- **Services**: plain-English public services for homes and small business, from `src/data/services.json`, each linking to its division. How IT7Q delivers them internally (tooling, stack) is gated (Q15). Until the enquiry form arrives (Phase 3, with service and division selectors), the page points to phone and email.
- **Contact / footer**: phone 0411 753 366, info@it7q.com.au, ABN 43 922 878 001, Kallangur QLD 4503. The Contact page also links WhatsApp at `wa.me/61411753366` (assumes WhatsApp is on the mobile number; Q49) and carries the enquiry form. Messenger is left off until Chris gives the page link (Q49).
- **About**: story (Est. 2020, Kallangur, Australian owned & operated), mission, four values (from v2), photo placeholders IMG-29/IMG-30, and a visible placeholder for a few lines from Chris (Q48).
- **Legal**: Privacy and Terms are plain-English drafts that state the §4.10 retention periods, no cookies, cookieless analytics, Turnstile and `sessionStorage`. The NDA page shows `src/legal/nda-1.0.md` with its version and SHA-256. All three carry a "Draft, being checked by a lawyer" note (Q36).
- **Portfolio**: §2.2.
- **Main nav** (v10): Home · Divisions · Services · Shop · Portfolio · Resources · About · Contact. Chris asked for Shop; I've added Resources too, since it's the biggest new page. Media, News, Credentials and Athena sit in the footer. Chris checks the order in the preview.
- **Footer** (v10, URLs v12): contact facts, then a **social row** (Instagram, X, YouTube, Chris's LinkedIn, Facebook; Google Business once its link arrives; see §1a Q54; as plain text-labelled links with `rel="noopener"`; no third-party scripts, embeds or widgets, so the CSP stays as is), the **WhatsApp button** (`wa.me/61411753366`, Q49), the footer page links, and a small **"Staff"** link. Social URLs live in `site.json`; an entry with no URL yet isn't rendered (so no dead links ship), and the launch check fails if any is still empty. v12: an entry can be marked `"hidden": true` (Google Business until its link arrives; TikTok until Q62), which the launch check accepts as a deliberate choice rather than a gap.
- **Shop / MERCATOR**: "Coming soon": IT7Q's hardware store (`shop.it7q.com.au`, shown as text, not linked until it's live). Three launch categories (Networking, Office Peripherals, Storage Solutions) as simple tiles, and a "Supply + Install" panel: *we sell the gear and install it*. CTA: the enquiry form with service "Parts, sales & service". No supplier names, prices or margins (the price guard already fails on any `$`).
- **Media**: "Coming soon": IT7Q's own video channel and podcast, self-hosted. Placeholder only; no YouTube or podcast embeds.
- **News**: "Coming soon": **HERALD**, IT7Q's own tech-news and updates feed. Placeholder only.
- **Credentials**: a list from `src/data/credentials.json` (title, issuer, year; optional "in progress"). Whole qualifications and certifications only, **no individual units**. Placeholder entries until Chris's list arrives (Q53, later). Linked from About and the footer.
- **Athena CE**: "Coming soon": Athena Browser Customer Edition. No download button until there's a signed build and a hosting decision (Q56, later). The OPUS Athena card links here.
- **Parked**: client portal dashboard, admin portal login, Neo evaluation workflow, WordPress (§9).

### 2.1 Project inventory (public card list)

Names and statuses come from the build pack unless marked otherwise. Each card gets an image ID `P-<div>-<nn>` (§5). Status values: *Developed · In development · In design · Documented · Coming soon*.

The card text (one-liner + "why it's unique") lives in `src/data/projects.json`. It's written from the build pack's **public teasers** (and v2 for products the pack doesn't cover), in plain English, with no tooling, ports, prices or specs. The TEMPESTAS "who it's for" lines and the one-liners for COLLOQUIUM, the PORTUS apps and the three FABRICUS services are **my drafts**, since the sources say little. Chris checks them all in the Phase 2 preview (Q45).

**Set to "In development" by default (Q35), for Chris to correct later**

| ID | Project | Status now | Correct to |
|---|---|---|---|
| P-MSP-05 | IT7Q SysMon | In development | |
| P-OPUS-10 | Andromeda CE / AI companion | In development | |
| P-OPUS-11 | Aegir — SecureStart | In development | |
| P-MEN-04 | FORTUNA | In development | |
| P-MEN-05 | COLLOQUIUM | In development | |
| P-POR-02 | PORTUS App | In development | |
| P-POR-03 | PORTUS Jnr | In development | |
| P-FAB-101 | FABRICUS App | In development | |
| P-FAB-102 | FORMAE | In development | |
| P-FAB-103 | BIONICUS | In development | |

**MSP — Managed Services**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MSP-01 | SCUTUM — managed antivirus/EDR. **Public "from" price shown** (Q28) | In development | build pack |
| P-MSP-02 | MSP Companion App (one-click enrolment) | In development (pilot) | build pack |
| P-MSP-03 | Managed security monitoring | Developed | build pack |
| P-MSP-04 | IT7Q Support Portal | In development | build pack, v2 |
| P-MSP-05 | IT7Q SysMon (server health monitoring) | In development | v2 |
| P-MSP-06 | **AI-powered security hardening for your small business and home** (featured on Home) | **Coming soon** | Chris (27 Oct) |
| P-MSP-07 | **MERCATOR — Parts, Sales & Service** (featured, links to `/shop/`): IT7Q's hardware store for networking, office peripherals and storage, with Supply + Install bundles | **Coming soon** | Chris (29 Oct) |

MERCATOR is a section **of MSP**, not a division. Its badge uses the MSP colour and master shapes; no new division colour, page or badge-row entry. It has no "Full details under NDA" line.

P-MSP-06 public wording is plain English only: what it does for the customer (finds and fixes weak security settings, with AI help). It never names tooling, agents, tunnels or WireGuard (§4.9). `tools/check.py` enforces this on all of `dist/` (§3, public-wording guard).

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
| P-OPUS-10 | Andromeda CE / Andromeda AI companion | In development | v2, Feb notes |
| P-OPUS-11 | Aegir — SecureStart (Windows privacy/setup tool) | In development | v2 |

**MENTIS — Mind & Intelligence (AI & automation)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-MEN-01 | Project Persephone (AI agent workforce). Its named agents appear **only in Persephone's gated detail**, with no cards of their own | Developed (partly live) | build pack, v2 |
| P-MEN-02 | MNEMOSYNE (AI memory layer) | In development | build pack |
| P-MEN-03 | Neo (AI website builder) | In development | build pack |
| P-MEN-04 | FORTUNA (investment-monitoring agent). Own card, labelled **"Part of Persephone"** | In development | build pack, v2 |
| P-MEN-05 | COLLOQUIUM (business chat/AI assistant service) | In development | Feb notes |
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
| P-POR-02 | PORTUS App | In development | v2 |
| P-POR-03 | PORTUS Jnr (child-safe version) | In development | v2 |

**PORTUS wording (29 Oct)**: every public line presents PORTUS as a **community safety tool** (neighbours, verified safe places, calling for help fast). Any domestic-violence use case lives **only in gated detail** (§4.9), so someone glancing at a phone or browser history sees nothing that puts a user at risk. The current public lines already fit; v10 adds a guard (§3) so they stay that way.

**FABRICUS — Craft & Making (woodcraft & digital manufacturing)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-FAB-101 | FABRICUS App (offline order/catalogue PWA) | In development | Feb notes |
| P-FAB-102 | FORMAE custom 3D prints | In development | Feb notes |
| P-FAB-103 | BIONICUS assistive body supports (Project Bionic) | In development | Feb notes |

**FABRICUS product range** (Q31). Source: July 2026 plan-sheet handover. Card ID = `P-FAB-` + the F-number (e.g. F-007 → `P-FAB-007`). **All public, all "In development"** (Q38). Photo placeholders until the real photos arrive (week of 2 Nov). Public one-liners are mine, in plain English; Chris checks them in the Phase 1 preview (Q39).

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
| F-020 | Stepped bedside table with asymmetric hutch | A bedside table with stepped levels and an off-centre hutch for books and bits. | |
| F-021 | House-shaped wall key holders (3 variants) | Little house-shaped key holders for the wall, in three styles. | |
| F-022 | Illuminated shadow-box frame planters | Shadow-box frames that double as planters, with built-in lighting. | |
| F-023 | Serving trays (standard & elevated) | Timber serving trays, flat or raised, for entertaining. | |
| F-024 | Cap display rack | A wall rack that shows off a cap collection neatly. | |
| F-025 | LED wall clock with shelf | A wall clock with LED lighting and a small display shelf. | |
| F-026 | Honeycomb hex shelf | Hexagon shelves that fit together in a honeycomb on the wall. | |
| F-027 | Kids' tree bookshelf | A tree-shaped bookshelf that makes kids' books part of the room. | |
| F-028 | Diagonal mug shelf | A diagonal wall shelf that shows off a mug collection. | |
| F-029 | Live-edge wine rack | A wine rack cut from live-edge timber, so each piece is one of a kind. | |
| F-030 | Bedside valet / dock | A bedside tidy for your phone, watch, wallet and keys. | |
| F-031 | Nightstand with hutch | A nightstand with a hutch on top for a lamp, books and the alarm clock. | Separate product from F-020 (Q38) |
| F-032 | Standing bird table | A free-standing bird table for the backyard. | |
| F-033 | Asymmetric geometric wall shelf | A geometric wall shelf with an off-beat, modern shape. | |
| F-034 | Arched slat-panel shelf | An arched shelf with a slatted back panel, for display or storage. | |
| F-035 | Guitar stand & media station | A stand for your guitar with room for the amp, music and gear. | |

Shared "why it's unique" for the range (from the build pack): *bespoke, maker's-marked, made in-house on IT7Q's own CNC and 3D printer.* TABULAE is no longer a separate project name in the inventory; it's F-016.

**DOMUS — Home & Dwelling (smart home)**
| ID | Project | Status | Source |
|---|---|---|---|
| P-DOM-01 | Smart, segmented, private home setup | Documented / service | build pack, business plan |

**Totals**: MSP 7 · OPUS 11 · MENTIS 5 · TEMPESTAS 6 · PORTUS 3 · FABRICUS 38 (35 range + 3) · DOMUS 1 = **71 cards**, all public. The hero stats ("7 divisions", "50+ projects") are unchanged.

Retired, so no card: original single-tenant Calendi for Pine Rivers RSL, and the NEXUS division (3CX/NBN), replaced by OPUS.

### 2.2 Portfolio

Consent is on file for **all** IT7Q-built sites.

| Label | Client | Link | Old name (redirects) | Repo (Chris's GitHub) |
|---|---|---|---|---|
| p1 | True Colours DSS | `p1.it7q.com.au` | `tc.it7q.com.au` | `TCDSS_Website` |
| p2 | Redbird Studio | `p2.it7q.com.au` | `rb.it7q.com.au` | — |
| p3 | Pine Rivers RSL Sub Branch | `p3.it7q.com.au` | `pr.it7q.com.au` | `PRRSL_Website` |
| p4 | The Artist Apron | `p4.it7q.com.au` | `aa.it7q.com.au` | — |
| p5 | Burpengary Jets | `p5.it7q.com.au` | — | — |
| p6 | BlueVibes Music | `p6.it7q.com.au` | — | `BlueVibes_Website` |
| p7 | Aussie Pathtag Club | `p7.it7q.com.au` | — | `AustPathClub` |
| p8 | Niuleaf | **`https://niuleaf.au`** (Q42) | — | — |
| p9 | Pro Energy Solutions | live domain when launched | — | — |

| Label | Client type | Source today | Snapshot | Card one-liner (from Chris's notes, Q42) |
|---|---|---|---|---|
| p1 | Past client (archive) | WordPress | export → static | A website for True Colours DSS, an NDIS-approved provider of support services. |
| p2 | Past client (archive) | WordPress | export → static | A website for Redbird Studio, which runs art classes. |
| p3 | Past client (archive) | static | copy → snapshot | The website for the Pine Rivers RSL Sub Branch. |
| p4 | Past client (archive) | WordPress | export → static | A website for The Artist Apron, which runs art classes. |
| p5 | Past client (archive) | static | copy → snapshot | A website for the Burpengary Jets rugby league club. |
| p6 | Past client (archive) | static | copy → snapshot | A website for BlueVibes Music. |
| p7 | Past client (archive) | WordPress | export → static | A website where pathtag collectors buy, sell and trade. |
| p8 | **Current client** | live site (a "coming soon" home page today) | **none**: links straight to `https://niuleaf.au` | **Placeholder** until Chris supplies it. Card status: **Coming soon**. |
| p9 | **Current client, reserved** | coming-soon page still to be built | none | `published: false` until Chris says it's live |

p6 has no description yet beyond the name, so its one-liner is just "A website for BlueVibes Music" (Q46).

Each card shows the client name, a client-type label (*Past client* or *Current client*), a thumbnail, the one-liner and a link. Past-client cards link to their `pN` snapshot, which doesn't exist yet. Until a snapshot is live (`snapshot_live: true` in `portfolio.json`), the card says "Snapshot coming soon" and has no link. The `published` flag stays, and `tools/check.py` fails if an unpublished entry (p9 today) appears in `dist/`. Hosting steps: §6.3.

### 2.3 Testimonials (28 Oct)

Chris has real testimonials. They live in `src/data/testimonials.json`:

```json
{
  "entries": [
    {
      "quote": "The client's exact words, unedited",
      "name": "First name or full name (optional if business is given)",
      "business": "Business or organisation (optional if name is given)",
      "consent": {"recorded": "2026-10-28", "method": "email", "note": "where the consent record is kept"},
      "approved": true
    }
  ]
}
```

- **Rendering**: the Home section shows only entries with `approved: true`. With none, the whole section, heading included, is left out.
- **Consent guard** (`tools/check.py`): fails if **any** entry, approved or not, lacks `consent.recorded` (a real date, not in the future) or `consent.method` (`email`, `written`, `form` or `sms`). It also fails if an entry has no quote, has neither a name nor a business, or if an unapproved quote appears in `dist/`.
- **Rules**: I never write or paraphrase a testimonial. The repo ships with an empty `entries` list and an `_example` block showing the shape. Any key starting with `_` is ignored.

### 2.4 Resources and Guides (29 Oct)

**Recommended software** (`src/data/resources.json`). Each entry: name, **what it is**, **why use it** (plain English, my drafts for Chris to check), a link to the matching IT7Q guide (where one exists), and a **Download** button to the project's **official** download page. **IT7Q never hosts binaries**: no `.exe`, `.msi`, `.dmg`, `.apk`, `.zip` etc. in `dist/`, and the buttons go only to official sites.

| Software | Official download page (I check each before the build) | Guide |
|---|---|---|
| Bitwarden | `bitwarden.com/download/` | ch. 1 |
| LibreOffice | `libreoffice.org/download/` | ch. 3 |
| OnlyOffice | `onlyoffice.com` (desktop editors download) | ch. 3 |
| Thunderbird | `thunderbird.net` | ch. 8 |
| GIMP | `gimp.org/downloads/` | ch. 8 |
| Krita | `krita.org` (download page) | ch. 8 |
| Inkscape | `inkscape.org/release/` | ch. 8 |
| darktable | `darktable.org/install/` | ch. 8 |
| Joplin | `joplinapp.org` (download page) | ch. 8 |
| 7-Zip | `7-zip.org/download.html` | ch. 8 |
| Nextcloud | `nextcloud.com/install/` | ch. 4 |
| ClamAV | `clamav.net/downloads` | ch. 5 |
| Pi-hole | `docs.pi-hole.net` (install page) | ch. 6 |
| WireGuard | `wireguard.com/install/` | ch. 7 |
| Jitsi | `jitsi.org/downloads/` | ch. 8 |

- **Download-link guard** (`tools/check.py`): every Download URL must be `https://` and on that entry's allow-listed official domain (kept in `resources.json`), and no binary/archive file may appear in `dist/`. Download links open with `rel="noopener noreferrer"`.
- Pi-hole's official quick install pipes a script into a shell. The guide shows the "download, read, then run" method instead.
- **ClamAV / WireGuard (Q55, decided)**: the public-wording guard (§3) still bans both names on every public page **except** `/resources/` and the guide pages (incl. guide PDFs), where they appear only as general recommendations for the reader. There, any sentence naming them that also says "we use", "we run", "our setup/servers/network" or similar fails the check. Everything else (division pages, Services, Shop, the MSP hardening card) stays blocked.

**Guides** (`src/data/guides.json`), on the Resources page. Each guide: **view in browser** + **PDF download**. Chris supplies the files; placeholders until then.

*IT7Q Client Education Series* (11 chapters):
1. Bitwarden
2. Windows backup & recovery
3. LibreOffice vs Microsoft Office
4. Private cloud storage
5. ClamAV
6. Pi-hole
7. WireGuard
8. More FOSS tools
9. Why FOSS
10. Windows 11 editions
11. Windows 11 privacy & security

*Device hardening & setup manuals* (Q57), one guide each: **Windows**, **Chromebook**, **Android**, **iPhone/iPad**, **macOS**, **Ubuntu**, plus three cross-platform guides: **Family & Multi-User**, **Security Hardening Checklist**, **Ongoing Maintenance**. Windows and Android are written (Chris supplies the files); the rest are placeholders.

- **View in browser**: if Chris supplies HTML or Markdown, each guide gets its own page (`/resources/guides/<slug>/`), built like the legal pages, so it's accessible and searchable. If he supplies only PDFs, "View" opens the PDF in the browser's own viewer. No embedded PDF viewer, so the CSP doesn't change.
- **PDFs** are served from `/resources/guides/pdf/`. Before they ship, `tools/check.py` scans each PDF for metadata (author, file paths, creator tool) and for the banned infrastructure words (§4.9), and fails if it finds any. Chris exports with metadata stripped.

### 2.5 PORTUS discretion guard

`tools/check.py` fails if any public file (`src/`, `dist/`) mentions domestic or family violence, abuse, refuges, escaping or similar wording near "PORTUS". Those words are allowed only in `gated/portus.json`. The public card, page title, meta description and image alt text all stay on "community safety".

### 2.6 Website pages now vs separate future builds

| Item | On this site at launch | Separate future project (not part of this site's launch) |
|---|---|---|
| MERCATOR | MSP featured card + `/shop/` Coming soon page | **The store itself** at `shop.it7q.com.au`: catalogue, cart, payments, stock |
| Media | `/media/` Coming soon page | **Self-hosted video and podcast hosting** |
| HERALD | `/news/` Coming soon page | **The HERALD app/feed** (publishing, RSS, archive) |
| Athena CE | `/athena/` Coming soon page | Signed builds, a hosting decision, update channel (Q56) |
| Resources | Full page: 15 software entries | — |
| Guides | Section + guide pages; placeholders until Chris's files arrive | — |
| Credentials | Full page; placeholders until Chris's list arrives | — |
| Staff link | Footer link to one URL | The Cloudflare Access app behind it (Chris) |
| Social links | Footer row; empty ones hidden | — |

The separate projects get their own plans and repos. Nothing on this site depends on them, and their "Coming soon" pages link nowhere until each one is live.

---

## 3. Reuse from v2 vs rebuild

| Area | Decision | Notes |
|---|---|---|
| Colours, fonts, logo | **Replace** with the business-card brand; circle shapes from `_brand/` | Self-host Rajdhani + Exo 2 (TTF + OFL), no Google Fonts. |
| Hero copy, tagline | **Reuse, re-case** | Card's sentence-case tagline + build pack mission + Chris's four stats (Q34). |
| Division card / portfolio card design, nav, scroll animations | **Reuse, refactor** | `addEventListener` instead of inline `onclick` (strict CSP). Respect `prefers-reduced-motion`. |
| v2 product list | **Mine for names only** | Folded into §2.1. v2 automations become the MENTIS services list. |
| NDA legal text | **Rewrite** | One-way, 3-year draft in `docs/nda-draft.md` (Q10). |
| Cookie banner | **Drop** | No cookies; cookieless analytics (Q20). |
| NDA modal, contact form, `alert()` validation, emoji icons, modal a11y | **Rebuild** | |
| Jan spec portal dashboard | **Drop** | Advertises internal hostnames. |

**Repo layout**
```
src/                 page sources + partials
  pages/             one .html per route (front matter + body)
  partials/          layout, header, footer, sprite
  data/site.json     public facts, hero stats, nav
  data/divisions.json  seven divisions: Latin name, translation, colour token, subtitle
  data/projects.json public card data only (no gated detail)
  data/portfolio.json  p1–p9, published flag, snapshot_live flag
  data/services.json   public services list
  data/testimonials.json  quotes + recorded consent (§2.3)
  data/resources.json  FOSS entries + official download domains (§2.4)
  data/guides.json     Education Series chapters + hardening manuals (§2.4)
  data/credentials.json  Chris's qualifications/certifications, no units (§2)
  templates/guide.html  one page per guide (§2.4)
src/guides/          <slug>.md (browser view) + <slug>.pdf (download), from Chris; PDFs ship to /resources/guides/pdf/
  assets/css|js|fonts|img
  assets/img/brand/mark.svg  four circle shapes, derived from the pack emblem, no colours
  _headers           security headers for Pages
tools/build.py       stdlib-only Python: partials + data → dist/ (Q21), watermarks rasters
tools/pngmark.py     stdlib PNG decode/encode + mark compositing + marker verification (§5.1)
tools/rastermark.py  JPEG/WebP watermarking via Pillow; stdlib marker embed/verify for all formats
requirements.txt     Pillow, pinned (the build's only dependency, Q43)
tools/brand_mark.py  one-off: pack emblem SVG → simplified mark.svg
tools/check.py       links, HTML sanity, gated-content leak check, infrastructure guard on gated/,
                     unpublished-portfolio check, financial-figure guard, price guard, SVG check,
                     watermark check, pack-colour guard, public-wording guard, consent guard,
                     font licence guard, config guard, JS-sink guard, form-label guard
tools/preview.py     local preview: serves dist/ with the Pages headers + mock webhooks (§4.12)
src/legal/nda-1.0.md the NDA text the site shows and fingerprints (reviewer notes stay in docs/)
src/data/forms.json  the three forms' fields: renders the HTML, drives the mock, spec for n8n
src/data/endpoints.json  public webhook origin + Turnstile site key
tools/tests/         unit tests for the build tools (python3 -m unittest)
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
- **Watermark check** (§5.1): every raster in `dist/` must be a PNG, JPEG or WebP carrying a valid IT7Q watermark marker. Anything else fails.
- **Consent guard** (§2.3): every testimonial needs recorded consent.
- **Font licence guard** (Q40): every shipped font needs its family's OFL file beside it.
- **Pack-colour guard** (Q37): none of the pack hex values may appear in `src/` or `dist/`.
- **Public-wording guard** (§4.9): `dist/` must not mention WireGuard, `wg0`, tunnels, cloudflared, Agent Smith, Wazuh, Velociraptor, ClamAV, n8n or internal hostnames (`*.nubius.com.au`). The webhook origin is allowed only in `_headers` and the JS config once Phase 3 adds it. v10: ClamAV and WireGuard allowed only under `/resources/` (Q55, §2.4). **v11 (Q58)**: the webhook base is one value, `hooks` in `src/data/endpoints.json`; the build writes it into `config.js` and the CSP in `_headers`, and the check allows that exact value only there. Once Chris switches it to `https://forms.it7q.com.au/webhook` (Phase 6), `nubius` is no longer allowed anywhere in `dist/`, `_headers` included.
- **Download-link guard** (v10, §2.4): Download buttons only to allow-listed official domains over HTTPS; no binaries or archives in `dist/`.
- **Guide PDF guard** (v10, §2.4): no metadata and no banned words in shipped PDFs.
- **PORTUS discretion guard** (v10, §2.5).
- **Footer guard** (v10): exactly one "Staff" link, in the footer only, never in the nav or sitemap; its URL must be `https://` and not an internal hostname.

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
5. 401 → clear the token and re-lock ("your session has ended"). 403 → re-lock that page only and keep the session, since a viewer without Investors access is still approved for the divisions. Network/5xx/bad JSON/wrong division → stay locked, with "try again". No cached fallback.
6. `{action:"logout"}` deletes the session server-side.

Honest limits: an approved viewer can still copy or screenshot. The NDA, watermark, audit log and revocation are the controls for that.

### 4.12 Front-end contract and local mock (Phase 3)

The browser side is built and tested against `tools/preview.py`, which plays the five webhooks. The Phase 4 n8n workflows must reply the same way.

| Hook | Request (JSON, ≤ 8 KB) | Replies |
|---|---|---|
| `nda-submission` | `forms.json` → `nda_request` fields + `nda_version`, `nda_sha256` | `202` (also for bots and duplicates: no enumeration), `400` invalid, `429` |
| `nda-login` | `email`, `password` | `200 {token, email, expires_at (ISO UTC), investor}`, one `401` for every failure, `429` after 5 fails in 15 min |
| `nda-content` | `{token, division}` (seven slugs or `investors`) or `{token, action:"logout"}` | `200 {division, viewer, projects: {ID: {summary, sections:[{heading, items[], paragraphs[]}]}}}`; investors: `{division, viewer, sections}`; `401` session, `403` scope |
| `website-enquiry` | `forms.json` → `enquiry` fields | `202`, `400`, `429` |

- **Every form also sends** `turnstile`, `website` (honeypot, must be empty) and `elapsed_ms`. Honeypot filled or under 3 s means a neutral `202`, with nothing stored or emailed. The signature must match the name (case and spacing ignored).
- **Config**: `tools/build.py` writes `assets/js/config.js` (webhook origin, Turnstile site key, NDA version + hash). It's the **only** file in `dist/` allowed to name the webhook origin. `--mock` builds point at `/webhook` on the preview server, and `tools/check.py` refuses a mock build unless it's told it's one, so a mock build can't be deployed by accident.
- **Turnstile**: loaded only on pages with forms. With no site key (as now, until Phase 6) the forms **fail closed**: they say the check couldn't load and send nothing.
- **Mock scenarios** (switch at `/__mock/scenario/<name>`): `normal`, `down`, `slow`, `rate-limited`, `content-500`, `content-bad-json`, `content-wrong-division`, `session-expired`, `forbidden`, `login-refused`. Mock logins are listed at the top of `tools/preview.py`. All their data is fake.
- **No JS runtime on Pantheon**, so the browser code is checked by guards (no `innerHTML`/`eval`, every field labelled), by tests of the mock and the page↔mock contract, and by Chris's browser walk-through (§7.1).

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

**Retention vs NDA survival (Q36, for the legal check)**: confidentiality now survives 2 years past the 3-year term, and indefinitely for trade secrets. The acceptance record is kept for term + 2 years, which covers the general survival period but not trade secrets, and not a claim brought later within Queensland's 6-year contract limitation period. The lawyer should say whether to keep a minimal acceptance record (name, email, version, hash, date; no IP) for longer.

### 4.11 Chris's server-side setup (documented in `deploy/`, not done by me)
- Mailboxes: **`noreply@it7q.com.au`** (MXRoute, sending only) and **`info@it7q.com.au`**. SPF/DKIM/DMARC for `it7q.com.au` must cover MXRoute.
- n8n credentials, referenced by name only: `IT7Q Edge Header`, `Turnstile secret`, `Postgres it7q_web`, `Mail sender (noreply@)`.
- n8n env var `NODE_FUNCTION_ALLOW_BUILTIN=crypto` (compose change under `/opt/it7q`).
- Postgres `it7q_web` DB + role, then run the SQL.
- Cloudflare: Transform Rule, cache bypass, rate-limit rule, Turnstile widget, **Access on `nda-review`**, Web Analytics on the Pages project.

---

## 5. Image and media list

Every image starts as a visible placeholder (`PLACEHOLDER <ID> — description (w×h)`, `role="img"` + matching `aria-label`), drawn in HTML/CSS so it isn't a raster. **Public images must not reveal gated detail**: no schematics, board close-ups, admin screens or architecture diagrams.

### 5.1 Watermark (build time)

- **What**: the business-card master mark (four circles), bottom-right, about 12% of the image width (48–160 px), ~30% opacity, with a margin. No text.
- **Where**: every raster image that ends up in `dist/`: photos, thumbnails, product shots, portfolio screenshots. SVG artwork (logo, badges) isn't watermarked.
- **How**: `tools/build.py` reads the clean source from `src/assets/img/`, composites the mark and writes the result to `dist/` only. Sources are never changed. The compositing code is the same for every format (`tools/pngmark.py`). Only decoding/encoding differs:
  - **PNG**: pure stdlib. If a PNG is interlaced or 16-bit, the build uses Pillow to decode it when Pillow is installed; otherwise it fails.
  - **JPEG and WebP**: Pillow decodes, the stdlib code composites, Pillow re-encodes (JPEG quality 82 progressive, WebP quality 80). On the way the build applies the camera's rotation, converts the colour profile to sRGB, scales anything wider than 1600 px down to 1600 px, and **drops all metadata (EXIF, including GPS location)**.
  - If Pillow isn't installed and a JPEG/WebP source exists, the build fails with a message saying how to install it. A build with only PNGs (or no rasters, as now) doesn't need Pillow.
- **Not covering the subject**: bottom-right by default. If the subject sits there, `src/data/images.json` can move the mark for that image (`"corner": "bl" | "tr" | "tl"`). Chris checks placement in the preview.
- **Proof**: every output carries an `IT7Q-Watermark v1 sha256=… corner=…` marker. In a PNG it's a `tEXt` chunk, and the hash covers the decoded pixels. In a JPEG it's a comment (`COM`) segment, and in a WebP an `XMP ` chunk; there the hash covers the whole file with the hash field zeroed. `tools/check.py` stays **stdlib-only**. It recomputes the hash and fails if the marker is missing, duplicated or doesn't match (e.g. a raw image copied in after the build, or an image edited afterwards).
- **Formats**: PNG, JPEG (`.jpg`/`.jpeg`) and WebP. Anything else (GIF, AVIF, TIFF…) fails the build: convert it first.
- **Previewing photos on Pantheon** needs Pillow in a local virtualenv (§7.1). Cloudflare Pages installs it from `requirements.txt` (§6).

**Site-wide**
| ID | Asset | Where | Size / format |
|---|---|---|---|
| IMG-01 | **Animated master logo**: the four circle shapes from `mark.svg` in the card colours, inline, animated with CSS (static when reduced motion is on) | Home hero | SVG |
| IMG-02 | Static master mark + IT7Q wordmark in Rajdhani | Header, footer | SVG + text |
| IMG-03 | Favicon | All | SVG favicon in card colours (Phase 1). PNG touch icons later, watermark-exempt as they *are* the mark |
| IMG-04 | Open Graph share image | All | 1200×630 |
| IMG-05–11 | Division badges ×7: the four circle shapes in the division colour + Latin name and translation as HTML text | Home badge row, divisions index, division pages | SVG (built from `mark.svg`) |
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
| IMG-20 | p2 Redbird Studio screenshot | as above |
| IMG-21 | p3 Pine Rivers RSL screenshot | as above |
| IMG-22 | p4 The Artist Apron screenshot | as above |
| IMG-23 | p5 Burpengary Jets screenshot | as above |
| IMG-35 | p6 BlueVibes Music screenshot | as above |
| IMG-36 | p7 Aussie Pathtag Club screenshot | as above |
| IMG-39 | p8 Niuleaf screenshot (from the live site) | as above |
| IMG-40 | p9 Pro Energy Solutions screenshot (when live) | as above |
| IMG-24–28, IMG-37–38 | Client logos p1–p7 (if consent covers logos) | SVG/PNG |

Screenshots are taken from the static snapshots (§6.3), so they match what the link shows.

**Project cards** (one public-safe image each, 800×500 JPEG or WebP; render, photo, product shot or illustrative graphic)
| IDs | Count | Notes |
|---|---|---|
| P-MSP-01…06 | 6 | UI mock-ups or illustrative graphics, not real admin screens |
| P-OPUS-01…11 | 11 | App screenshots with dummy data |
| P-MEN-01…05 | 5 | Illustrative (agent "team" graphic etc.) |
| P-TEM-01…06 | 6 | One per tier (T3 Guard gets a larger hero image, 1600×1000, from Chris's earlier **marketing renders**) + carrier board. **No PCB/schematic close-ups or spec labels** |
| P-POR-01…03 | 3 | Concept art/signage, no real locations of people's homes |
| P-FAB-001…035, P-FAB-101…103 | 38 | F-001–F-035 product photos (real photos week of 2 Nov) + FABRICUS App, FORMAE, BIONICUS |
| P-DOM-01 | 1 | Generic smart-home photo |

Plus P-MSP-07 (MERCATOR: a generic photo of networking gear and peripherals, no brand logos visible). That's **71 project images**, all watermarked at build (§5.1).

**v10 pages**: IMG-41 Shop category tiles ×3 (Networking, Office Peripherals, Storage Solutions; 800×500), IMG-42 Media/HERALD/Athena Coming soon art (HTML/CSS, no raster needed), IMG-43 software logos on Resources: **text only, no third-party logos**, to avoid trademark questions.

**Gated** (served only via `nda-content`, never in `dist/`): G-<project-id> detail images where useful, ≤ 300 KB each, as data URIs. Investor presentation assets: G-INV-xx.

---

## 6. Deployment approach

**Cloudflare Pages, free plan.**
- Private repo → Pages build command `pip install -r requirements.txt && python3 tools/build.py`, environment variable `PYTHON_VERSION=3.13` → publishes `dist/` only. `gated/`, `n8n/`, `deploy/`, `_brand/` and `_source/` never publish.
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
| `p1`–`p7.it7q.com.au` | Portfolio snapshots (archives) | One Pages project each (§6.3) | Created by Pages → Custom domains. p8/p9 need no record: they link to the clients' own domains |
| `tc` / `rb` / `pr` / `aa.it7q.com.au` | Old portfolio names | Proxied placeholder record + redirect rule → `p1`–`p4` | §6.3 step 7 |
| `downloads.it7q.com.au` | Existing (build pack) | unchanged | Confirm it stays |
| MX / SPF / DKIM / DMARC | noreply@ and info@ on MXRoute | MXRoute | Check SPF/DKIM cover MXRoute's sending hosts |
| `hooks.nubius.com.au` | Webhooks today | Existing cloudflared tunnel | Replaced for the public site by `forms.it7q.com.au` before launch (Q58) |
| `forms.it7q.com.au` | Public webhook base (Q58) | Same tunnel, `/webhook/*` only, edge header + Turnstile as §4.2 | Chris, Phase 6; then `endpoints.json` → `https://forms.it7q.com.au/webhook` |
| `staff.it7q.com.au` | Footer "Staff" link (Q52) | Behind Cloudflare Access | Chris, at launch |
| `shop.it7q.com.au` | MERCATOR store | — | Separate future build (§2.6); no record until then |

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

p1–p7 are archives (Q33). Each becomes a frozen static copy on its own Pages project. p8 Niuleaf stays on its live host and is only linked; p9 isn't touched until it's live. Steps, one site at a time, starting with p1:

1. **Inventory** (me, read-only, with Chris): for each site, record the current host and any dynamic bits a snapshot will break (contact forms, search, logins, booking/calendar widgets).
2. **Export** the four WordPress sites (**p1 True Colours, p2 Redbird Studio, p4 The Artist Apron, p7 Aussie Pathtag Club**): mirror each to static HTML with `wget --mirror --convert-links --adjust-extension --page-requisites --no-parent`. That's in-house, with nothing installed on the client's WordPress. Then strip `wp-json`, `xmlrpc`, `?ver=` query strings, oEmbed and login links. The static sites (p3, p5, p6) are copied from their repo or current host as-is.
3. **Archive treatment** on every snapshot page, applied by one small post-processing script:
   - `<meta name="robots" content="noindex">` on every page, plus `X-Robots-Tag: noindex` in `_headers`;
   - every `<form>` disabled (fields and submit `disabled`, `action` removed) with a short note: *"This is a portfolio copy, so this form is switched off."*;
   - a small fixed banner: *"Portfolio snapshot built by IT7Q"*, linking to `https://it7q.com.au/portfolio/`;
   - a basic CSP in `_headers`.
4. **Repo per snapshot**: a private repo per site (e.g. `IT7Q/p1-snapshot`). No build command; output directory is the site root.
5. **Pages project** `it7q-pN` (Chris creates it), connected to that repo. Check it on `it7q-pN.pages.dev`: pages, images, links, mobile.
6. **Custom domain** `pN.it7q.com.au` added in Pages (Chris, at go-live). Pages creates the DNS record.
7. **Old names** (`tc`→p1, `rb`→p2, `pr`→p3, `aa`→p4): keep a proxied DNS record on each old name, and add one Cloudflare **Single Redirect** rule per name: `301` to `https://pN.it7q.com.au` with path and query kept. Test with `curl -I` on a few deep links.
8. **Retire old hosting** for each site once its `pN` and redirect are verified (Chris).
9. **Screenshots** for IMG-19–23/35–36 are taken from the snapshots; IMG-39 from Niuleaf's live site.

Nothing in §6.3 touches DNS until Chris does steps 6–8.

---

## 7. Build phases (one step at a time)

0. ✅ Repo, source, plan v1. ✅ Financials removed from repo + history, GitHub purge done (§10). ✅ Plans v2–v6. ✅ NDA draft for review. ✅ Brand packs extracted and checked.
1. ✅ **Phase 1 (27 Oct)**: `src/` structure with stub pages for every route, build/check tools with unit tests, watermark pipeline, brand tokens, base CSS, header/footer, placeholder component, animated logo, Home (hero stats, badge row, coming-soon teaser). Preview: §7.1.
2. ✅ **Phase 2 (28 Oct, scope set by Chris)**: Divisions index + 7 division pages with all 70 cards from `projects.json`, MENTIS services list, Portfolio (`portfolio.json`), Services (`services.json`), Home testimonials (`testimonials.json`, consent guard). Plus Q40 fonts and Q43 JPEG/WebP watermarking. All images are placeholders.
3. ✅ **Phase 3 (28 Oct)**: About, Contact (+ enquiry form), Privacy, Terms and NDA pages (drafts, legal check pending); NDA front end: `/access/` (read + sign + request, login, logged-in state), locked panels on every card, the gated-detail renderer with watermark, the logout bar, the `/investors/` locked shell; `tools/preview.py` mock with failure scenarios (§4.12).
3b. ✅ **Phase 3b (29 Oct)**: MERCATOR card (P-MSP-07) + `/shop/`; `/resources/` with the 15 software entries + Guides section and guide pages (placeholders); `/media/`, `/news/`, `/athena/` Coming soon pages; `/credentials/`; nav update; footer social row, WhatsApp button and Staff link; About text from Q51; the four v10 guards (§3) with tests; the webhook base as one config value (Q58). Download URLs were written from my knowledge of each project's official site; Pantheon's sandbox blocked fetching them, so Chris clicks each one in the preview (Q60). Guide Markdown uses the legal-text renderer (headings, paragraphs, lists, bold); it gets extended when Chris's first guide files show what they need.
3c. **Phase 3c (next small step, when Chris says go)**: About: drop the two overlapping lines, keep the Credentials link (Q61). Footer: the five social URLs and the "Chris's LinkedIn" label in `site.json`, Google Business and TikTok hidden, no Reddit/Etsy (Q54); a test for each. Fix any Download URLs Chris reports from the click-test (Q60).
4. Gated content: feature-level `gated/` JSON (§4.9, Chris reviews), the n8n workflows (five webhooks + `nda-retention`), SQL, `deploy/` docs for Chris to review.
5. Investor content (the shell and its renderer exist since Phase 3); Blog + Downloads only if 2–3 posts are ready (Q17).
6. QA (§6.2), preview deploy, Chris walk-through, DNS (Chris), go live. Launch switches: webhook base → `https://forms.it7q.com.au/webhook` in `endpoints.json` (Q58), Cloudflare Access on `staff.it7q.com.au` (Q52), Turnstile site key in `endpoints.json`, Pillow hashes in `requirements.txt` (Q47), a check that fails on any remaining PLACEHOLDER text, "Draft" legal note, empty social URL or placeholder Staff URL.
7. Portfolio snapshots (§6.3), one site at a time. This can run alongside phases 2–6.

### 7.1 Previewing locally
From `/srv/work/it7q-website` on Pantheon:
```
.venv/bin/python tools/preview.py
```
Then open <http://localhost:8080/> in a browser on the Windows side (WSL2 forwards localhost). It builds a **mock** build, serves it with the same security headers as Pages (so CSP problems show in the browser console), and answers the forms and logins itself (§4.12). It's bound to 127.0.0.1 only. `Ctrl+C` stops it. Afterwards, `dist/` holds the mock build: run `.venv/bin/python tools/build.py` before comparing anything with production.

**Walk-through** (what I can't test without a browser): send the enquiry form; request access; log in as `investor@example.test`, open a division page and the investor area, log out; then repeat with scenarios `down`, `slow`, `session-expired`, `forbidden` and `content-bad-json`. Every failure must leave the cards locked.

Once JPEG/WebP photos are in `src/assets/img/`, the build needs Pillow in `.venv/` (git-ignored). On Ubuntu, `python3 -m venv` only includes pip if the `python3-venv` package is installed. Without it the venv comes out empty (that happened on 28 Oct: `.venv/` has no pip and no Pillow). One-off fix as `chris`:
```
sudo apt install python3-venv          # adds ensurepip, so new venvs get pip
cd /srv/work/it7q-website
rm -rf .venv && python3 -m venv .venv  # recreate it, now with pip
.venv/bin/pip install -r requirements.txt
.venv/bin/python -c "import PIL; print(PIL.__version__)"   # expect 12.0.0
```

---

## 8. Open questions for Chris

**Answered**: 1–43, 47, 48, 51, 52, 54 (all but Google Business), 55, 57, 58 and 61 (see §1a). Q35's defaults are in the §2.1 table for Chris to correct later. Q39 and Q41 are checked in the preview.

**Still open**
36. **Legal check** before launch: the NDA (`src/legal/nda-1.0.md`, reviewer notes in `docs/nda-draft.md`), plus the new Privacy and Terms drafts.
44. **Proposed extra stats** (§2): approve any of the five, or none.
45. **Card copy**: check the one-liners and "why it's unique" lines on the division pages, especially my drafts (TEMPESTAS "who it's for", COLLOQUIUM, PORTUS App/Jnr, FABRICUS App/FORMAE/BIONICUS) and the MENTIS automations list.
46. **BlueVibes Music (p6)**: a few words on what it is, for a better one-liner. **Niuleaf (p8)**: the one-liner you said you'd supply.
49. **Messaging**: is WhatsApp on 0411 753 366 (the Contact page and now the footer link `wa.me/61411753366`)? And the Facebook Messenger page link, if you want it listed.
50. **Pillow on Pantheon**: `.venv/` has no pip yet; fix in §7.1 (needs `sudo`).
53. **Credentials list** (to come): qualifications and certifications (title, issuer, year), no units.
54. **Google Business** share link (to come). Hidden until then.
56. **Athena CE** (later): where the build will be hosted, and whether it's code-signed.
59. **Guide files**: Windows and Android hardening guides, then the Education Series chapters, as Markdown/HTML for view-in-browser plus a PDF each, with metadata stripped.
60. **Download links** (Chris is click-testing): click each of the 15 Download buttons on `/resources/` in the preview and report any that don't land on the official download page.
62. **TikTok**: the v10 footer list had TikTok, but your Q54 list doesn't. Drop it, or keep it hidden until there's an account?

---

## 9. Parked (pins)
- Client portal dashboard / SSO (Jan spec): needs its own auth design and shouldn't advertise internal hostnames.
- Admin portal login: better as a bookmark behind Cloudflare Access.
- Neo website-evaluation workflow.
- WordPress version: superseded.
- Blog + Downloads, if fewer than 2–3 posts are ready at launch (Q17). (HERALD may end up replacing the blog; decide when HERALD is planned.)
- **FABRICUS Etsy shop**: once the shop exists, its link goes on the FABRICUS division page (not the footer; no Etsy link in the social row).
- **IT7Q LinkedIn company page**: when it exists, swap it in for (or add it beside) Chris's LinkedIn in the footer.
- **Separate future builds** (§2.6), each with its own plan and repo: the **MERCATOR store** (`shop.it7q.com.au`), **self-hosted video/podcast hosting**, the **HERALD app**, and Athena CE distribution.

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
- **27 Oct 2026: plan v7 + Phase 1.** Brand = business card. Phase 1 scaffold, tools and Home committed.
- **28 Oct 2026: plan v8 + Phase 2.** Q40–Q43 answered, portfolio details, testimonials. Phase 2 built: cards, Portfolio, Services, testimonials, TTF fonts, JPEG/WebP watermarking.
- **28 Oct 2026: plan v9 + Phase 3.** Q47 answered. About, Contact, Legal, NDA front end, enquiry form, local mock. NDA text moved to `src/legal/nda-1.0.md`.
- **29 Oct 2026: plan v10.** Chris's new scope folded in: MERCATOR (MSP section) + Shop, Resources + Guides, Media, News (HERALD), Credentials, Athena CE page, footer Staff/social links, PORTUS discretion. Phase 3b planned; separate future builds listed in §2.6.
- **29 Oct 2026: plan v11.** Q51, Q52, Q54, Q55, Q57, Q58 answered.
- **29 Oct 2026: Phase 3b built.** MERCATOR card + Shop, Resources + 20 guide pages, Media/News/Athena/Credentials pages, footer social/WhatsApp/Staff, About text, webhook base as one value; download, PDF, PORTUS and footer guards.
- **29 Oct 2026: plan v12.** Q61 and Q54 (all but Google Business) answered; Q62 (TikTok) asked; Etsy and LinkedIn company page pinned; Phase 3c queued.
