# IT7Q NDA — draft v1.0 for review

**Status: DRAFT for Chris's review, then a legal check (PLAN.md Q10, Q36). Not legal advice, and not for publishing until it's been checked.**

This replaces v2's "Mutual" NDA. v2's text called itself mutual, but only IT7Q discloses anything, and it framed everything around investors. This draft is one-way, covers all seven divisions and the investor area, runs for 3 years, and ties website access to that term.

---

## The agreement text

The agreement itself is in **`src/legal/nda-1.0.md`**. The site shows exactly that file on `/legal/nda/` and `/access/`, and its SHA-256 is the fingerprint recorded when someone signs (PLAN.md §4.3). Edit the text there, and give it a new version number (a new file, `nda-1.1.md`) once anyone has signed v1.0.

## Notes for the reviewer (not part of the agreement)

1. **One-way** (IT7Q discloses only), replacing v2's "Mutual" wording. Section 1 states that the recipient isn't asked to disclose anything.
2. **Scope**: the Purpose is broad (investment, partnership, customer/supplier dealings), because approval grants all seven divisions by default. Investor access is granted per person, but the same agreement covers it.
3. **Term and survival**: 3 years, and website access ends at the same time. Confidentiality survives (clause 8(b)): indefinitely for trade secrets, otherwise 2 years after the Term.
4. **No-screenshot clause** (4(d)): is it enforceable or reasonable as worded? It backs up the watermark in the site.
5. **Electronic signature**: relies on typed name + tick + click, with the record emailed to the signer. Please confirm this is adequate under the *Electronic Transactions (Queensland) Act 2001*.
6. **Privacy** (clause 11): retention periods match PLAN.md §4.10. The privacy policy page must say the same.
7. **Entity**: "IT7Q Cyber-Tech Services" with ABN 43 922 878 001, as in v2. Please confirm this is the correct legal name for that ABN.
8. **Version**: when the text is final, the site embeds its SHA-256. Any later change gets a new version number, and existing signers stay on the version they accepted.
9. **Records vs survival**: acceptance records are deleted at Term + 2 years (PLAN.md §4.10). That covers survival limb (ii), but not limb (i) (trade secrets, indefinite), or a claim brought within Queensland's 6-year limitation period. Should a minimal acceptance record (name, email, version, hash, date; no IP) be kept longer?

10. **Survival period (clause 8)**: Chris's instruction is that confidentiality must survive the Term: indefinitely for trade secrets, otherwise for a sensible period. I've drafted **2 years** after the Term, so the total is 5 years from acceptance. That lines up with the site's record retention (Term + 2 years). Please confirm the period suits, and see note 9 on keeping records long enough to enforce the trade-secret limb.

**This draft needs a legal check before launch.**
