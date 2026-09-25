# DEPRECATED (2026-09-12): superseded by PipelineExecutor + core/orchestrator/*.
# Kept for reference; not part of the generic pipeline. See docs/UNWIRED-MODULES-TRIAGE.md.
"""
Conversation & Idea Ingestion - Database Models

PostgreSQL tables for storing conversations, extracted ideas,
requirements, decisions, and change packages from external sources
(ChatGPT, Gemini, Claude).
"""

import uuid
import os
import json
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────

class SourcePlatform(str, Enum):
    CHATGPT = "chatgpt"
    GEMINI = "gemini"
    CLAUDE = "claude"
    MANUAL = "manual"


class IntentType(str, Enum):
    SAVE_IDEA = "save_idea"
    NEW_PROJECT = "new_project"
    NEW_PROJECT_QUICK = "new_project_quick"
    MODIFY_PROJECT = "modify_project"
    ADD_CONTEXT = "add_context"
    PRODUCT_FORGE_IMPROVEMENT = "product_forge_improvement"
    # Deprecated alias: legacy deployments stored the string "factory_improvement".
    FACTORY_IMPROVEMENT = "product_forge_improvement"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str) and value == "factory_improvement":
            return cls.PRODUCT_FORGE_IMPROVEMENT
        return None


_LEGACY_INTENT_VALUES = {"factory_improvement": "product_forge_improvement"}


def canonical_intent(value):
    """Map legacy stored intent strings to their canonical Product Forge values."""
    if value is None:
        return value
    return _LEGACY_INTENT_VALUES.get(str(value), str(value))


class ConversationStatus(str, Enum):
    RECEIVED = "received"
    COMPILING = "compiling"
    COMPILED = "compiled"
    PENDING_COMPILATION = "pending_compilation"
    COMPILATION_FAILED = "compilation_failed"
    BUILDING = "building"
    BUILD_COMPLETE = "build_complete"
    BUILD_FAILED = "build_failed"
    REJECTED = "rejected"


class IdeaStatus(str, Enum):
    NEW = "new"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROMOTED = "promoted"


class RequirementType(str, Enum):
    FUNCTIONAL = "functional"
    NON_FUNCTIONAL = "non_functional"
    CONSTRAINT = "constraint"


class ChangeType(str, Enum):
    ADD = "add"
    MODIFY = "modify"
    REMOVE = "remove"


class ChangePackageStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    FAILED = "failed"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ImplementationStatus(str, Enum):
    PENDING = "pending"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    APPROVED = "approved"
    EXECUTING = "executing"
    EXECUTED = "executed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


# ─── Data Classes ─────────────────────────────────────────────────

@dataclass
class ConversationMessage:
    role: str  # "user" or "assistant"
    content: str
    message_order: int = 0
    extracted: bool = False


@dataclass
class ExtractedIdea:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    project_id: str = ""
    title: str = ""
    description: str = ""
    confidence: float = 0.0
    status: str = IdeaStatus.NEW.value
    source_messages: List[int] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ExtractedRequirement:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    idea_id: str = ""
    requirement_text: str = ""
    requirement_type: str = RequirementType.FUNCTIONAL.value
    priority: str = "medium"
    confidence: float = 0.0
    status: str = "proposed"
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ExtractedDecision:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    idea_id: str = ""
    decision_text: str = ""
    rationale: str = ""
    alternatives: List[str] = field(default_factory=list)
    confidence: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class ChangeItem:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    change_type: str = ChangeType.ADD.value  # add, modify, remove
    target: str = ""  # requirement, file, module, etc.
    target_id: str = ""
    description: str = ""
    priority: str = "medium"
    confidence: float = 0.0
    files_affected: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChangePackage:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    project_id: str = ""
    status: str = ChangePackageStatus.PENDING.value
    changes: List[ChangeItem] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    open_questions: List[str] = field(default_factory=list)
    impact_analysis: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    approved_at: str = ""
    applied_at: str = ""


@dataclass
class FileChange:
    """A single file change in an implementation plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    file_path: str = ""
    operation: str = "modify"  # "modify" | "create" | "delete"
    line_start: int = 0
    line_end: int = 0
    old_code: str = ""
    new_code: str = ""
    explanation: str = ""
    risk_level: str = RiskLevel.LOW.value
    selected: bool = True  # User can deselect this change


@dataclass
class ImplementationPlan:
    """Plan for implementing Product Forge improvements."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    file_changes: List[FileChange] = field(default_factory=list)
    risk_level: str = RiskLevel.LOW.value
    requires_tests: bool = True
    rollback_available: bool = True
    status: str = ImplementationStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    executed_at: str = ""
    rolled_back_at: str = ""


@dataclass
class ExecutionResult:
    """Result of executing an implementation plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    plan_id: str = ""
    conversation_id: str = ""
    files_modified: List[str] = field(default_factory=list)
    tests_passed: bool = False
    test_output: str = ""
    syntax_valid: bool = True
    success: bool = False
    rolled_back: bool = False
    error_message: str = ""
    backup_paths: List[str] = field(default_factory=list)
    executed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


@dataclass
class Conversation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_platform: str = SourcePlatform.MANUAL.value
    source_conversation_id: str = ""
    intent: str = IntentType.SAVE_IDEA.value
    target_project_id: str = ""
    target_project_name: str = ""
    project_name: str = ""
    project_description: str = ""
    title: str = ""
    scope: str = "entire"
    scope_n: int = 0
    status: str = ConversationStatus.RECEIVED.value
    messages: List[ConversationMessage] = field(default_factory=list)
    raw_messages_json: str = ""
    compiled_summary: str = ""
    extracted_ideas: List[ExtractedIdea] = field(default_factory=list)
    extracted_requirements: List[ExtractedRequirement] = field(default_factory=list)
    extracted_decisions: List[ExtractedDecision] = field(default_factory=list)
    change_package: Optional[ChangePackage] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 10
    next_retry_at: str = ""
    error_message: str = ""
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    compiled_at: str = ""

    def __post_init__(self):
        # Read-compat: normalize legacy intent strings ("factory_improvement").
        self.intent = canonical_intent(self.intent)


# ─── JSON Storage ─────────────────────────────────────────────────
# Using JSON file storage (same pattern as agent_memory.py)

class ConversationStore:
    """JSON file-backed storage for conversations."""

    def __init__(self, base_dir: str = "products/.conversations"):
        self.base_dir = base_dir
        # U7: canonical location; legacy path (old dashboard product) is read-only fallback
        self.legacy_conversations_base = None
        if not os.path.exists(os.path.join(base_dir, "conversations.json")):
            legacy = os.path.join("pipeline_dashboard", "products", ".conversations")
            if os.path.exists(legacy) and os.path.abspath(legacy) != os.path.abspath(base_dir):
                self.legacy_conversations_base = legacy
        os.makedirs(base_dir, exist_ok=True)
        self.conversations_file = os.path.join(base_dir, "conversations.json")
        self.ideas_file = os.path.join(base_dir, "ideas.json")
        self.requirements_file = os.path.join(base_dir, "requirements.json")
        self.decisions_file = os.path.join(base_dir, "decisions.json")
        self.change_packages_file = os.path.join(base_dir, "change_packages.json")
        self.plans_file = os.path.join(base_dir, "implementation_plans.json")
        self._ensure_files()
        # In-memory chunk buffers for chunked upload
        self._chunk_buffers: Dict[str, Dict[str, Any]] = {}

    def _ensure_files(self):
        for f in [self.conversations_file, self.ideas_file,
                  self.requirements_file, self.decisions_file,
                  self.change_packages_file]:
            if not os.path.exists(f):
                with open(f, 'w') as fh:
                    json.dump({}, fh)

    def _load(self, filepath: str) -> Dict:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data:
                return data
        except (json.JSONDecodeError, FileNotFoundError):
            data = None
        # U7: read-only fallback to the legacy location when canonical is empty
        legacy = getattr(self, "legacy_conversations_base", None)
        if legacy:
            try:
                with open(os.path.join(legacy, os.path.basename(filepath)), 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return data if isinstance(data, dict) else {}

    def _save(self, filepath: str, data: Dict):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    # ─── Conversations ────────────────────────────────────────────

    def save_conversation(self, conv: Conversation) -> str:
        data = self._load(self.conversations_file)
        conv.updated_at = datetime.utcnow().isoformat()
        data[conv.id] = asdict(conv)
        self._save(self.conversations_file, data)
        return conv.id

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        data = self._load(self.conversations_file)
        if conv_id in data:
            d = data[conv_id]
            d['messages'] = [ConversationMessage(**m) for m in d.get('messages', [])]
            d['extracted_ideas'] = [ExtractedIdea(**i) for i in d.get('extracted_ideas', [])]
            d['extracted_requirements'] = [ExtractedRequirement(**r) for r in d.get('extracted_requirements', [])]
            d['extracted_decisions'] = [ExtractedDecision(**dec) for dec in d.get('extracted_decisions', [])]
            if d.get('change_package'):
                d['change_package'] = ChangePackage(**d['change_package'])
            return Conversation(**d)
        return None

    def get_conversation_by_source_id(self, source_id: str) -> Optional[Conversation]:
        data = self._load(self.conversations_file)
        for conv_id, d in data.items():
            if d.get('source_conversation_id') == source_id:
                return self.get_conversation(conv_id)
        return None

    def list_conversations(self, source_platform: str = None,
                           intent: str = None, status: str = None,
                           limit: int = 50, offset: int = 0) -> List[Conversation]:
        data = self._load(self.conversations_file)
        result = []
        for conv_id, d in data.items():
            if source_platform and d.get('source_platform') != source_platform:
                continue
            if intent and d.get('intent') != intent:
                continue
            if status and d.get('status') != status:
                continue
            d_copy = d.copy()
            d_copy['messages'] = [ConversationMessage(**m) for m in d_copy.get('messages', [])]
            d_copy['extracted_ideas'] = [ExtractedIdea(**i) for i in d_copy.get('extracted_ideas', [])]
            d_copy['extracted_requirements'] = [ExtractedRequirement(**r) for r in d_copy.get('extracted_requirements', [])]
            d_copy['extracted_decisions'] = [ExtractedDecision(**dec) for dec in d_copy.get('extracted_decisions', [])]
            if d_copy.get('change_package'):
                d_copy['change_package'] = ChangePackage(**d_copy['change_package'])
            result.append(Conversation(**d_copy))
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result[offset:offset + limit]

    def update_conversation(self, conv: Conversation) -> bool:
        data = self._load(self.conversations_file)
        if conv.id in data:
            conv.updated_at = datetime.utcnow().isoformat()
            data[conv.id] = asdict(conv)
            self._save(self.conversations_file, data)
            return True
        return False

    def delete_conversation(self, conv_id: str) -> bool:
        data = self._load(self.conversations_file)
        if conv_id in data:
            del data[conv_id]
            self._save(self.conversations_file, data)
            return True
        return False

    def count_conversations(self, status: str = None) -> int:
        data = self._load(self.conversations_file)
        if status:
            return sum(1 for d in data.values() if d.get('status') == status)
        return len(data)

    # ─── Ideas ────────────────────────────────────────────────────

    def save_idea(self, idea: ExtractedIdea) -> str:
        data = self._load(self.ideas_file)
        data[idea.id] = asdict(idea)
        self._save(self.ideas_file, data)
        return idea.id

    def get_idea(self, idea_id: str) -> Optional[ExtractedIdea]:
        data = self._load(self.ideas_file)
        if idea_id in data:
            return ExtractedIdea(**data[idea_id])
        return None

    def list_ideas(self, status: str = None, source: str = None,
                   min_confidence: float = 0.0,
                   limit: int = 50, offset: int = 0) -> List[ExtractedIdea]:
        data = self._load(self.ideas_file)
        result = []
        for idea_id, d in data.items():
            if status and d.get('status') != status:
                continue
            if source and d.get('metadata', {}).get('source') != source:
                continue
            if d.get('confidence', 0) < min_confidence:
                continue
            result.append(ExtractedIdea(**d))
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result[offset:offset + limit]

    def update_idea(self, idea: ExtractedIdea) -> bool:
        data = self._load(self.ideas_file)
        if idea.id in data:
            data[idea.id] = asdict(idea)
            self._save(self.ideas_file, data)
            return True
        return False

    def count_ideas(self, status: str = None) -> int:
        data = self._load(self.ideas_file)
        if status:
            return sum(1 for d in data.values() if d.get('status') == status)
        return len(data)

    # ─── Requirements ─────────────────────────────────────────────

    def save_requirement(self, req: ExtractedRequirement) -> str:
        data = self._load(self.requirements_file)
        data[req.id] = asdict(req)
        self._save(self.requirements_file, data)
        return req.id

    def list_requirements(self, conversation_id: str = None,
                          idea_id: str = None) -> List[ExtractedRequirement]:
        data = self._load(self.requirements_file)
        result = []
        for req_id, d in data.items():
            if conversation_id and d.get('conversation_id') != conversation_id:
                continue
            if idea_id and d.get('idea_id') != idea_id:
                continue
            result.append(ExtractedRequirement(**d))
        return result

    def count_requirements(self) -> int:
        data = self._load(self.requirements_file)
        return len(data)

    # ─── Decisions ────────────────────────────────────────────────

    def save_decision(self, dec: ExtractedDecision) -> str:
        data = self._load(self.decisions_file)
        data[dec.id] = asdict(dec)
        self._save(self.decisions_file, data)
        return dec.id

    def list_decisions(self, conversation_id: str = None,
                       idea_id: str = None) -> List[ExtractedDecision]:
        data = self._load(self.decisions_file)
        result = []
        for dec_id, d in data.items():
            if conversation_id and d.get('conversation_id') != conversation_id:
                continue
            if idea_id and d.get('idea_id') != idea_id:
                continue
            result.append(ExtractedDecision(**d))
        return result

    def count_decisions(self) -> int:
        data = self._load(self.decisions_file)
        return len(data)

    # ─── Change Packages ──────────────────────────────────────────

    def save_change_package(self, cp: ChangePackage) -> str:
        data = self._load(self.change_packages_file)
        data[cp.id] = asdict(cp)
        self._save(self.change_packages_file, data)
        return cp.id

    def get_change_package(self, cp_id: str) -> Optional[ChangePackage]:
        data = self._load(self.change_packages_file)
        if cp_id in data:
            d = data[cp_id]
            d['changes'] = [ChangeItem(**c) for c in d.get('changes', [])]
            return ChangePackage(**d)
        return None

    def list_change_packages(self, project_id: str = None,
                             status: str = None) -> List[ChangePackage]:
        data = self._load(self.change_packages_file)
        result = []
        for cp_id, d in data.items():
            if project_id and d.get('project_id') != project_id:
                continue
            if status and d.get('status') != status:
                continue
            d_copy = d.copy()
            d_copy['changes'] = [ChangeItem(**c) for c in d_copy.get('changes', [])]
            result.append(ChangePackage(**d_copy))
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result

    def update_change_package(self, cp: ChangePackage) -> bool:
        data = self._load(self.change_packages_file)
        if cp.id in data:
            data[cp.id] = asdict(cp)
            self._save(self.change_packages_file, data)
            return True
        return False

    def count_change_packages(self, status: str = None) -> int:
        data = self._load(self.change_packages_file)
        if status:
            return sum(1 for d in data.values() if d.get('status') == status)
        return len(data)

    # ─── Stats ────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        return {
            "conversations": self.count_conversations(),
            "conversations_by_status": {
                status: self.count_conversations(status=status.value)
                for status in ConversationStatus
            },
            "ideas": self.count_ideas(),
            "ideas_by_status": {
                status: self.count_ideas(status=status.value)
                for status in IdeaStatus
            },
            "requirements": self.count_requirements(),
            "decisions": self.count_decisions(),
            "change_packages": self.count_change_packages(),
            "change_packages_by_status": {
                status: self.count_change_packages(status=status.value)
                for status in ChangePackageStatus
            }
        }

    # ─── Chunk Upload Buffer (File-based) ────────────────────────

    def _get_chunk_dir(self, conv_id: str) -> str:
        """Get the chunk directory for a conversation."""
        chunk_dir = os.path.join(self.base_dir, f".chunks_{conv_id}")
        os.makedirs(chunk_dir, exist_ok=True)
        return chunk_dir

    def store_chunk(self, conv_id: str, chunk_index: int, total_chunks: int, content: str) -> Dict[str, Any]:
        """Store a chunk of file content. Returns status of upload."""
        chunk_dir = self._get_chunk_dir(conv_id)

        # Store metadata
        meta_path = os.path.join(chunk_dir, "_meta.json")
        meta = {"total_chunks": total_chunks, "created_at": datetime.utcnow().isoformat()}
        if os.path.exists(meta_path):
            with open(meta_path, 'r') as f:
                meta = json.load(f)
        meta["total_chunks"] = total_chunks
        with open(meta_path, 'w') as f:
            json.dump(meta, f)

        # Store chunk content
        chunk_path = os.path.join(chunk_dir, f"chunk_{chunk_index}.txt")
        with open(chunk_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # Count received chunks
        received = len([f for f in os.listdir(chunk_dir) if f.startswith("chunk_")])
        return {
            "received": True,
            "chunks_received": received,
            "total_chunks": total_chunks,
            "complete": received == total_chunks
        }

    def get_chunk_buffer(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get the chunk buffer for a conversation."""
        chunk_dir = self._get_chunk_dir(conv_id)
        meta_path = os.path.join(chunk_dir, "_meta.json")
        if not os.path.exists(meta_path):
            return None
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        received = len([f for f in os.listdir(chunk_dir) if f.startswith("chunk_")])
        return {"total_chunks": meta["total_chunks"], "chunks_received": received}

    def combine_chunks(self, conv_id: str) -> Optional[str]:
        """Combine all chunks into full content. Returns None if incomplete."""
        chunk_dir = self._get_chunk_dir(conv_id)
        meta_path = os.path.join(chunk_dir, "_meta.json")
        if not os.path.exists(meta_path):
            return None

        with open(meta_path, 'r') as f:
            meta = json.load(f)

        total_chunks = meta["total_chunks"]
        received = len([f for f in os.listdir(chunk_dir) if f.startswith("chunk_")])
        if received != total_chunks:
            return None

        # Combine in order
        parts = []
        for i in range(total_chunks):
            chunk_path = os.path.join(chunk_dir, f"chunk_{i}.txt")
            if os.path.exists(chunk_path):
                with open(chunk_path, 'r', encoding='utf-8') as f:
                    parts.append(f.read())
            else:
                parts.append("")

        # Clean up chunk directory
        import shutil
        shutil.rmtree(chunk_dir, ignore_errors=True)

        return "".join(parts)

    # ─── Implementation Plans ────────────────────────────────────

    def save_plan(self, plan: ImplementationPlan) -> str:
        data = self._load(self.plans_file)
        data[plan.id] = asdict(plan)
        self._save(self.plans_file, data)
        return plan.id

    def get_plan(self, plan_id: str) -> Optional[ImplementationPlan]:
        data = self._load(self.plans_file)
        if plan_id in data:
            d = data[plan_id]
            d['file_changes'] = [FileChange(**fc) for fc in d.get('file_changes', [])]
            return ImplementationPlan(**d)
        return None

    def get_plan_by_conversation(self, conv_id: str) -> Optional[ImplementationPlan]:
        data = self._load(self.plans_file)
        for plan_id, d in data.items():
            if d.get('conversation_id') == conv_id:
                d['file_changes'] = [FileChange(**fc) for fc in d.get('file_changes', [])]
                return ImplementationPlan(**d)
        return None

    def update_plan(self, plan: ImplementationPlan) -> bool:
        data = self._load(self.plans_file)
        if plan.id in data:
            data[plan.id] = asdict(plan)
            self._save(self.plans_file, data)
            return True
        return False

    def list_plans(self, status: str = None) -> List[ImplementationPlan]:
        data = self._load(self.plans_file)
        result = []
        for plan_id, d in data.items():
            if status and d.get('status') != status:
                continue
            d['file_changes'] = [FileChange(**fc) for fc in d.get('file_changes', [])]
            result.append(ImplementationPlan(**d))
        result.sort(key=lambda x: x.created_at, reverse=True)
        return result
