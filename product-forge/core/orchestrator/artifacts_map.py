"""
Semantic artifact map (re-run impact + context assembly).

Maps **semantic input/output ids** (e.g. `design_spec`, `component_plan`) to the
**agent(s) that produce them**, so we can:
  - assemble an agent's context from the right producer artifacts, and
  - invalidate exactly the agents/stages that consume a re-run agent's outputs.

Derived from AgentSpec.outputs / allowed_inputs when available, with a static
fallback so it works even before specs carry inputs/outputs.
"""
from typing import Dict, List, Optional, Set

# semantic id -> producing agent ids (fallback / seed)
STATIC_PRODUCERS: Dict[str, List[str]] = {
    "product_spec": ["ideation", "discovery"],
    "requirement": ["ideation", "discovery"],
    "design_spec": ["design", "product-design-spec"],
    "design_tokens": ["ux-ia"],
    "ux_spec": ["ux-ia"],
    "component_plan": ["architect"],
    "api_contract": ["architect", "implement-api"],
    "source_diff": ["implement", "implement-api", "implement-db", "implement-logic",
                    "implement-ui", "devops", "fix"],
    "test_results": ["validate"],
    "build_config": ["devops"],
    "deploy_config": ["devops"],
    "screenshot": ["visual_qa"],
    "component_tree": ["design_critic"],
    # Phase 1.5 (Business, Market & Monetization) + Phase 7 (Operate, Grow & Engage)
    "business_brief": ["product-owner"],
    "market_analysis": ["researcher"],
    "monetization": ["pricing-strategist"],
    "gtm_plan": ["marketing"],
    "growth_plan": ["growth"],
    "sales_playbook": ["sales-crm"],
    "customer_success_playbook": ["customer-success"],
    "social_media_plan": ["community-social"],
    "legal_compliance": ["legal-privacy"],
    "analytics_plan": ["product-analytics"],
    "ops_report": ["observer"],
    "knowledge_index": [],
    "project_state": [],
    "budget_state": [],
    "all_artifacts_metadata": [],
}


def _spec_inputs_outputs(specs: Optional[Dict]):
    ins: Dict[str, List[str]] = {}
    outs: Dict[str, List[str]] = {}
    if specs:
        for aid, spec in specs.items():
            ins[aid] = list(getattr(spec, "allowed_inputs", []) or [])
            outs[aid] = list(getattr(spec, "outputs", []) or [])
    return ins, outs


def producer_map(specs: Optional[Dict] = None) -> Dict[str, List[str]]:
    """semantic id -> producers (static ∪ spec.outputs for all input ids)."""
    m: Dict[str, Set[str]] = {k: set(v) for k, v in STATIC_PRODUCERS.items()}
    _, outs = _spec_inputs_outputs(specs)
    for aid, olist in outs.items():
        for oid in olist:
            m.setdefault(oid, set()).add(aid)
    return {k: sorted(v) for k, v in m.items()}


def allowed_producer_agents(allowed_inputs: List[str], specs: Optional[Dict] = None) -> Set[str]:
    """Agents whose outputs feed the given semantic inputs (for context selection)."""
    m = producer_map(specs)
    out: Set[str] = set()
    for i in (allowed_inputs or []):
        out.update(m.get(i, []))
    return out


def outputs_of(agent: str, specs: Optional[Dict] = None) -> Set[str]:
    """Semantic output ids produced by an agent."""
    _, outs = _spec_inputs_outputs(specs)
    ids = set(outs.get(agent, []))
    for oid, prods in STATIC_PRODUCERS.items():
        if agent in prods:
            ids.add(oid)
    return ids


def consumers_of(agent: str, specs: Optional[Dict] = None) -> Set[str]:
    """Agents whose inputs include any output of `agent` (direct consumers)."""
    m = producer_map(specs)
    outs = outputs_of(agent, specs)
    ins, spec_outs = _spec_inputs_outputs(specs)
    # agent inputs = spec.allowed_inputs; if absent, infer from map (any id they consume)
    consumers: Set[str] = set()
    for other, inps in ins.items():
        if other == agent:
            continue
        if set(inps) & outs:
            consumers.add(other)
    # also include agents whose STATIC producer relationship implies consumption
    for oid in outs:
        for other, inps in ins.items():
            if oid in inps and other != agent:
                consumers.add(other)
    return consumers


def consumers_transitive(agents: List[str], specs: Optional[Dict] = None) -> Set[str]:
    """Transitive agent consumers of the given agents' outputs."""
    seen: Set[str] = set()
    frontier = list(agents)
    while frontier:
        cur = frontier.pop()
        for nxt in consumers_of(cur, specs):
            if nxt not in seen and nxt not in agents:
                seen.add(nxt)
                frontier.append(nxt)
    return seen
