"""
Knowledge Compiler
Transforms raw knowledge into compiled, structured knowledge.
"""

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Any
from datetime import datetime

@dataclass
class Concept:
    concept_id: str
    name: str
    definition: str
    category: str  # fact, principle, pattern, rule
    confidence: float
    source: str
    timestamp: str
    related_concepts: List[str] = field(default_factory=list)

@dataclass
class Relationship:
    relationship_id: str
    source_concept: str
    target_concept: str
    relationship_type: str  # depends_on, contradicts, supports, extends
    confidence: float
    evidence: str

@dataclass
class CompiledKnowledge:
    knowledge_id: str
    domain: str
    concepts: List[Concept]
    relationships: List[Relationship]
    contradictions: List[Dict]
    last_compiled: str
    source_count: int

class KnowledgeCompiler:
    def __init__(self, knowledge_dir: str = "docs/knowledge"):
        self.knowledge_dir = knowledge_dir
        self.compiled_dir = os.path.join(knowledge_dir, "compiled")
        os.makedirs(self.compiled_dir, exist_ok=True)
    
    def compile_from_text(self, text: str, domain: str, source: str) -> CompiledKnowledge:
        """Compile knowledge from raw text."""
        concepts = self._extract_concepts(text, domain, source)
        relationships = self._extract_relationships(concepts)
        contradictions = self._detect_contradictions(concepts)
        
        knowledge = CompiledKnowledge(
            knowledge_id=f"kb-{domain}-{int(datetime.now().timestamp())}",
            domain=domain,
            concepts=concepts,
            relationships=relationships,
            contradictions=contradictions,
            last_compiled=datetime.now().isoformat(),
            source_count=1
        )
        
        self._store(knowledge)
        return knowledge
    
    def _extract_concepts(self, text: str, domain: str, source: str) -> List[Concept]:
        """Extract concepts from text."""
        concepts = []
        # Simple extraction - look for definitions, facts, patterns
        lines = text.split('\n')
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            # Look for definition patterns
            if ':' in line or 'is' in line.lower() or 'means' in line.lower():
                concept = Concept(
                    concept_id=f"concept-{domain}-{i}",
                    name=line[:50],
                    definition=line,
                    category="fact",
                    confidence=0.7,
                    source=source,
                    timestamp=datetime.now().isoformat()
                )
                concepts.append(concept)
        return concepts[:20]  # Limit to 20 concepts per text
    
    def _extract_relationships(self, concepts: List[Concept]) -> List[Relationship]:
        """Extract relationships between concepts."""
        relationships = []
        for i, c1 in enumerate(concepts):
            for j, c2 in enumerate(concepts):
                if i >= j:
                    continue
                # Check for related terms
                if any(word in c2.definition.lower() for word in c1.name.lower().split()):
                    rel = Relationship(
                        relationship_id=f"rel-{c1.concept_id}-{c2.concept_id}",
                        source_concept=c1.concept_id,
                        target_concept=c2.concept_id,
                        relationship_type="related_to",
                        confidence=0.6,
                        evidence=f"Term overlap between '{c1.name}' and '{c2.name}'"
                    )
                    relationships.append(rel)
        return relationships[:10]  # Limit
    
    def _detect_contradictions(self, concepts: List[Concept]) -> List[Dict]:
        """Detect potential contradictions between concepts."""
        contradictions = []
        # Simple contradiction detection - look for negation patterns
        for i, c1 in enumerate(concepts):
            for j, c2 in enumerate(concepts):
                if i >= j:
                    continue
                # Check for opposite meanings
                if self._are_contradictory(c1.definition, c2.definition):
                    contradictions.append({
                        "concept_1": c1.concept_id,
                        "concept_2": c2.concept_id,
                        "evidence_1": c1.definition,
                        "evidence_2": c2.definition
                    })
        return contradictions
    
    def _are_contradictory(self, text1: str, text2: str) -> bool:
        """Check if two texts contradict each other."""
        # Simple check for negation patterns
        negations = ["not", "never", "no", "cannot", "don't", "doesn't"]
        for neg in negations:
            if neg in text1.lower() and neg not in text2.lower():
                return True
            if neg in text2.lower() and neg not in text1.lower():
                return True
        return False
    
    def _store(self, knowledge: CompiledKnowledge):
        """Store compiled knowledge to disk."""
        file_path = os.path.join(self.compiled_dir, f"{knowledge.knowledge_id}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(knowledge), f, indent=2, ensure_ascii=False)
    
    def _deserialize_knowledge(self, data: Dict) -> CompiledKnowledge:
        """Deserialize JSON data back into CompiledKnowledge with proper nested types."""
        concepts = [Concept(**c) for c in data.get("concepts", [])]
        relationships = [Relationship(**r) for r in data.get("relationships", [])]
        contradictions = data.get("contradictions", [])
        return CompiledKnowledge(
            knowledge_id=data["knowledge_id"],
            domain=data["domain"],
            concepts=concepts,
            relationships=relationships,
            contradictions=contradictions,
            last_compiled=data["last_compiled"],
            source_count=data["source_count"]
        )
    
    def query(self, domain: str = None, concept_name: str = None) -> List[CompiledKnowledge]:
        """Query compiled knowledge."""
        results = []
        if os.path.exists(self.compiled_dir):
            for f in os.listdir(self.compiled_dir):
                if f.endswith('.json'):
                    with open(os.path.join(self.compiled_dir, f), 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                        kb = self._deserialize_knowledge(data)
                        if domain and kb.domain != domain:
                            continue
                        if concept_name and not any(concept_name.lower() in c.name.lower() for c in kb.concepts):
                            continue
                        results.append(kb)
        return results