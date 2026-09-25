"""
Compliance Orchestrator (extracted from pipeline_executor - 1A.11).

Runs the full post-execution compliance suite for an agent:
  1. rule-based ComplianceChecker report
  2. knowledge/guideline compliance
  3. code-quality gate (no stubs/mocks)
  4. stack compliance (unrequested framework imports)
  5. real verification (validate agent only)
  6. compliance action handling (retry / escalate / approve)

Returns a plain dict so the caller (execute_agent) owns execution state.
"""
import json
import os
from typing import Any, Callable, Dict, List, Optional


class ComplianceOrchestrator:
    def __init__(self, products_dir: str, project: str, project_dir: str,
                 knowledge_compliance=None, compliance_handler=None,
                 stack_compliance: Optional[Callable[[], List[Dict]]] = None,
                 tech_stack_hints: Optional[List[str]] = None,
                 llm_verify: Optional[Callable[..., Optional[Dict]]] = None,
                 use_test_suites: bool = False,
                 multi_review: Optional[Callable[..., Optional[Dict]]] = None,
                 test_cycle: Optional[Callable[..., Optional[Dict]]] = None,
                 coverage: Optional[Callable[[], Optional[Dict]]] = None,
                 enforce_coverage: bool = False,
                 spec_review: Optional[Callable[..., Optional[Dict]]] = None,
                 qa_gate: Optional[Callable[..., Optional[Dict]]] = None):
        self.products_dir = products_dir
        self.project = project
        self.project_dir = project_dir
        self.knowledge_compliance = knowledge_compliance
        self.compliance_handler = compliance_handler
        self.stack_compliance = stack_compliance
        self.tech_stack_hints = tech_stack_hints or []
        self.llm_verify = llm_verify
        self.use_test_suites = use_test_suites
        self.multi_review = multi_review
        self.test_cycle = test_cycle
        self.coverage = coverage
        self.enforce_coverage = enforce_coverage
        self.spec_review = spec_review
        self.qa_gate = qa_gate

    def run_rule_compliance(self, agent_id: str, stage_id: str) -> Dict:
        """Rule-based compliance check; writes compliance/<agent>-compliance.json."""
        try:
            from core.compliance_check import ComplianceChecker

            checker = ComplianceChecker(products_dir=self.products_dir, project=self.project)
            report = checker.check_agent(agent_id)

            if hasattr(report, "to_dict"):
                report_dict = report.to_dict()
            elif hasattr(report, "__dict__"):
                report_dict = report.__dict__
            else:
                report_dict = report

            compliance_dir = os.path.join(self.project_dir, "compliance")
            os.makedirs(compliance_dir, exist_ok=True)
            report_file = os.path.join(compliance_dir, f"{agent_id}-compliance.json")
            with open(report_file, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, ensure_ascii=False)

            passed = report_dict.get("overall_status", "unknown") == "pass"
            # No checks defined for this agent -> not a failure.
            _summary = report_dict.get("summary") or {}
            if not passed and int(_summary.get("total", 0) or 0) == 0:
                passed = True
            return {"passed": passed, "report": report_dict}
        except Exception as e:
            print(f"[PipelineExecutor] Compliance check error: {e}")
            return {"error": str(e), "passed": False}

    def run(self, agent_id: str, stage_id: str, artifacts: List[str],
            auto_approve: bool = False,
            tech_stack_hints: Optional[List[str]] = None) -> Dict:
        """Run the full suite. Returns a state-free result bundle."""
        hints = tech_stack_hints if tech_stack_hints is not None else self.tech_stack_hints
        result = self.run_rule_compliance(agent_id, stage_id)
        report = result.get("report", result)
        passed = result.get("passed", False)

        # 11b. Knowledge-based compliance
        if self.knowledge_compliance is not None:
            try:
                knowledge_result = self.knowledge_compliance.check_agent_compliance(
                    agent_id=agent_id,
                    stage_id=stage_id,
                    project=self.project,
                    artifact_paths=artifacts,
                )
                report["knowledge_compliance"] = knowledge_result.to_dict()
                if knowledge_result.violations:
                    result["violations"] = [
                        v.to_dict() if hasattr(v, "to_dict") else v
                        for v in knowledge_result.violations
                    ]
                    result["passed"] = knowledge_result.passed
                    passed = knowledge_result.passed
            except Exception as e:
                print(f"[KnowledgeCompliance] Error: {e}")

        # 11b2a. Code-quality gate (no stubs/mocks)
        try:
            from core.code_quality_gate import gate_agent_output
            gate = gate_agent_output(agent_id, artifacts, self.project_dir)
            report["code_quality_gate"] = gate
            if not gate.get("passed", True):
                findings = [{"id": f"stub::{f['file']}", "severity": "high",
                             "detail": f"{f['pattern']} in {f['file']}"}
                            for f in gate.get("findings", [])]
                if not isinstance(result.get("violations"), list):
                    result["violations"] = []
                result["violations"].extend(findings)
                result["passed"] = False
                passed = False
                print(f"  [GATE] {agent_id}: {len(gate['findings'])} stub/mock finding(s)")
        except Exception as e:
            print(f"[CodeQualityGate] {e}")

        # 11b2b. Stack compliance
        if self.stack_compliance is not None:
            try:
                stack_viol = self.stack_compliance()
                if stack_viol:
                    report["stack_compliance"] = stack_viol
                    if not isinstance(result.get("violations"), list):
                        result["violations"] = []
                    result["violations"].extend(
                        [{"id": f"stack::{v['file']}", "severity": "high",
                          "detail": f"unrequested framework '{v['framework']}' in {v['file']}"}
                         for v in stack_viol])
                    result["passed"] = False
                    passed = False
                    print(f"  [STACK] {agent_id}: {len(stack_viol)} unrequested framework import(s)")
            except Exception as e:
                print(f"[StackCompliance] {e}")

        # 11b2c. Real verification (validate agent only)
        if agent_id == "validate":
            try:
                from core.verification_runner import run_verification
                ver = run_verification(self.project_dir, hints,
                                       stage_id=stage_id, use_suites=self.use_test_suites)
                report["verification"] = ver
                if ver.get("ran"):
                    print(f"  [VERIFY] {ver.get('detected')} verification ran; passed={ver.get('passed')}")
                    if not ver.get("passed"):
                        result["passed"] = False
                        passed = False
                else:
                    print("  [VERIFY] no project files detected; verification skipped")
            except Exception as e:
                print(f"[Verification] {e}")

        # 11c. LLM-as-verifier: a second model reviews the work (opt-in).
        if self.llm_verify is not None:
            try:
                llm_report = self.llm_verify(agent_id, stage_id, artifacts)
                if llm_report and llm_report.get("results"):
                    report["llm_verification"] = llm_report
                    high_conf = [r for r in llm_report.get("results", [])
                                 if not r.get("passed") and r.get("confidence", 0.0) >= 0.7]
                    if high_conf:
                        if not isinstance(result.get("violations"), list):
                            result["violations"] = []
                        result["violations"].extend(
                            [{"id": f"llm::{r.get('check_name')}", "severity": "medium",
                              "detail": (r.get("reasoning") or "")[:200]} for r in high_conf])
                        result["passed"] = False
                        passed = False
                        print(f"  [LLM-VERIFY] {agent_id}: {len(high_conf)} high-confidence failure(s)")
                    else:
                        print(f"  [LLM-VERIFY] {agent_id}: passed "
                              f"({llm_report.get('pass_count')}/{llm_report.get('total')})")
            except Exception as e:
                print(f"[LLMVerifier] {e}")

        # 11d. Multi-model review for design/architecture (opt-in).
        if self.multi_review is not None:
            try:
                mr = self.multi_review(agent_id, stage_id, artifacts)
                if mr:
                    report["multi_model_review"] = mr
                    if not mr.get("passed"):
                        if not isinstance(result.get("violations"), list):
                            result["violations"] = []
                        result["violations"].extend(
                            [{"id": "multi_review", "severity": "medium", "detail": str(i)[:200]}
                             for i in (mr.get("issues") or [])])
                        result["passed"] = False
                        passed = False
                        print(f"  [MULTI-REVIEW] {agent_id}: consensus {mr.get('consensus')} -> FAIL")
                    else:
                        print(f"  [MULTI-REVIEW] {agent_id}: consensus {mr.get('consensus')} -> PASS")
            except Exception as e:
                print(f"[MultiReview] {e}")

        # 11e. Output completeness checklist (generic; essential fails, recommended warns)
        try:
            from core.output_checklist import has_checklist, check as check_output
            if has_checklist(agent_id):
                chk = check_output(agent_id, artifacts)
                if chk.get("had_content"):
                    report["output_completeness"] = chk
                    ess = chk.get("essential_missing") or []
                    rec = chk.get("recommended_missing") or []
                    if ess:
                        if not isinstance(result.get("violations"), list):
                            result["violations"] = []
                        result["violations"].extend(
                            [{"id": f"{agent_id}::{m}", "severity": "high",
                              "detail": f"missing required section: {m}"} for m in ess])
                        result["passed"] = False
                        passed = False
                        print(f"  [CHECKLIST] {agent_id}: missing ESSENTIAL sections {ess}")
                    else:
                        print(f"  [CHECKLIST] {agent_id}: essential complete "
                              f"({len(chk['present'])}/{chk['total']} sections)"
                              + (f"; recommended missing: {rec}" if rec else ""))
                    if rec:
                        report["output_recommended_missing"] = rec
        except Exception as e:
            print(f"[OutputChecklist] {e}")

        # 11f. Test-framework cycle (functional/NFR/install/etc.) for validate.
        if agent_id == "validate" and self.test_cycle is not None:
            try:
                tc = self.test_cycle(stage_id)
                if tc:
                    report["test_cycle"] = tc
                    if tc.get("failed", 0) > 0:
                        result["passed"] = False
                        passed = False
                        print(f"  [TEST-CYCLE] {tc.get('failed')} failed test(s); "
                              f"cycle={tc.get('cycle_id')}")
                    else:
                        print(f"  [TEST-CYCLE] {tc.get('passed')}/{tc.get('total')} passed "
                              f"(cycle={tc.get('cycle_id')})")
            except Exception as e:
                print(f"[TestCycle] {e}")

        # 11h. Requirement traceability: FR/NFR ids referenced by the tests.
        if agent_id == "validate" and self.coverage is not None:
            try:
                cov = self.coverage()
                if cov:
                    report["requirement_coverage"] = cov
                    missing = list(cov.get("fr_missing") or []) + list(cov.get("missing") or [])
                    if missing:
                        print(f"  [COVERAGE] untested requirement ids: {missing[:10]}"
                              + (" ..." if len(missing) > 10 else ""))
                        if self.enforce_coverage:
                            result["passed"] = False
                            passed = False
                            if not isinstance(result.get("violations"), list):
                                result["violations"] = []
                            result["violations"].extend(
                                [{"id": f"coverage::{m}", "severity": "medium",
                                  "detail": f"requirement {m} has no referencing test"}
                                 for m in missing[:20]])
                    else:
                        print(f"  [COVERAGE] FR {cov.get('fr_covered')}/{cov.get('fr_total')}, "
                              f"NFR {cov.get('covered')}/{cov.get('total')}")
            except Exception as e:
                print(f"[Coverage] {e}")

        # 11i. QA Spec Review gate (stage 3a): block on any blocking finding.
        if agent_id == "validate" and str(stage_id) == "3a" and self.spec_review is not None:
            try:
                sr = self.spec_review(stage_id)
                if sr:
                    report["spec_review"] = sr.get("summary", {})
                    blk = (sr.get("summary") or {}).get("blocking_open", 0)
                    opt = (sr.get("summary") or {}).get("optional_open", 0)
                    if blk:
                        result["passed"] = False
                        passed = False
                        if not isinstance(result.get("violations"), list):
                            result["violations"] = []
                        owners = sorted({f["owner"] for r in sr.get("reviews", [])
                                         for f in r.get("findings", [])
                                         if f["class"] == "BLOCKING"})
                        result["violations"].append({
                            "id": "spec_review", "severity": "high",
                            "detail": f"{blk} blocking QA spec finding(s); revise: {', '.join(owners)}"})
                        result["retry_feedback"] = (
                            f"QA spec review found {blk} blocking issue(s). "
                            f"Artifacts to revise (owner agents): {', '.join(owners)}.")
                        print(f"  [SPEC-REVIEW] {blk} blocking finding(s); owners: {owners}")
                    else:
                        print(f"  [SPEC-REVIEW] approved"
                              + (f" with {opt} optional finding(s)" if opt else ""))
            except Exception as e:
                print(f"[SpecReview] {e}")

        # 11j. QA Go/No-Go gate (stage 10a): NO-GO blocks release.
        if agent_id == "validate" and str(stage_id) == "10a" and self.qa_gate is not None:
            try:
                gng = self.qa_gate(stage_id)
                if gng:
                    report["go_no_go"] = {"decision": gng.get("decision"),
                                          "qir": gng.get("qir"),
                                          "matrix": gng.get("matrix")}
                    decision = gng.get("decision")
                    print(f"  [GO/NO-GO] {decision} (QIR {gng.get('qir', {}).get('number')})")
                    if decision == "NO-GO":
                        override = False
                        try:
                            pj = os.path.join(self.project_dir, "project.json")
                            if os.path.exists(pj):
                                with open(pj, encoding="utf-8") as f:
                                    override = bool((json.load(f) or {}).get("qa", {}).get("override_gonogo"))
                        except Exception:
                            override = False
                        if not isinstance(result.get("violations"), list):
                            result["violations"] = []
                        if override:
                            result["violations"].append({
                                "id": "go_no_go_overridden", "severity": "medium",
                                "detail": "QA Go/No-Go NO-GO overridden by HIL (qa.override_gonogo). "
                                          + "; ".join(gng.get("rationale", [])[:3])})
                            print("  [GO/NO-GO] NO-GO overridden by HIL (qa.override_gonogo)")
                        else:
                            result["passed"] = False
                            passed = False
                            result["violations"].append({
                                "id": "go_no_go", "severity": "high",
                                "detail": "QA Go/No-Go = NO-GO: " + "; ".join(gng.get("rationale", [])[:5])})
            except Exception as e:
                print(f"[GoNoGo] {e}")

        # 11g. Compliance actions (retry / approve / escalate)
        action_dict: Optional[Dict] = None
        blocking_action: Optional[str] = None
        reason = ""
        feedback = ""
        if self.compliance_handler is not None:
            try:
                compliance_action = self.compliance_handler.handle_compliance_result(
                    agent_id=agent_id,
                    stage_id=stage_id,
                    compliance_result=result,
                    artifacts=artifacts,
                    auto_approve=auto_approve,
                )
                action_dict = compliance_action.to_dict()
                blocking_action = compliance_action.action
                reason = compliance_action.reason
                feedback = compliance_action.feedback_prompt
            except Exception as e:
                print(f"[ComplianceAction] Error: {e}")

        return {
            "execution_report": report,
            "compliance_result": result,
            "passed": passed,
            "action": action_dict,
            "blocking_action": blocking_action,
            "reason": reason,
            "feedback": feedback,
        }
