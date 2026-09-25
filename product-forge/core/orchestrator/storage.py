"""
Orchestrator support: audit log, LLM response cache, artifact summarizer.

Extracted from the monolithic pipeline_executor to improve modularity (1A.11).
"""
import hashlib
import json
import os
import threading
from typing import Dict, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Cache policy (owner decision): GENERATION OUTPUT is never served from a cache.
# Caching is allowed ONLY on the INPUT side, keyed by a fingerprint of the
# resolved inputs, so a hit happens only when the inputs are provably unchanged.
# ─────────────────────────────────────────────────────────────────────────────

def _env_flag(name: str, default: str = "0") -> bool:
    """Truthy env flag ('1'/'true'/'yes'/'on')."""
    return str(os.getenv(name, default)).strip().lower() in ("1", "true", "yes", "on")


def no_cache() -> bool:
    """Layer 3 hard bypass: PIPELINE_NO_CACHE=1 skips ALL cache reads AND writes."""
    return _env_flag("PIPELINE_NO_CACHE", "0")


def output_cache_allowed() -> bool:
    """Layer 1 escape hatch (debug only): outputs are NEVER served from cache by
    default. Set PIPELINE_ALLOW_OUTPUT_CACHE=1 to re-enable the legacy output
    cache (logs loudly when used)."""
    return _env_flag("PIPELINE_ALLOW_OUTPUT_CACHE", "0")


def input_cache_enabled() -> bool:
    """Layer 2 feature flag: input-side (fingerprint-keyed) cache, default ON.
    Set PIPELINE_INPUT_CACHE=0 to disable."""
    return _env_flag("PIPELINE_INPUT_CACHE", "1")


# Bump when prompt assembly changes shape; part of the input-cache key.
TEMPLATE_VERSION = os.getenv("PIPELINE_TEMPLATE_VERSION", "v1")


def digest_text(text: str) -> str:
    """Stable sha256 digest of a text payload (used for resolved-input digests)."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def fingerprint_inputs(upstream_digests=None, feedback: str = "", notes: str = "",
                       conditions: str = "", section_id: str = "", config=None) -> str:
    """Deterministic digest of the RESOLVED inputs that affect an agent's output.

    A cache hit is legitimate ONLY when the full key (which includes this
    fingerprint) matches — i.e. the inputs are provably unchanged.
    """
    payload = {
        "upstream": sorted(str(x) for x in (upstream_digests or [])),
        "feedback": feedback or "",
        "notes": notes or "",
        "conditions": conditions or "",
        "section_id": section_id or "",
        "config": config or {},
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def input_cache_key(model: str, agent_id: str, prompt: str, template_version: str,
                    fingerprint: str) -> str:
    """Layer 2 key: sha256(model : agent_id : prompt : template_version : fingerprint).

    `prompt` here is the cheap BASE instruction/task component (the full assembled
    prompt is the cached value, so it cannot be part of the lookup key).
    """
    raw = ":".join([str(model or ""), str(agent_id or ""), prompt or "",
                    str(template_version or ""), str(fingerprint or "")])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AgentAuditLog:
    """Detailed audit log for each agent execution."""

    def __init__(self, project_dir: str):
        self.project_dir = project_dir
        self.log_file = os.path.join(project_dir, "agent-audit-log.json")
        self.entries = []
        self._lock = threading.Lock()
        self._load()

    def _load(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    self.entries = json.load(f)
            except Exception:
                self.entries = []

    def _save(self):
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.entries, f, indent=2, ensure_ascii=False)

    def log_agent_execution(self, entry: Dict):
        with self._lock:
            self.entries.append(entry)
            self._save()

    def get_summary(self) -> Dict:
        total_tokens = sum(e.get("total_tokens", 0) for e in self.entries)
        total_cost = sum(e.get("cost", 0) for e in self.entries)
        cache_hits = sum(1 for e in self.entries if e.get("cache_hit", False))
        chunked = sum(1 for e in self.entries if e.get("chunking_used", False))
        return {
            "total_executions": len(self.entries),
            "total_tokens": total_tokens,
            "total_cost": total_cost,
            "cache_hits": cache_hits,
            "chunked_calls": chunked,
            "models_used": list(set(e.get("model", "") for e in self.entries if e.get("model"))),
        }


class LLMCache:
    """Application-level cache for LLM responses."""

    def __init__(self, project_dir: str):
        self.cache_dir = os.path.join(project_dir, ".llm-cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _hash_prompt(self, prompt: str, model: str, agent_id: str) -> str:
        key = f"{model}:{agent_id}:{prompt}"
        return hashlib.sha256(key.encode()).hexdigest()[:32]

    def get(self, prompt: str, model: str, agent_id: str) -> Optional[Dict]:
        cache_key = self._hash_prompt(prompt, model, agent_id)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def set(self, prompt: str, model: str, agent_id: str, result: Dict):
        cache_key = self._hash_prompt(prompt, model, agent_id)
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    def clear(self):
        for f in os.listdir(self.cache_dir):
            if f.endswith('.json'):
                os.remove(os.path.join(self.cache_dir, f))


class InputCache:
    """Input-side cache: stores the ASSEMBLED PROMPT, never the generation output.

    A hit requires the full key (model + agent + base prompt + template version +
    resolved-input fingerprint) to match. It is project-scoped under
    ``products/<project>/.input-cache`` so global/shared caches are never touched.
    Disabled entirely by PIPELINE_NO_CACHE=1.
    """

    def __init__(self, project_dir: str):
        self.cache_dir = os.path.join(project_dir, ".input-cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def get(self, key: str, agent_id: str = "") -> Optional[Dict]:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None

    def set(self, key: str, agent_id: str, result: Dict, stage_id: str = "") -> bool:
        try:
            payload = dict(result or {})
            payload.setdefault("agent_id", agent_id)
            payload.setdefault("stage_id", stage_id)
            with open(self._path(key), 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def clear(self, agents=None, stages=None) -> int:
        """Invalidate entries for given agents/stages (or everything when both empty)."""
        agents = set(agents or [])
        stages = set(stages or [])
        removed = 0
        try:
            names = os.listdir(self.cache_dir)
        except Exception:
            return 0
        for fn in names:
            if not fn.endswith('.json'):
                continue
            path = os.path.join(self.cache_dir, fn)
            if not agents and not stages:
                try:
                    os.remove(path)
                    removed += 1
                except Exception:
                    pass
                continue
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    meta = json.load(f) or {}
            except Exception:
                meta = {}
            if (meta.get("agent_id") in agents) or (meta.get("stage_id") in stages):
                try:
                    os.remove(path)
                    removed += 1
                except Exception:
                    pass
        return removed


class ArtifactSummarizer:
    """Summarize older artifacts by extracting headers + first bullet."""

    @staticmethod
    def summarize(content: str, max_chars: int = 0) -> str:
        """Structured digest (headers + first bullet per section).

        ``max_chars=0`` (default) keeps the FULL digest — no hard cap. A positive
        budget trims it, preferring to keep headings/lines intact.
        """
        if not content:
            return content
        if max_chars and len(content) <= max_chars:
            return content
        lines = content.split('\n')
        summary_parts = []
        current_section = None
        current_bullets = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#'):
                if current_section:
                    summary_parts.append(current_section)
                    if current_bullets:
                        summary_parts.append("  " + current_bullets[0])
                current_section = stripped
                current_bullets = []
            elif stripped.startswith('- ') or stripped.startswith('* '):
                current_bullets.append(stripped)
        if current_section:
            summary_parts.append(current_section)
            if current_bullets:
                summary_parts.append("  " + current_bullets[0])
        summary = '\n'.join(summary_parts) or content
        if max_chars and len(summary) > max_chars:
            summary = summary[:max_chars].rsplit("\n", 1)[0] + "\n...[compacted]"
        return summary
