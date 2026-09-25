"""
Checkpoint / status documents (extracted from pipeline_executor - 1A.11).

Writes the standardized runtime checkpoint docs:
  - PROJECT-STATUS.md              (journal.write_status)
  - docs/agent-context.md          (current stage/agent/tokens/files)
  - docs/compact/<stage>-summary.md
  - docs/feature-status.md         (iteration stages)
"""
from typing import Dict, List, Optional


class CheckpointWriter:
    def __init__(self, journal, phasing, summarizer, phase_stages):
        self.journal = journal
        self.phasing = phasing
        self.summarizer = summarizer
        self.phase_stages = phase_stages or []

    def feature_status_map(self, stage_executions: Dict) -> Dict[str, str]:
        """Map feature id -> 'done' for features in completed iteration stages."""
        done: Dict[str, str] = {}
        completed = set(stage_executions.keys()) if stage_executions else set()
        for it in (getattr(self.phasing, "phase_plan", []) or []):
            if it.stage_id in completed:
                for f in it.feature_subset:
                    done[f.get("id")] = "done"
        return done

    def write_stage(self, stage_id, stage_executions, execution=None):
        """Write all checkpoint docs for a completed stage (best-effort)."""
        if not self.journal:
            return
        try:
            completed = execution.stage_executions if execution else {}
            self.journal.write_status(execution)
            last_agent = stage_executions[-1].agent_id if stage_executions else ""
            files_ = [a for e in stage_executions for a in (e.artifacts or [])]
            self.journal.write_agent_context(
                current_stage=stage_id, current_agent=last_agent,
                tokens=execution.total_tokens if execution else 0,
                files=files_[:10])
            text = ""
            for a in files_:
                try:
                    with open(a, "r", encoding="utf-8") as f:
                        text += f.read() + "\n"
                except Exception:
                    pass
            if text and self.summarizer:
                # No hard cap: structured compact (headings + key bullets), open size.
                self.journal.write_compact_summary(
                    stage_id, self.summarizer.summarize(text, max_chars=0))
            if stage_id in self.phase_stages:
                self.journal.write_feature_status(
                    self.phasing.extract_features(),
                    self.feature_status_map(completed))
        except Exception:
            pass
