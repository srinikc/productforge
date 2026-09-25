"""
Skill Contracts
Defines composable skill contracts separate from agent contracts.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class SkillInput:
    name: str
    type: str  # text, file, json, etc.
    required: bool = True
    description: str = ""

@dataclass
class SkillOutput:
    name: str
    type: str
    format: str  # markdown, json, code, etc.
    description: str = ""

@dataclass
class SkillCheck:
    check_id: str
    description: str
    verify: str  # auto, llm, human
    severity: str  # critical, high, medium, low

@dataclass
class SkillContract:
    skill_id: str
    name: str
    version: str
    description: str
    domain: str
    category: str  # reasoning, execution, analysis, creation
    inputs: List[SkillInput]
    outputs: List[SkillOutput]
    procedure: List[str]  # Steps to execute
    quality_checks: List[SkillCheck]
    dependencies: List[str]  # Other skill IDs
    tags: List[str]
    created_at: str
    updated_at: str

class SkillContractRegistry:
    def __init__(self, registry_dir: str = "pipeline/skills"):
        self.registry_dir = registry_dir
        os.makedirs(registry_dir, exist_ok=True)
        self.contracts: Dict[str, SkillContract] = {}
        self._load_all()
    
    def _load_all(self):
        """Load all skill contracts from disk."""
        if os.path.exists(self.registry_dir):
            for f in os.listdir(self.registry_dir):
                if f.endswith('.json'):
                    with open(os.path.join(self.registry_dir, f), 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                        contract = SkillContract(**data)
                        self.contracts[contract.skill_id] = contract
    
    def register(self, contract: SkillContract) -> bool:
        """Register a new skill contract."""
        try:
            file_path = os.path.join(self.registry_dir, f"{contract.skill_id}.json")
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(contract), f, indent=2, ensure_ascii=False)
            self.contracts[contract.skill_id] = contract
            return True
        except Exception as e:
            print(f"Error registering skill: {e}")
            return False
    
    def get(self, skill_id: str) -> Optional[SkillContract]:
        """Get a skill contract by ID."""
        return self.contracts.get(skill_id)
    
    def search(self, domain: str = None, category: str = None, tags: List[str] = None) -> List[SkillContract]:
        """Search for skill contracts."""
        results = []
        for contract in self.contracts.values():
            if domain and contract.domain != domain:
                continue
            if category and contract.category != category:
                continue
            if tags and not any(t in contract.tags for t in tags):
                continue
            results.append(contract)
        return results
    
    def get_dependencies(self, skill_id: str) -> List[SkillContract]:
        """Get all dependencies for a skill."""
        contract = self.contracts.get(skill_id)
        if not contract:
            return []
        deps = []
        for dep_id in contract.dependencies:
            dep = self.contracts.get(dep_id)
            if dep:
                deps.append(dep)
        return deps
    
    def compose(self, skill_ids: List[str]) -> List[SkillContract]:
        """Compose multiple skills into a workflow."""
        composed = []
        for skill_id in skill_ids:
            contract = self.contracts.get(skill_id)
            if contract:
                # Add dependencies first
                for dep in self.get_dependencies(skill_id):
                    if dep not in composed:
                        composed.append(dep)
                composed.append(contract)
        return composed