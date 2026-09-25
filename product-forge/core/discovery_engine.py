"""Discovery Engine - Multi-perspective ideation for vague user ideas.

Runs 3 agents with different perspectives to clarify:
- Product Analyst: What problem, who users, core job-to-be-done
- Business Analyst: Domain, business model, competitors
- UX Researcher: Personas, workflows, devices

Synthesizes answers into structured outputs.
"""
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


@dataclass
class DiscoveryQuestion:
    """A question from a discovery agent."""
    agent: str
    perspective: str
    question: str
    context: str = ""
    model_used: str = ""


@dataclass
class DiscoveryAnswer:
    """Answer to a discovery question."""
    question: str
    answer: str
    agent: str
    confidence: float = 0.8


@dataclass
class DiscoveryResult:
    """Complete discovery result."""
    project: str
    user_idea: str
    questions: List[DiscoveryQuestion] = field(default_factory=list)
    answers: List[DiscoveryAnswer] = field(default_factory=list)
    domain_analysis: str = ""
    stakeholder_map: str = ""
    user_personas: str = ""
    workflow_type: str = "normal-sdlc"  # normal-sdlc, dynamic, hybrid
    product_plan: str = ""
    created_at: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "project": self.project,
            "user_idea": self.user_idea,
            "questions": [{"agent": q.agent, "perspective": q.perspective, "question": q.question, "context": q.context} for q in self.questions],
            "answers": [{"question": a.question, "answer": a.answer, "agent": a.agent, "confidence": a.confidence} for a in self.answers],
            "domain_analysis": self.domain_analysis,
            "stakeholder_map": self.stakeholder_map,
            "user_personas": self.user_personas,
            "workflow_type": self.workflow_type,
            "product_plan": self.product_plan,
            "created_at": self.created_at,
        }


# Agent perspectives for discovery
DISCOVERY_AGENTS = {
    "product_analyst": {
        "name": "Product Analyst",
        "model_tier": "cheap",  # GPT-5 mini
        "perspective": "product_clarity",
        "questions": [
            "Who are the primary users of this product?",
            "What specific problem does this solve for them?",
            "What is the core job-to-be-done?",
            "What are the secondary jobs this product could address?",
            "What would make this product a must-have vs nice-to-have?",
            "What are the key success metrics?",
        ],
    },
    "business_analyst": {
        "name": "Business Analyst",
        "model_tier": "recommended",  # Claude Sonnet
        "perspective": "domain_business",
        "questions": [
            "What business domain does this belong to? (productivity, health, finance, education, etc.)",
            "What is the business model? (SaaS, marketplace, freemium, enterprise, etc.)",
            "Who are the main competitors or alternatives?",
            "What is the target market size and segment?",
            "What are the regulatory or compliance requirements?",
            "What is the go-to-market strategy?",
        ],
    },
    "ux_researcher": {
        "name": "UX Researcher",
        "model_tier": "cheap",  # Gemini Flash
        "perspective": "user_experience",
        "questions": [
            "What are the primary user personas?",
            "What is the main workflow the user will follow?",
            "What devices will users primarily use? (desktop, mobile, tablet)",
            "What are the pain points with existing solutions?",
            "What would delight the user beyond basic functionality?",
            "What accessibility requirements should we consider?",
        ],
    },
}


def generate_discovery_questions(user_idea: str, project: str) -> List[DiscoveryQuestion]:
    """Generate discovery questions from all 3 perspectives."""
    questions = []
    
    for agent_id, agent_config in DISCOVERY_AGENTS.items():
        for q_text in agent_config["questions"]:
            questions.append(DiscoveryQuestion(
                agent=agent_id,
                perspective=agent_config["perspective"],
                question=q_text,
                context=f"User idea: {user_idea}",
                model_used=agent_config["model_tier"],
            ))
    
    return questions


def synthesize_domain_analysis(answers: List[DiscoveryAnswer]) -> str:
    """Synthesize domain analysis from answers."""
    business_answers = [a for a in answers if a.agent == "business_analyst"]
    
    analysis = "## Domain Analysis\n\n"
    for answer in business_answers:
        analysis += f"**{answer.question}**\n{answer.answer}\n\n"
    
    return analysis


def synthesize_stakeholder_map(answers: List[DiscoveryAnswer]) -> str:
    """Synthesize stakeholder map from answers."""
    product_answers = [a for a in answers if a.agent == "product_analyst"]
    
    stakeholder_map = "## Stakeholder Map\n\n"
    for answer in product_answers:
        stakeholder_map += f"**{answer.question}**\n{answer.answer}\n\n"
    
    return stakeholder_map


def synthesize_user_personas(answers: List[DiscoveryAnswer]) -> str:
    """Synthesize user personas from answers."""
    ux_answers = [a for a in answers if a.agent == "ux_researcher"]
    
    personas = "## User Personas\n\n"
    for answer in ux_answers:
        personas += f"**{answer.question}**\n{answer.answer}\n\n"
    
    return personas


def determine_workflow_type(answers: List[DiscoveryAnswer]) -> str:
    """Determine workflow type based on complexity and uncertainty."""
    total_confidence = sum(a.confidence for a in answers) / len(answers) if answers else 0.5
    
    # Low confidence = more discovery needed = dynamic workflow
    if total_confidence < 0.6:
        return "dynamic"
    # Medium confidence = hybrid
    elif total_confidence < 0.8:
        return "hybrid"
    # High confidence = normal SDLC
    else:
        return "normal-sdlc"


def generate_product_plan(user_idea: str, answers: List[DiscoveryAnswer], 
                          domain_analysis: str, stakeholder_map: str, 
                          user_personas: str, workflow_type: str) -> str:
    """Generate comprehensive product plan from discovery results."""
    plan = f"""# Product Plan: {user_idea}

## Vision
{user_idea}

## Domain
{domain_analysis}

## Stakeholders
{stakeholder_map}

## User Personas
{user_personas}

## Workflow Type
{workflow_type.upper()}

## Discovery Answers

"""
    for answer in answers:
        plan += f"### {answer.question}\n{answer.answer}\n\n"
    
    plan += """## Next Steps
1. Review and refine product plan with stakeholders
2. Create detailed requirements document
3. Begin design phase
4. Start implementation

---
*Generated by Discovery Engine with 3 agent perspectives*
"""
    
    return plan


def synthesize_refined_idea(user_idea: str, answers: List[DiscoveryAnswer]) -> str:
    """A crisper brief: the original idea plus every recorded clarification.

    Deterministic and offline-safe (no LLM). Downstream stages consume this so the
    clarifications actually change Design / Architecture / Implement.
    """
    lines = ["# Refined Idea", "", "## Original Idea", "", (user_idea or "").strip(), ""]
    if answers:
        lines += ["## Clarifications", ""]
        for a in answers:
            lines.append(f"- **{a.question}**")
            lines.append(f"  - {a.answer}")
        lines.append("")
    else:
        lines += ["_No discovery clarifications were recorded._", ""]
    return "\n".join(lines)


def run_discovery(user_idea: str, project: str, products_dir: str = "products",
                  answers: Optional[List[DiscoveryAnswer]] = None) -> DiscoveryResult:
    """Run full discovery process and generate outputs.

    ``answers`` must be supplied by the caller (the interactive bridge, the
    discovery LLM agent, or the human proxy). Do NOT fabricate placeholder
    answers here — an unanswered discovery synthesizes empty sections on purpose.
    """
    result = DiscoveryResult(
        project=project,
        user_idea=user_idea,
        created_at=datetime.now().isoformat(),
    )

    # Generate questions
    result.questions = generate_discovery_questions(user_idea, project)

    # Answers come from the caller only.
    result.answers = list(answers or [])

    # Synthesize outputs
    result.domain_analysis = synthesize_domain_analysis(result.answers)
    result.stakeholder_map = synthesize_stakeholder_map(result.answers)
    result.user_personas = synthesize_user_personas(result.answers)
    result.workflow_type = determine_workflow_type(result.answers)
    
    # Generate product plan
    result.product_plan = generate_product_plan(
        user_idea, result.answers, result.domain_analysis,
        result.stakeholder_map, result.user_personas, result.workflow_type
    )
    
    # Save outputs
    project_dir = os.path.join(products_dir, project)
    os.makedirs(project_dir, exist_ok=True)
    docs_dir = os.path.join(project_dir, "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    # Save discovery result
    with open(os.path.join(project_dir, "discovery-result.json"), 'w', encoding='utf-8') as f:
        json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)
    
    # Save individual docs
    with open(os.path.join(docs_dir, "domain-analysis.md"), 'w', encoding='utf-8') as f:
        f.write(result.domain_analysis)
    
    with open(os.path.join(docs_dir, "stakeholder-map.md"), 'w', encoding='utf-8') as f:
        f.write(result.stakeholder_map)
    
    with open(os.path.join(docs_dir, "user-personas.md"), 'w', encoding='utf-8') as f:
        f.write(result.user_personas)
    
    with open(os.path.join(docs_dir, "product-plan.md"), 'w', encoding='utf-8') as f:
        f.write(result.product_plan)
    
    return result


def discovery_to_dict(result: DiscoveryResult) -> Dict:
    """Convert discovery result to dict for API responses."""
    return result.to_dict()


if __name__ == "__main__":
    # Test discovery engine
    result = run_discovery("Build a task management app", "test-discovery")
    print(f"Discovery completed for: {result.user_idea}")
    print(f"Workflow type: {result.workflow_type}")
    print(f"Questions generated: {len(result.questions)}")
    print(f"Answers generated: {len(result.answers)}")
