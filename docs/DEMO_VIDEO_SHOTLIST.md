# Demo video — shot list (target 5–8 min)

Maps 1:1 onto `DEMO.md`'s 11 segments. For every screen: use the role
switcher (top bar) so the viewer always sees *who* is acting. Show URLs in the
browser bar (localhost vs ADP) so "this is real" is unmissable.

Exact values below are the seeded/demo-data defaults — if `make demo` prints
different numbers **on the day**, read the screen, don't fight it. The guard
is the *story beats*, not the digits.

| # | Time | Screen (who) | Action | Say (≤2 sentences) | Proof byte |
|---|---|---|---|---|---|
| 1 | 0:00–0:30 | Problem (no app — whiteboard / cover art) | — | "Fault know-how lives in a few senior technicians' heads. When they retire, it retires with them." | none needed |
| 2 | 0:30–0:50 | Dashboard, 6 demo users | hover the role switcher | "5 roles, 6 users, 33 API endpoints — RBAC tested server-side, not just in the UI." | roles dropdown |
| 3 | 0:50–1:20 | Steward + Capture | paste J. Lim CRAH interview → **Review** | "AI drafts structured heuristics. Nothing ships until a *different* steward approves." | draft labelled **AI hypothesis**; note the verbatim-grounding dropdown |
| 4 | 1:20–1:35 | Steward | untick two wrong-cause heuristics (thermistor demo) | "Grounding check: quotes must exist verbatim or the item is dropped — capture gained negation-awareness this sprint." | the offending heuristics vanish, status → review |
| 5 | 1:35–1:55 | Steward #1 back on queue | self-approve → greyed + reason | "It says *you sent this* — a different steward must decide. Server-side 403 too." | `403 "steward1 proposed PROP-... and cannot also approve it"` (curl optional) |
| 6 | 1:55–2:15 | Steward #2 | approve → KB bumps to next version | "Approved. Versioned, rollback-able, owner recorded in the Pill Registry." | `/kb/versions`; new version label shown |
| 7 | 2:15–2:50 | Technician + AOM | new case CRAH-DC1-01 → **New Case** (form scrolls into view) → advance | "Deterministic tree, W1–W5 confidence, guardrails G1–G9 run *before* any human sees it." | diagnosis card labelled **deterministic**; confidence factor bars |
| 8 | 2:50–3:15 | AOM Decision | refrigerant-leak repair: **G2b hazard banner** next to Approve/Reject | "Safety flag is on the approve screen itself — approve, reject or modify with rationale." | the red hazard banner |
| 9 | 3:15–3:40 | AOM Decision (second case) | AI second opinion disagreement → G9 | "The AI disagrees *advisory-only* — it flags, it never routes." | AI card: **AI hypothesis — advisory only, does not affect routing** |
| 10 | 3:40–4:05 | AOM | approve → work order → outcome | "Every action typed by name into a SHA-256 chain." | outcome status |
| 11 | 4:05–4:30 | Outcome screen | submit feedback → **hint now clears**; steward approves proposal | "Feedback can't touch the KB directly — it becomes a proposal a steward approves." | tip text disappears post-submit; proposal in queue |
| 12 | 4:30–4:50 | Technician re-runs diagnosis | identical fault now shows **Expert Knowledge Reused** (J. Lim, KB vX, verbatim quote) | "Same fault, faster — reuses the captured knowledge, confidence rises." | `kb_match` / confidence delta |
| 13 | 4:50–5:10 | Escalation | G3 cross-domain case → Resolve Escalation reason box | "Cross-domain issues route to another pill's owner — 'who to call' is visible." | ESCALATED → CLOSED |
| 14 | 5:10–5:30 | Unknown asset | **free-text asset** in New Case (e.g. `NOPE-999`) → G5 | "Unknown asset escalates, never fabricates a diagnosis. That's the guardrail the rubric noticed." | confidence 0.0 + G5 rule ids |
| 15 | 5:30–5:50 | Governance / audit | open audit table; red **FAIL** chain badge on the restarted case + **Integrity Events** card | "Tamper any past entry and every later hash breaks — and the evidence itself is archived, so even a clean restart can't sweep it away." | FAIL badges + Integrity card |
| 16 | 5:50–6:00 | Close | — | "AI harvests the know-how; determinism executes; each **pill** extends the same loop to a new asset class — four ship today." | endpoint `/pills` or the 4 asset cards |

## If the review runs long
- **Drop #4 half**, keep one untick.
- **Drop #13 or #14** — never both; #14 is the strongest in front of judges who read the rubric.

## Recording hygiene
- 1080p, capture window at browser *and* terminal (run `make demo` alongside for the deterministic output).
- Note: tampered snapshots are archived on load (or before any overwrite) and listed on the Governance **Integrity Events** card — a tamper stays provable *even after a graceful shutdown*. To film it: edit `data/tbc.sqlite`, restart once, and show both the red FAIL badges and the preserved archive.
- End with 3s of held frame on the close line.