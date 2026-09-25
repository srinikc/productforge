# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Conversation & Idea Ingestion - Conversation Compiler

Two-pass extraction:
Pass 1: Extract ideas, requirements, decisions from conversation
Pass 2: Score confidence, deduplicate, adjudicate

Uses LLM APIs (Gemini/Claude) for extraction with retry logic.
"""

import os
import json
import time
import re
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field, asdict

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.conversation_models import (
    ConversationStore, Conversation, ConversationMessage,
    ExtractedIdea, ExtractedRequirement, ExtractedDecision,
    ChangePackage, ChangeItem,
    ConversationStatus, IdeaStatus, RequirementType, ChangeType
)


# ─── Extraction Prompts ──────────────────────────────────────────

EXTRACTION_PROMPT = """Analyze this conversation and extract:

1. IDEAS - Main ideas, concepts, or proposals discussed
2. REQUIREMENTS - Functional and non-functional requirements
3. DECISIONS - Decisions made and their rationale
4. CONSTRAINTS - Any constraints or limitations mentioned
5. OPEN QUESTIONS - Unresolved questions or concerns

For each item, provide:
- title/description
- confidence (0.0-1.0)
- priority (high/medium/low)
- type (for requirements: functional/non-functional/constraint)

Return as JSON:
{
  "ideas": [
    {"title": "...", "description": "...", "confidence": 0.9}
  ],
  "requirements": [
    {"text": "...", "type": "functional", "priority": "high", "confidence": 0.85}
  ],
  "decisions": [
    {"decision": "...", "rationale": "...", "confidence": 0.9}
  ],
  "constraints": [
    {"text": "...", "confidence": 0.8}
  ],
  "open_questions": [
    {"question": "...", "confidence": 0.7}
  ]
}"""

ADJUDICATION_PROMPT = """Review these extracted items and:
1. Remove duplicates
2. Adjust confidence scores based on context
3. Identify conflicts between items
4. Mark items as: accepted, proposed, or rejected

Return as JSON with the same structure, adding "status" field to each item."""


# ─── LLM Client Stubs ───────────────────────────────────────────

class LLMClient:
    """Base class for LLM API calls."""

    def extract(self, conversation_text: str, prompt: str) -> Dict[str, Any]:
        raise NotImplementedError


class GeminiClient(LLMClient):
    """Gemini API client for extraction."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        # Overridable; the previous hardcoded "gemini-2.0-flash" was retired (404).
        self.model = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

    def extract(self, conversation_text: str, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback_extract(conversation_text)

        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(
                f"{prompt}\n\nConversation:\n{conversation_text}"
            )
            return self._parse_response(response.text)
        except Exception as e:
            print(f"[GeminiClient] Error: {e}")
            return self._fallback_extract(conversation_text)

    def _parse_response(self, text: str) -> Dict[str, Any]:
        try:
            # Try to extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"ideas": [], "requirements": [], "decisions": [], "constraints": [], "open_questions": []}

    def _fallback_extract(self, text: str) -> Dict[str, Any]:
        """Fallback extraction when API is unavailable."""
        return {
            "ideas": [{"title": "Extracted from conversation", "description": text[:200], "confidence": 0.5}],
            "requirements": [],
            "decisions": [],
            "constraints": [],
            "open_questions": []
        }


class ClaudeClient(LLMClient):
    """Claude API client for extraction."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = "claude-3-5-sonnet-20241022"

    def extract(self, conversation_text: str, prompt: str) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback_extract(conversation_text)

        try:
            import anthropic
            client = anthropic.Anthropic(api_key=self.api_key)
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{"role": "user", "content": f"{prompt}\n\nConversation:\n{conversation_text}"}]
            )
            return self._parse_response(response.content[0].text)
        except Exception as e:
            print(f"[ClaudeClient] Error: {e}")
            return self._fallback_extract(conversation_text)

    def _parse_response(self, text: str) -> Dict[str, Any]:
        try:
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass
        return {"ideas": [], "requirements": [], "decisions": [], "constraints": [], "open_questions": []}

    def _fallback_extract(self, text: str) -> Dict[str, Any]:
        """Fallback extraction when API is unavailable."""
        return {
            "ideas": [{"title": "Extracted from conversation", "description": text[:200], "confidence": 0.5}],
            "requirements": [],
            "decisions": [],
            "constraints": [],
            "open_questions": []
        }


# ─── Conversation Compiler ───────────────────────────────────────

class ConversationCompiler:
    """Compiles conversations into structured knowledge."""

    def __init__(self, primary_client: str = "gemini"):
        self.store = ConversationStore()
        self.primary_client = primary_client
        self.gemini = GeminiClient()
        self.claude = ClaudeClient()
        self.max_retries = 5
        self.retry_delays = [5, 30, 120, 600, 3600]  # seconds

    def get_client(self, client_name: str = None) -> LLMClient:
        """Get LLM client by name."""
        name = client_name or self.primary_client
        if name == "claude":
            return self.claude
        return self.gemini

    def compile_conversation(self, conv_id: str) -> bool:
        """Compile a conversation into structured knowledge."""
        conv = self.store.get_conversation(conv_id)
        if not conv:
            print(f"[Compiler] Conversation {conv_id} not found")
            return False

        # Mark as compiling
        conv.status = ConversationStatus.COMPILING.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        try:
            # Build conversation text
            conv_text = self._build_conversation_text(conv)

            # Pass 1: Extract
            extracted = self._extract(conv_text)

            # Pass 2: Adjudicate
            adjudicated = self._adjudicate(extracted)

            # Convert to domain objects
            ideas = self._to_ideas(conv.id, adjudicated.get("ideas", []))
            requirements = self._to_requirements(conv.id, adjudicated.get("requirements", []))
            decisions = self._to_decisions(conv.id, adjudicated.get("decisions", []))

            # Update conversation
            conv.extracted_ideas = ideas
            conv.extracted_requirements = requirements
            conv.extracted_decisions = decisions
            conv.compiled_summary = self._generate_summary(conv, ideas, requirements, decisions)
            conv.status = ConversationStatus.COMPILED.value
            conv.compiled_at = datetime.utcnow().isoformat()
            conv.updated_at = datetime.utcnow().isoformat()
            self.store.update_conversation(conv)

            # Store individual items
            for idea in ideas:
                self.store.save_idea(idea)
            for req in requirements:
                self.store.save_requirement(req)
            for dec in decisions:
                self.store.save_decision(dec)

            print(f"[Compiler] Compiled conversation {conv_id}: {len(ideas)} ideas, {len(requirements)} requirements, {len(decisions)} decisions")
            return True

        except Exception as e:
            print(f"[Compiler] Compilation failed for {conv_id}: {e}")
            conv.status = ConversationStatus.COMPILATION_FAILED.value
            conv.error_message = str(e)
            conv.retry_count += 1
            if conv.retry_count < conv.max_retries:
                delay = self.retry_delays[min(conv.retry_count - 1, len(self.retry_delays) - 1)]
                conv.next_retry_at = (datetime.utcnow().timestamp() + delay)
                conv.status = ConversationStatus.PENDING_COMPILATION.value
            conv.updated_at = datetime.utcnow().isoformat()
            self.store.update_conversation(conv)
            return False

    def retry_pending(self) -> int:
        """Retry pending compilations. Returns number of retries attempted."""
        pending = self.store.list_conversations(status=ConversationStatus.PENDING_COMPILATION.value)
        now = datetime.utcnow().timestamp()
        retried = 0

        for conv in pending:
            if conv.next_retry_at:
                retry_time = datetime.fromisoformat(conv.next_retry_at).timestamp() if isinstance(conv.next_retry_at, str) else conv.next_retry_at
                if now >= retry_time:
                    self.compile_conversation(conv.id)
                    retried += 1

        return retried

    def _build_conversation_text(self, conv: Conversation) -> str:
        """Build conversation text from messages."""
        parts = []
        for msg in conv.messages:
            parts.append(f"{msg.role.upper()}: {msg.content}")
        return "\n\n".join(parts)

    def _extract(self, conv_text: str) -> Dict[str, Any]:
        """Pass 1: Extract ideas, requirements, decisions."""
        client = self.get_client()
        return client.extract(conv_text, EXTRACTION_PROMPT)

    def _adjudicate(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Pass 2: Deduplicate, score, adjudicate."""
        # For now, do basic deduplication and scoring
        # In production, this would call the LLM again

        result = {
            "ideas": self._deduplicate_ideas(extracted.get("ideas", [])),
            "requirements": extracted.get("requirements", []),
            "decisions": extracted.get("decisions", []),
            "constraints": extracted.get("constraints", []),
            "open_questions": extracted.get("open_questions", [])
        }

        # Adjust confidence based on position in conversation
        # (later items tend to be more important)
        total_items = sum(len(v) for v in result.values() if isinstance(v, list))
        for i, idea in enumerate(result["ideas"]):
            position_boost = (i / max(total_items, 1)) * 0.1
            idea["confidence"] = min(1.0, idea.get("confidence", 0.5) + position_boost)

        return result

    def _deduplicate_ideas(self, ideas: List[Dict]) -> List[Dict]:
        """Remove duplicate ideas based on title similarity."""
        seen_titles = set()
        unique = []
        for idea in ideas:
            title = idea.get("title", "").lower().strip()
            if title not in seen_titles:
                seen_titles.add(title)
                unique.append(idea)
        return unique

    def _to_ideas(self, conv_id: str, ideas: List[Dict]) -> List[ExtractedIdea]:
        """Convert extracted ideas to domain objects."""
        return [
            ExtractedIdea(
                conversation_id=conv_id,
                title=idea.get("title", ""),
                description=idea.get("description", ""),
                confidence=idea.get("confidence", 0.5),
                status=IdeaStatus.NEW.value,
                metadata={"source": "compiler", "raw": idea}
            )
            for idea in ideas
        ]

    def _to_requirements(self, conv_id: str, reqs: List[Dict]) -> List[ExtractedRequirement]:
        """Convert extracted requirements to domain objects."""
        return [
            ExtractedRequirement(
                conversation_id=conv_id,
                requirement_text=req.get("text", ""),
                requirement_type=req.get("type", "functional"),
                priority=req.get("priority", "medium"),
                confidence=req.get("confidence", 0.5),
                status="proposed"
            )
            for req in reqs
        ]

    def _to_decisions(self, conv_id: str, decs: List[Dict]) -> List[ExtractedDecision]:
        """Convert extracted decisions to domain objects."""
        return [
            ExtractedDecision(
                conversation_id=conv_id,
                decision_text=dec.get("decision", ""),
                rationale=dec.get("rationale", ""),
                alternatives=dec.get("alternatives", []),
                confidence=dec.get("confidence", 0.5)
            )
            for dec in decs
        ]

    def _generate_summary(self, conv: Conversation, ideas: List[ExtractedIdea],
                          reqs: List[ExtractedRequirement],
                          decs: List[ExtractedDecision]) -> str:
        """Generate a summary of the compilation."""
        parts = [f"Conversation: {conv.title}"]
        parts.append(f"Source: {conv.source_platform}")
        parts.append(f"Intent: {conv.intent}")

        if ideas:
            parts.append(f"\nIdeas ({len(ideas)}):")
            for i in ideas[:5]:
                parts.append(f"  - {i.title} (confidence: {i.confidence:.0%})")

        if reqs:
            parts.append(f"\nRequirements ({len(reqs)}):")
            for r in reqs[:5]:
                parts.append(f"  - [{r.requirement_type}] {r.requirement_text}")

        if decs:
            parts.append(f"\nDecisions ({len(decs)}):")
            for d in decs[:5]:
                parts.append(f"  - {d.decision_text}")

        return "\n".join(parts)


# ─── CLI Entry Point ─────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python conversation_compiler.py <conversation_id>")
        sys.exit(1)

    conv_id = sys.argv[1]
    compiler = ConversationCompiler()
    success = compiler.compile_conversation(conv_id)
    if success:
        print(f"Successfully compiled conversation {conv_id}")
    else:
        print(f"Failed to compile conversation {conv_id}")
        sys.exit(1)
