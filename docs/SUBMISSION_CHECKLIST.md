# Hackathon Submission Checklist (Keppel AI HARVEST, Real Estate)

**Deadline:** Thu 16 Oct 2026 · **Prize route:** top 2 per track → Demo Day
(3 Nov) → First Prize SGD $10,000.
**Status legend:** ✅ done (in repo) · 🖐 needs Maya's manual action · ⚠ open/optional

---

## 1. Platform gate (mandatory)

| Item | Status | Where / note |
|---|---|---|
| Built on CodeBuddy, deployed via WorkBuddy/ADP | ✅ | CodeBuddy produced the backend/frontend; WorkBuddy produced spec (`miora/`); ADP deployment steps in `docs/ADP_SETUP.md` |
| ≥3 chat-log screenshots | 🖐 | Maya has them (CodeBuddy/WorkBuddy conversations). Add to the form and/or the repo under `docs/submission_assets/chatlogs/` (optional for repo). |
| Live project link (ADP Experience URL) | 🖐 | Requires publishing the ADP agent in the Tencent Cloud console. Repo is wired & verified for `TBC_LLM_PROVIDER=adp`; see `docs/ADP_SETUP.md`. |

## 2. Required text fields (use exactly one of each)

### Project title
```
Technical Services Intelligence Pill — Keppel AI HARVEST
```
(Shorter alternative if the form truncates: **`Keppel Technical Services Intelligence Pill`**)

### Blurb (must be <10 words) — pick one
1. `Expert know-how captured, governed, and reused on demand.` (7 words)
2. `Retire-proof fault diagnosis for Keppel data centres.` (7 words)
3. `AI drafts, stewards approve, machines stay deterministic.` (7 words)

**Recommended: option 1** (maps most directly to "capture, reuse, AOM supervision, post-deploy governance").

### Project description (with quantifiable metrics)
Suggested 4-paragraph skeleton — reuse the checked numbers from `README.md` § Quantifiable metrics:

1. **Problem & users.** Fault-diagnosis know-how lives in a few senior technicians' heads; retirement loses it. Users: technicians, Asset Ops Managers, Knowledge Stewards (all demoable in-app).
2. **What it does (the loop).** Capture → AI draft → second-steward approval → governed pill → deterministic diagnosis → guardrails → AOM approval → outcome → validated feedback written back. AI is bounded: drafts capture, advisory second opinion only.
3. **Quantifiable metrics.** 133 pytest & 13/13 acceptance evals pass from a clean clone; 4 asset classes/24 canonical causes/9 deterministic guardrails/11-state hash-chained audit; 5-role RBAC, 6 demo users; an approved knowledge cycle measurably lifts `kb_match` 0.73→1.00 and confidence on the next identical fault.
4. **Honest boundaries.** Machine triage baseline flagged as an assumption pending a measured Keppel figure; telemetry is a mock registry until a real BMS/SCADA feed (deployment staged in `docs/IMPLEMENTATION_PATH.md`).

### Cover image (mandatory, 16:9, 380×216)
| Item | Status |
|---|---|
| 16:9, exactly 380×216 px | 🖐 generate + export |
| Shows the loop (Capture → Steward → Diagnose → Guardrail → AOM) | use the diagram in `docs/SOLUTION_DIAGRAM.md` as the art source |
| Text legible at thumbnail size | keep to ≤4 short labels |
| **Suggested source:** title slide of the demo video (same art = cohesive branding) | 🖐 |

## 3. Screenshots (mandatory ×3 minimum)
| Item | Status |
|---|---|
| 3 ch at-logs (CodeBuddy + WorkBuddy) | 🖐 insert |
| Suggested trio: (1) WorkBuddy spec/UX chat, (2) CodeBuddy backend/test chat, (3) capture/grounding chat | match caption |
| Optional UI screenshots to reinforce: Decision screen (G2b banner), Capture review, Knowledge Reused | ✅ `make serve` → localhost:8000/ui |

## 4. Demo video (optional, maximum 5–8 min)
| Item | Status |
|---|---|
| Script follows `DEMO.md` (6-minute mark) | ✅ script exists |
| Cover the round-2 judge's live probes so they survive a re-run: CLOSED loop, ESCALATED resolve, approval block, steward self-approval 403, capture→reuse, rollback, AI offline, audit-tamper FAIL badge + Integrity Events card, unknown-asset G5 via the UI free-text field | ✅ all now reachable via UI **and re-verified headlessly** — `tests/self_probe.py` re-runs every probe from both judge reports as one **14/14 PASS** table (`docs/SELF_PROBE_QA.md`) |
| Record screen at 1080p, plan a clean 60s out-take where the flow breaks (e.g. ask a judge "what should it do?") — ownership beats polish | 🖐 |
| Upload + link the video in the form and/or README | ⚠ optional |

## 5. Where everything already provable (rebuttal kit)
- `make test` (133 passing) · `make eval` (13/13) · `make serve` → live UI · `make demo` (scripted walkthrough)
- `tests/self_probe.py` (**14/14 PASS**) + `docs/SELF_PROBE_QA.md` — every judge probe from both reports re-run as one evidence table
- `docs/SOLUTION_DIAGRAM.md` — point-by-point map of the 8 required questions
- `docs/IMPLEMENTATION_PATH.md` — feasibility / staged production path
- `docs/ADP_SETUP.md` — ADP (Tencent Cloud) wiring
- `docs/JUDGE_REPORT_2026-10-07_round2.md` → **fixes all five findings** (negation-aware capture, G2b banner on decision, G5 free-text asset, New-Case scroll-into-view, stale-hint cleanup): verified in code + tests + evals; the round-3 score is what matters.

## 6. Final QA gate (run before upload)
```bash
make test && make eval && make serve   # all green, then screenshot every screen
```
1. Confirm the demo video opens every screen shown
2. Confirm ADR screenshot each chat log is readable at thumbnail size
3. Confirm cover image has no bottom-crop at 216px height (16:9 math: 380×213.75 → pad to 216)
4. Confirm description uses "133 / 13" (not the stale "120 / 19")

## 7. GitHub repo metadata (About / description)

**Repository description (≤350 chars):**
```
Technical Services Intelligence Pill for Keppel AI HARVEST. Captures expert
fault-diagnosis know-how as steward-governed, versioned knowledge; deterministic
decision trees + 9 guardrails + advisory AI; hash-chained audit. 133 tests, 13/13
evals.
```

**About section (short):**
```
• Capture → steward review → approved knowledge → reuse
• AI drafts & advises; AOM decides; guardrails enforce
• Deterministic decision trees, 5-role RBAC, SHA-256 audit
Topics: ai-harvest, keppel, hackathon, intelligence-pill, fastapi, rbac, guardrails, fault-diagnosis
Website: (ADP Experience URL once published — 🖐)
```

---
*Nothing above requires inventing Keppel data; every number is measured in this repo or explicitly labelled an assumption.*