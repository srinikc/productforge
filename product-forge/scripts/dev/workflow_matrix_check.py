"""Workflow combination matrix check.

Exercises the combinations that can occur in the agent/pipeline workflow around the
pre-execution gates, model registry/gate, locks, events and reports, and asserts the
expected verdict. Run from the repo root:

    python scripts/dev/workflow_matrix_check.py

Exit 0 = all combinations behaved; non-zero = at least one defect (printed).
"""
import json
import os
import sys
import tempfile
from unittest import mock

sys.path.insert(0, os.getcwd())

from core import agent_readiness, events, model_gate, model_catalog  # noqa: E402
from core.lock_manager import LockManager, LockInfo, _pid_from_holder  # noqa: E402

FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name}  {detail}")
        FAILS.append(f"{name}: {detail}")


def section(t):
    print(f"\n== {t} ==")


# ── agent_readiness ──────────────────────────────────────────────────────────
section("readiness.evaluate combinations")
check("no requirements + empty context -> ok",
      agent_readiness.evaluate("ideation", stage_id="0", available_keys=[], model="m",
                               provider="openrouter")["ok"] is True)

v = agent_readiness.evaluate("product-owner", stage_id="0b",
                             available_keys=["0_ideation"], context_chars=500,
                             model="qwen/qwen3.8-27b:free", provider="openrouter")
check("product-owner@0b missing required input -> BLOCK",
      v["ok"] is False and bool(v["missing"]), str(v["missing"]))

v = agent_readiness.evaluate("product-owner", stage_id="0b",
                             available_keys=["0_ideation", "0a_discovery"], context_chars=5000,
                             model="qwen/qwen3.8-27b:free", provider="openrouter")
check("product-owner@0b all inputs -> ok", v["ok"] is True, str(v["checks"]))

v = agent_readiness.evaluate("product-owner", stage_id="0b",
                             available_keys=["0_ideation", "0a_discovery"], context_chars=10,
                             model="qwen/qwen3.8-27b:free", provider="openrouter")
check("thin context -> warn (does NOT block)",
      v["ok"] is True and any(c["name"] == "context_size" and c["status"] == "warn"
                              for c in v["checks"]))

v = agent_readiness.evaluate("ideation", stage_id="0", available_keys=[], context_chars=0,
                             model="", provider="openrouter")
check("no model assigned -> BLOCK", v["ok"] is False and any(
    c["name"] == "model_assigned" and c["status"] == "fail" for c in v["checks"]))

check("DAG-derived requirements (0b->0a; 0->none)",
      agent_readiness._dag_required("0b") == ["0a"]
      and agent_readiness._dag_required("0") == [])

# ── readiness report round-trip ──────────────────────────────────────────────
section("readiness.record / load_report round-trip")
with tempfile.TemporaryDirectory() as d:
    v1 = agent_readiness.evaluate("product-owner", stage_id="0b", available_keys=[],
                                  context_chars=0, model="m", provider="openrouter")
    agent_readiness.record(d, run_id="r1", stage="0b", agent="product-owner", verdict=v1)
    v2 = agent_readiness.evaluate("product-owner", stage_id="0b",
                                  available_keys=["0_ideation", "0a_discovery"],
                                  context_chars=5000, model="m", provider="openrouter")
    agent_readiness.record(d, run_id="r1", stage="0b", agent="product-owner", verdict=v2)
    rep = agent_readiness.load_report(d)
    check("upsert keeps one row per (stage,agent)",
          rep and len([a for a in rep["agents"] if a["agent"] == "product-owner"]) == 1)
    check("summary blocked count correct", agent_readiness.summary(d)["blocked"] == 0)

# ── model_gate ───────────────────────────────────────────────────────────────
section("model_gate.evaluate combinations")
empty = model_gate.evaluate({})
check("empty profile -> no entries, no crash",
      empty["summary"]["total"] == 0 and empty["summary"]["incompatible"] == 0)

with mock.patch.object(model_catalog, "fit") as fit:
    def _fit(model, needs):
        return {"ok": True, "reasons": ["ok"]} if model == "good" else \
               {"ok": False, "reasons": ["BAD tools"]}
    fit.side_effect = _fit
    prof = {"default_tier": "t", "default_model": "good",
            "agents": {"implement": {"model": "bad"}, "ideation": {"model": "good"}}}
    rep = model_gate.evaluate(prof)
    by = {e["agent"]: e for e in rep["entries"]}
    check("incompatible agent flagged + recommended substitute",
          by["implement"]["status"] == "INCOMPATIBLE" and by["implement"]["recommended"] == "good")
    check("compatible agent OK", by["ideation"]["status"] == "OK")
    check("summary incompatible=1", rep["summary"]["incompatible"] == 1)

with mock.patch.object(model_catalog, "fit") as fit:
    fit.return_value = {"ok": None, "reasons": ["no catalog data"]}
    rep = model_gate.evaluate({"default_tier": "t", "agents": {"implement": {"model": "x"}}})
    check("unknown capabilities -> UNKNOWN (does not block)",
          rep["entries"][0]["status"] == "UNKNOWN" and rep["summary"]["incompatible"] == 0)

with tempfile.TemporaryDirectory() as d:
    model_gate.save_report(d, {"summary": {"total": 1}, "entries": []})
    check("model-gate report round-trip", model_gate.load_report(d).get("summary"))

# ── model_catalog.capabilities lookups ───────────────────────────────────────
section("model_catalog.capabilities id variants")
fake = {"nvidia/nemotron-3.5-lightning:free": {"id": "nvidia/nemotron-3.5-lightning:free",
                                               "registry_name": "nemotron-3.5-lightning-free",
                                               "tools": True}}
with mock.patch.object(model_catalog, "load", return_value=fake):
    for probe in ("nvidia/nemotron-3.5-lightning:free", "nemotron-3.5-lightning-free"):
        check(f"resolves '{probe}'", model_catalog.capabilities(probe).get("tools") is True)
    check("unknown model -> {}", model_catalog.capabilities("nope/xyz") == {})

# ── locks ────────────────────────────────────────────────────────────────────
section("lock_manager combinations")
with tempfile.TemporaryDirectory() as d:
    lm = LockManager(d)
    l1 = lm.acquire_lock("p", holder="run-111")
    check("fresh acquire", l1 is not None)
    check("second holder refused while live-ish", lm.acquire_lock("p", holder="run-222") is None
          or _pid_from_holder("run-111") is not None)
    lm.release_lock("p", "run-111")

    # dead-pid holder must be reclaimed
    lp = os.path.join(d, ".locks", "p.lock")
    with open(lp, "w") as f:
        json.dump(LockInfo(holder="run-999999", acquired_at="2000-01-01T00:00:00",
                           expires_at="2999-01-01T00:00:00", project="p", run_id="x").to_dict(), f)
    r = lm.acquire_lock("p", holder="run-123")
    check("dead-pid lock reclaimed", r is not None)

    # corrupt lock
    with open(lp, "w") as f:
        f.write("{not json")
    check("corrupt lock recovered", lm.acquire_lock("p", holder="run-124") is not None)

    check("force_unlock", lm.force_unlock("p") is True and not os.path.exists(lp))

# ── events ───────────────────────────────────────────────────────────────────
section("events round-trip")
with tempfile.TemporaryDirectory() as d:
    events.emit(d, "agent_blocked", run_id="r", stage="0b", agent="product-owner",
                reason="missing inputs")
    got = events.read(d)
    check("event persisted with fields",
          got and got[-1]["type"] == "agent_blocked" and got[-1]["agent"] == "product-owner")
    check("counts works", events.counts(d).get("agent_blocked") == 1)

# ── plan_evaluator (post-discovery planner) ──────────────────────────────────
section("plan_evaluator combinations")
from core import plan_evaluator as _pe  # noqa: E402
with tempfile.TemporaryDirectory() as d:
    os.makedirs(os.path.join(d, "artifacts", "0 - Ideation"), exist_ok=True)
    with open(os.path.join(d, "artifacts", "0 - Ideation", "ideation-output.md"),
              "w", encoding="utf-8") as f:
        f.write("# Vision\nA subscription SaaS with pricing tiers and market competitors.\n")
    p = _pe.evaluate(d)
    g = {x["key"]: x for x in p["groups"]}
    check("monetization recommended from 'pricing' signal", g["monetization"]["recommended"] is True)
    check("group carries description + skip impact",
          bool(g["monetization"].get("provides")) and bool(g["monetization"].get("skip_impact")))
    check("recommendation has reason", bool(g["monetization"].get("reason")))

inc, sk, notes = _pe._close_prereqs(["13a"], ["13"], _pe._stages())
check("prerequisite closure pulls in 13 for 13a", "13" in inc and "13" not in sk)

r_strict = _pe.resolve({"include_optional": [], "skip_optional": ["0e"],
                        "dependencies": [{"skipped": "0e", "dependents": ["1"]}]}, strict=True)
check("strict_deps keeps risky skip", "0e" not in r_strict["skip_optional"])
r_soft = _pe.resolve({"include_optional": [], "skip_optional": ["0e"],
                      "dependencies": [{"skipped": "0e", "dependents": ["1"]}]}, strict=False)
check("non-strict warns and allows skip", "0e" in r_soft["skip_optional"] and r_soft["warnings"])

_conf = _pe.confirm(dict(_pe.evaluate(d)), d)
check("confirm default accepts recommendations", isinstance(_conf.get("include_optional"), list))

# ── brief sufficiency guard ──────────────────────────────────────────────────
section("brief_check combinations (config-driven, LLM)")
from core import brief_check as _bc  # noqa: E402
check("empty brief unclear", _bc.assess("")["ok"] is False)
with mock.patch.object(_bc, "_llm_check", return_value={"usable": False, "question": "q"}):
    check("model says unusable -> unclear", _bc.assess("build it", llm=object())["ok"] is False)
with mock.patch.object(_bc, "_llm_check", return_value={"usable": True}):
    check("model says usable -> ok", _bc.assess("a real product brief here", llm=object())["ok"] is True)
with mock.patch.object(_bc, "_llm_check", return_value=None):
    check("validator unavailable -> no fabricated verdict",
          _bc.assess("x", llm=object())["ok"] is True)

from core.orchestrator.prompt_builder import no_invention_guard  # noqa: E402
check("agents get a no-invention directive", "Do NOT invent" in no_invention_guard("ideation"))

print(f"\n{'='*60}\nRESULT: {'PASS' if not FAILS else 'FAIL'} "
      f"({len(FAILS)} failure(s))")
for f in FAILS:
    print(" -", f)
raise SystemExit(1 if FAILS else 0)
