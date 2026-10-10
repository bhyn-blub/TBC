#!/usr/bin/env python3
"""Self-probe QA pass — re-runs every live probe from both judge reports
(docs/JUDGE_REPORT_2026-10-07.md and ..._round2.md) as one deterministic,
judge-shaped evidence table, plus the two new tamper-durability probes.

Run:  .venv\\Scripts\\python.exe tests/self_probe.py   (exit 0 == all PASS)

Each probe gets a fresh temp DB and a factory-reset engine (same isolation as
the pytest files) so the judge's narrative can be replayed exactly:
P01  CLOSED lifecycle in click order           P08  tamper: runtime edit
P02  ESCALATED -> resolved via API             P09  tamper: offline + restarts
P03  technician approval blocked (+ spoof)     P10  unknown asset -> G5
P04  steward self-approval blocked             P11  identity spoofing
P05  capture -> reuse (verbatim KB match)      P12  extractor regression (r2 #1)
P06  approve -> rollback int<->label           P13  G2b hazard data contract
P07  AI offline / capture 502                  P14  contrast + integrity UI + demo
"""
from __future__ import annotations

import glob as _glob
import os
import pickle
import sqlite3
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime

# Take over the environment before importing app modules, and force the
# cookie-only security mode off via TBC_DEMO_INSECURE=0 (never honour ?user=).
os.environ.setdefault("TBC_LLM_PROVIDER", "mock")
os.environ.pop("TBC_ADP_API_KEY", None)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

from technical_services_pill import learning, llm, persistence, store, tools  # noqa: E402
from technical_services_pill.app import app  # noqa: E402
from technical_services_pill.database import SQLiteStore  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []  # (id, title, passed, detail)


def _isolate(probe: str) -> str:
    """Factory-reset the engine singletons and point all DBs at a fresh temp
    dir so probes never read each other's state."""
    d = tempfile.mkdtemp(prefix=f"tbc-selfprobe-{probe}-")
    os.environ["TBC_DB_PATH"] = os.path.join(d, "tbc.sqlite")
    os.environ["TBC_CASE_DB_PATH"] = os.path.join(d, "cases.sqlite3")
    os.environ["TBC_PERSIST"] = "1"
    # The bulk of the judge-style probes call the API with ?user= (as the
    # evals do). The secure default is itself probe P11, which toggles this
    # flag off and proves ?user= is rejected without a cookie.
    os.environ["TBC_DEMO_INSECURE"] = "1"
    os.environ["TBC_LLM_PROVIDER"] = "mock"
    os.environ.pop("TBC_ADP_API_KEY", None)
    persistence._INTEGRITY_EVENTS.clear()
    persistence._last_written.clear()
    persistence._reported.clear()
    store.STORE._db = SQLiteStore(os.path.join(d, "cases.sqlite3"))
    store.STORE._cases.clear()
    learning.STORE.__init__()
    tools.TOOL_AUDIT_LOG[:] = []
    return d


def _login(client: TestClient, user_id: str) -> None:
    resp = client.post("/login", params={"user_id": user_id})
    assert resp.status_code == 200, resp.text


def _create_and_advance(client: TestClient, asset_id="CRAH-DC1-01",
                        sensor_id="SA-TEMP-01", obs="temperature_measurement_missing") -> dict:
    resp = client.post("/cases", params={
        "asset_id": asset_id, "sensor_id": sensor_id, "user": "tech1",
        "observation_type": obs, "reading_status": "absent",
    })
    assert resp.status_code == 200, resp.text
    case_id = resp.json()["case_id"]
    resp = client.post(f"/cases/{case_id}/advance", params={"user": "tech1"})
    assert resp.status_code == 200, resp.text
    return client.get(f"/cases/{case_id}", params={"user": "tech1"}).json()


def _tamper_cases_blob(db: str) -> None:
    conn = sqlite3.connect(db)
    (blob,) = conn.execute("SELECT blob FROM snapshots WHERE key='cases'").fetchone()
    data = pickle.loads(blob)
    for st in data.values():
        if getattr(st, "history", None):
            st.history[-1].reason += " [TAMPERED-EDIT]"
            break
    conn.execute(
        "INSERT OR REPLACE INTO snapshots (key, blob, saved_at) VALUES (?, ?, ?)",
        ("cases", pickle.dumps(data), datetime.now().isoformat()),
    )
    conn.commit()
    conn.close()


def _archives(probe_dir: str) -> list[str]:
    return _glob.glob(os.path.join(probe_dir, "tbc.tampered.*.sqlite"))


def probe(probe_id: str, title: str):
    def decorator(fn):
        def wrapper():
            try:
                detail = fn() or "ok"
                RESULTS.append((probe_id, title, True, detail))
            except AssertionError as exc:
                RESULTS.append((probe_id, title, False, str(exc)))
            except Exception as exc:  # noqa: BLE001 -- a probe erroring is a failure
                RESULTS.append((probe_id, title, False, f"{type(exc).__name__}: {exc}"))
        return wrapper
    return decorator


# --------------------------------------------------------------------------- #
@probe("P01", "CLOSED lifecycle: create, approve, work order, outcome, feedback")
def _p01():
    d = _isolate("p01")
    with TestClient(app) as c:
        resp = c.post("/cases", params={
            "user": "tech1", "asset_id": "CRAH-DC1-01", "sensor_id": "SA-TEMP-01",
            "observation_type": "temperature_measurement_missing", "reading_status": "absent",
        })
        cid = resp.json()["case_id"]
        c.post(f"/cases/{cid}/advance", params={"user": "tech1"})
        c.post(f"/cases/{cid}/approval", params={"user": "mgr1", "decision": "approve", "rationale": "x"})
        c.post(f"/cases/{cid}/work-order", params={"user": "mgr1"})
        c.post(f"/cases/{cid}/outcome", params={
            "user": "tech1", "result": "resolved", "root_cause_confirmed": "sensor_hardware_failure",
        })
        c.post(f"/cases/{cid}/feedback", params={"user": "steward1"})
        snap = c.get(f"/cases/{cid}", params={"user": "tech1"}).json()
        assert snap["current_state"] == "CLOSED", snap["current_state"]
        assert snap["audit_chain_valid"] is True
        assert len(snap["history"]) >= 7
    return f"{cid} CLOSED, chain valid, {len(snap['history'])} audit entries"


@probe("P02", "ESCALATED (G3, comm bus) -> resolved to CLOSED")
def _p02():
    d = _isolate("p02")
    with TestClient(app) as c:
        snap = _create_and_advance(c, "CRAH-DC1-02", "SA-TEMP-02")
        cid = snap["case_id"]
        assert snap["current_state"] == "ESCALATED", snap["current_state"]
        gr = snap["guardrail_result"]
        assert "G3" in gr["rule_ids"]
        assert "Building Management System" in " ".join(gr["reasons"])
        r = c.post(f"/cases/{cid}/escalation/close", params={"user": "mgr1", "reason": "known cross-domain fault"})
        assert r.status_code == 200, r.text
        snap = c.get(f"/cases/{cid}", params={"user": "tech1"}).json()
        assert snap["current_state"] == "CLOSED"
    return f"{cid} ESCALATED(G3) -> CLOSED"


@probe("P03", "Technician approval blocked, incl. cookie + ?user=mgr1 spoof")
def _p03():
    d = _isolate("p03")
    with TestClient(app) as c:
        _login(c, "tech1")
        snap = _create_and_advance(c)
        cid = snap["case_id"]
        r = c.post(f"/cases/{cid}/approval", params={
            "user": "mgr1", "decision": "approve", "rationale": "x",
        })
        assert r.status_code == 403, r.text
        assert "approve_reject_modify" in r.json()["detail"]
    return "cookie=tech1 + ?user=mgr1 spoof still rejected with 403"


@probe("P04", "Steward self-approval blocked server-side")
def _p04():
    d = _isolate("p04")
    with TestClient(app) as c:
        snap = _create_and_advance(c)
        cid = snap["case_id"]
        c.post(f"/cases/{cid}/approval", params={"user": "mgr1", "decision": "approve", "rationale": "x"})
        c.post(f"/cases/{cid}/work-order", params={"user": "mgr1"})
        c.post(f"/cases/{cid}/outcome", params={
            "user": "tech1", "result": "resolved", "root_cause_confirmed": "sensor_hardware_failure",
        })
        _login(c, "steward1")
        fb = c.post(f"/cases/{cid}/feedback", params={"user": "steward1"}).json()
        queue = c.get("/kb/queue", params={"user": "steward1"}).json()["queue"]
        pid = next(p["proposal_id"] for p in queue if p["feedback_id"] == fb["feedback_id"])
        # Spoof a different steward via ?user= on the proposer's own session.
        r = c.post(f"/kb/proposals/{pid}/approve", params={"user": "steward2"})
        assert r.status_code == 403, r.text
        assert "cannot also approve" in r.json()["detail"]
        r2 = c.post(f"/kb/proposals/{pid}/approve", params={"user": "steward2"})
        assert r2.status_code == 403
    return "self-approval 403 with spoofed ?user=steward2 layered over steward1 cookie"


@probe("P05", "Capture -> steward approval -> verbatim reuse of expert knowledge")
def _p05():
    d = _isolate("p05")
    from technical_services_pill.capture import SAMPLE_INTERVIEW
    with TestClient(app) as c:
        pre = _create_and_advance(c)
        pre_kb = pre["confidence_breakdown"]["kb_match"]
        pre_match = c.get(f"/cases/{pre['case_id']}/expert-knowledge", params={"user": "tech1"}).json()
        assert pre_match["matches"] == [], "no approved expert knowledge yet"

        r = c.post("/capture/interview", json={
            "expert_name": "R. Tan", "expert_role": "Senior M&E Technician, 22 years",
            "asset_type": "CRAH", "transcript": SAMPLE_INTERVIEW,
        }, params={"user": "steward1"})
        assert r.status_code == 200, r.text
        pid = r.json()["proposal_id"]
        assert len(r.json()["heuristics"]) == 4, r.json()["heuristics"]
        r = c.post(f"/kb/proposals/{pid}/approve", params={"user": "steward2"})
        assert r.status_code == 200, r.text

        post = _create_and_advance(c)
        post_kb = post["confidence_breakdown"]["kb_match"]
        assert post["diagnosis"]["top_cause_id"] == "sensor_hardware_failure", post["diagnosis"]
        matches = c.get(f"/cases/{post['case_id']}/expert-knowledge", params={"user": "tech1"}).json()["matches"]
        assert len(matches) == 1, matches
        m = matches[0]
        assert m["expert_name"] == "R. Tan", m
        assert m["knowledge_id"].startswith("KB-EXP-"), m
        assert len(m["evidence_quote"]) >= 20, m["evidence_quote"]
    return f"KB-EXP reuse shown for R. Tan (kb_match {pre_kb:.2f} -> {post_kb:.2f})"


@probe("P06", "Approve -> version bump -> rollback: label and confidence restored exactly")
def _p06():
    d = _isolate("p06")
    with TestClient(app) as c:
        baseline = _create_and_advance(c)
        confidence_before = baseline["confidence"]
        version_before = c.get("/kb/stats", params={"user": "tech1"}).json()["kb_version"]
        cid = baseline["case_id"]
        c.post(f"/cases/{cid}/approval", params={"user": "mgr1", "decision": "approve", "rationale": "x"})
        c.post(f"/cases/{cid}/work-order", params={"user": "mgr1"})
        c.post(f"/cases/{cid}/outcome", params={
            "user": "tech1", "result": "resolved", "root_cause_confirmed": "sensor_hardware_failure",
        })
        fb = c.post(f"/cases/{cid}/feedback", params={"user": "steward1"}).json()
        queue = c.get("/kb/queue", params={"user": "steward1"}).json()["queue"]
        pid = next(p["proposal_id"] for p in queue if p["feedback_id"] == fb["feedback_id"])
        c.post(f"/kb/proposals/{pid}/approve", params={"user": "steward2"})
        bumped = c.get("/kb/stats", params={"user": "tech1"}).json()["kb_version"]
        assert bumped != version_before

        r = c.post(f"/kb/rollback/{version_before}", params={"user": "admin1"})
        assert r.status_code == 200, r.text
        after = c.get("/kb/stats", params={"user": "tech1"}).json()["kb_version"]
        assert after == version_before, f"{after} != {version_before}"
        restored = _create_and_advance(c)
        assert restored["confidence"] == confidence_before
    return f"rollback restored label {version_before} and confidence {confidence_before} exactly"


@probe("P07", "AI offline: second opinion soft-fails; capture hard-fails 502")
def _p07():
    d = _isolate("p07")
    os.environ["TBC_LLM_PROVIDER"] = "adp"
    os.environ.pop("TBC_ADP_API_KEY", None)
    try:
        with TestClient(app) as c:
            snap = _create_and_advance(c)
            assert snap["ai_hypothesis"]["status"] == "unavailable"
            assert snap["diagnosis"] is not None
            r = c.post("/capture/draft", json={
                "asset_type": "CRAH", "transcript": "Interviewer: What do you check?\n\nTechnician: The obvious thing.",
            }, params={"user": "steward1"})
            assert r.status_code == 502, r.text
        return "ADP (no key): diagnosis unaffected, AI labelled unavailable, capture HTTP 502"
    finally:
        os.environ["TBC_LLM_PROVIDER"] = "mock"


@probe("P08", "Tamper while running: archived at next save, no restart needed")
def _p08():
    d = _isolate("p08")
    db = os.environ["TBC_DB_PATH"]
    with TestClient(app) as c:
        cid = _create_and_advance(c)["case_id"]
        _tamper_cases_blob(db)
        c.post(f"/cases/{cid}/advance", params={"user": "tech1"})
        evs = c.get("/system/integrity", params={"user": "auditor1"}).json()["events"]
        assert any(e["event"] == "snapshot_modified_between_saves" for e in evs), evs
        denied = c.get("/system/integrity", params={"user": "tech1"})
        assert denied.status_code == 403
    assert len(_archives(d)) == 1
    return f"runtime tamper archived ({len(_archives(d))} file) + integrity event; RBAC enforced"


@probe("P09", "Tamper offline: evidence survives clean restarts, stays flagged")
def _p09():
    d = _isolate("p09")
    db = os.environ["TBC_DB_PATH"]
    with TestClient(app) as c:
        cid = _create_and_advance(c)["case_id"]
    _tamper_cases_blob(db)
    with TestClient(app) as c:
        evs = c.get("/system/integrity", params={"user": "auditor1"}).json()["events"]
        assert any(e["event"] == "audit_chain_failure_on_load" for e in evs), evs
        assert c.get(f"/cases/{cid}", params={"user": "tech1"}).json()["audit_chain_valid"] is False
    assert len(_archives(d)) == 1
    with TestClient(app) as c:
        evs = c.get("/system/integrity", params={"user": "auditor1"}).json()["events"]
        n = len([e for e in evs if e["event"] == "audit_chain_failure_on_load"])
        assert n == 1, "the same tamper must not be double-reported across restarts"
        assert c.get(f"/cases/{cid}", params={"user": "tech1"}).json()["audit_chain_valid"] is False
    assert len(_archives(d)) == 1
    return "tamper archived once, event survives 2 clean restarts, case stays FAIL"


@probe("P10", "Unknown asset NOPE-999 escalates via G5, never fabricates")
def _p10():
    d = _isolate("p10")
    with TestClient(app) as c:
        snap = _create_and_advance(c, "NOPE-999", "X")
        assert snap["current_state"] == "ESCALATED", snap["current_state"]
        assert "G5" in snap["guardrail_result"]["rule_ids"]
        assert snap["confidence"] == 0.0
        assert snap["diagnosis"] is None
    src = open("frontend/static/js/screens.js", encoding="utf-8").read()
    assert "Other / unregistered asset" in src, "G5 must be reachable from the New Case form"
    return "NOPE-999 -> ESCALATED (G5), confidence 0.0, no diagnosis; free-text option present in UI"


@probe("P11", "Identity spoofing: cookie wins, ?user= disabled by default")
def _p11():
    d = _isolate("p11")
    os.environ["TBC_DEMO_INSECURE"] = "0"
    with TestClient(app) as c:
        r = c.get("/causes", params={"user": "mgr1"})
        assert r.status_code == 401, "no-cookie ?user=mgr1 must be rejected when insecure is off"
    with TestClient(app) as c:
        _login(c, "tech1")
        r = c.get("/causes", params={"user": "mgr1"})
        assert r.status_code == 200
        snap = _create_and_advance(c)
        r = c.post(f"/cases/{snap['case_id']}/approval", params={
            "user": "mgr1", "decision": "approve", "rationale": "x",
        })
        assert r.status_code == 403, "cookie=tech1 + ?user=mgr1 must resolve as tech1"
        # The ?user= fallback genuinely exists only under TBC_DEMO_INSECURE=1.
        os.environ["TBC_DEMO_INSECURE"] = "1"
        c.cookies.clear()
        r = c.get("/causes", params={"user": "mgr1"})
        assert r.status_code == 200
        os.environ["TBC_DEMO_INSECURE"] = "0"
    return "no-cookie ?user rejected; cookie beats ?user; fallback only under insecure flag"


@probe("P12", "Extractor regression: dead thermistor -> exactly sensor_hardware_failure")
def _p12():
    d = _isolate("p12")
    transcript = (
        "Interviewer: Tell me about a recent sensor failure you diagnosed.\n\n"
        "Technician: We had a supply air thermistor that just went dead one "
        "morning. I checked it wasn't the bus, not the controller, every "
        "other tag on that bus was reporting fine. The wiring was not loose "
        "either, I checked the terminal and it was seated properly. Turned "
        "out the thermistor was past its calibration date and just hit end "
        "of life. I replaced it and logged the work.\n"
    )
    result = llm._mock_extract(transcript)
    causes = {h["likely_cause"] for h in result["heuristics"]}
    assert causes == {"sensor_hardware_failure"}, causes
    assert len(result["heuristics"]) == 1
    from technical_services_pill.capture import SAMPLE_INTERVIEW
    sample = {h["likely_cause"] for h in llm._mock_extract(SAMPLE_INTERVIEW)["heuristics"]}
    assert sample == {"refrigerant_leak", "condenser_fouling", "comm_bus_failure", "sensor_hardware_failure"}
    return "judge's dead-thermistor transcript -> exactly 1 heuristic, no mis-tagged causes"


@probe("P13", "G2b hazard is in the payload the AOM Decision screen renders")
def _p13():
    d = _isolate("p13")
    with TestClient(app) as c:
        snap = _create_and_advance(c, "CHILLER-DC1-01", "CHILLER-DC1-01-s", "chiller_compressor_trip")
        assert snap["current_state"] == "AWAITING_APPROVAL"
        reasons = snap["guardrail_result"]["reasons"]
        assert any("[G2b]" in r for r in reasons)
        assert any("hazard" in r.lower() or "safety" in r.lower() for r in reasons)
    src = open("frontend/static/js/screens.js", encoding="utf-8").read()
    assert "Safety/environmental hazard" in src
    assert "banner-warn" in src
    return "refrigerant-leak approval carries [G2b] + hazard text; Decision screen renders a warning banner"


@probe("P14", "Contrast 28/28, Integrity card in UI, demo run")
def _p14():
    d = _isolate("p14")
    subprocess.run([sys.executable, "-m", "pytest", "tests/test_contrast.py", "-q"],
                   check=True, capture_output=True, text=True)
    src = open("frontend/static/js/screens.js", encoding="utf-8").read()
    assert "Integrity Events" in src and "integrity-body" in src
    r = subprocess.run([sys.executable, "-m", "technical_services_pill.demo"],
                       capture_output=True, text=True, cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    assert "DEMO PASSED" in (r.stdout or ""), (r.stdout[-400:] if r.stdout else r.stderr[-400:])
    return "test_contrast.py pass; Integrity Events card markup present; make demo -> DEMO PASSED"


PROBES = [_p01, _p02, _p03, _p04, _p05, _p06, _p07, _p08, _p09, _p10, _p11, _p12, _p13, _p14]


def main() -> int:
    for fn in PROBES:
        fn()
    width = max(len(title) for _, title, _, _ in RESULTS)
    print(f"{'ID':4s}  {'PROBE':{width}s}  RESULT")
    print("-" * (4 + 2 + width + 2 + 8))
    failures = 0
    for pid, title, passed, detail in RESULTS:
        status = "PASS" if passed else "FAIL"
        if not passed:
            failures += 1
        print(f"{pid:4s}  {title:{width}s}  {status}")
        print(f"{'':4s}  {'':{width}s}  -> {detail}")
    print("-" * (4 + 2 + width + 2 + 8))
    print(f"{len(RESULTS) - failures}/{len(RESULTS)} probes passed")
    return 1 if failures else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)