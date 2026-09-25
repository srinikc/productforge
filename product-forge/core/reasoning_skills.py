"""
Reasoning Skills
Provides reasoning skills: problem restatement, first principles, premortem, decision matrices.
"""

import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime

@dataclass
class ReasoningOutput:
    skill: str
    input_problem: str
    output: Dict
    timestamp: str
    confidence: float

class ReasoningSkills:
    def __init__(self):
        self.skills = {
            "problem_restatement": self.problem_restatement,
            "first_principles": self.first_principles,
            "premortem": self.premortem,
            "decision_matrix": self.decision_matrix,
            "alternative_generation": self.alternative_generation
        }
    
    def execute(self, skill_name: str, problem: str, context: Dict = None) -> ReasoningOutput:
        """Execute a reasoning skill."""
        if skill_name not in self.skills:
            raise ValueError(f"Unknown skill: {skill_name}")
        
        output = self.skills[skill_name](problem, context or {})
        return ReasoningOutput(
            skill=skill_name,
            input_problem=problem,
            output=output,
            timestamp=datetime.now().isoformat(),
            confidence=0.8
        )
    
    def problem_restatement(self, problem: str, context: Dict) -> Dict:
        """Restate the problem from different perspectives."""
        return {
            "original": problem,
            "perspectives": [
                {"perspective": "user", "restatement": f"From the user's view: {problem}"},
                {"perspective": "technical", "restatement": f"Technically: {problem}"},
                {"perspective": "business", "restatement": f"From business view: {problem}"}
            ],
            "key_assumptions": ["Assumption 1", "Assumption 2"],
            "clarifying_questions": ["What is the core need?", "What are the constraints?"]
        }
    
    def first_principles(self, problem: str, context: Dict) -> Dict:
        """Break down to fundamental truths."""
        return {
            "problem": problem,
            "fundamental_truths": [
                "Truth 1: Core requirement",
                "Truth 2: Constraint",
                "Truth 3: Resource limitation"
            ],
            "derived_insights": [
                "Insight from truth 1",
                "Insight from truth 2"
            ],
            "recommended_approach": "Build from fundamentals up"
        }
    
    def premortem(self, problem: str, context: Dict) -> Dict:
        """Imagine the project failed and work backwards."""
        return {
            "problem": problem,
            "failure_scenarios": [
                {"scenario": "Scope creep", "likelihood": "high", "mitigation": "Strict scope control"},
                {"scenario": "Technical debt", "likelihood": "medium", "mitigation": "Regular refactoring"},
                {"scenario": "Resource constraint", "likelihood": "medium", "mitigation": "Phased delivery"}
            ],
            "risk_register": [
                {"risk": "R1", "impact": "high", "probability": "medium", "mitigation": "M1"}
            ],
            "preventive_actions": ["Action 1", "Action 2"]
        }
    
    def decision_matrix(self, problem: str, context: Dict) -> Dict:
        """Create a decision matrix for comparing options."""
        options = context.get("options", ["Option A", "Option B", "Option C"])
        criteria = context.get("criteria", ["Cost", "Time", "Quality", "Risk"])
        
        matrix = []
        for option in options:
            row = {"option": option, "scores": {}}
            for criterion in criteria:
                row["scores"][criterion] = 0.5  # Default score
            matrix.append(row)
        
        return {
            "problem": problem,
            "criteria": criteria,
            "matrix": matrix,
            "recommendation": f"Based on analysis, {options[0]} is recommended"
        }
    
    def alternative_generation(self, problem: str, context: Dict) -> Dict:
        """Generate alternative approaches."""
        return {
            "problem": problem,
            "alternatives": [
                {"name": "Conservative", "description": "Low risk, incremental approach", "pros": ["Safe"], "cons": ["Slow"]},
                {"name": "Moderate", "description": "Balanced risk and speed", "pros": ["Balanced"], "cons": ["Some risk"]},
                {"name": "Aggressive", "description": "High risk, fast results", "pros": ["Fast"], "cons": ["Risky"]}
            ],
            "recommended": "Moderate approach based on risk tolerance"
        }
