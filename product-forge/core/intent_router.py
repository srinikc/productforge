# NOT deprecated for intake: this module IS on the live intake path -
# core/intake.py routes conversations through IntentRouter to core/backlog_link
# (BI-0054). (The old "superseded by PipelineExecutor" note was wrong for intake;
# PipelineExecutor supersedes it only for pipeline stage execution.)
"""
Conversation & Idea Ingestion - Intent Router

Routes conversations based on intent:
- save_idea: Store extracted ideas
- new_project: Create project + start pipeline
- new_project_quick: Create project + just prototype
- modify_project: Create change package + start pipeline
- add_context: Attach context to project
"""

try:
    from core.paths import ROOT as _PF_ROOT
except ImportError:  # executed as a script: seed the repo root on sys.path, then retry
    import os as _pf_os
    import sys as _pf_sys
    _pf_d = _pf_os.path.abspath(__file__)
    for _pf_i in range(3):
        _pf_d = _pf_os.path.dirname(_pf_d)
        if _pf_os.path.isfile(_pf_os.path.join(_pf_d, 'core', 'paths.py')):
            _pf_sys.path.insert(0, _pf_d)
            break
    from core.paths import ROOT as _PF_ROOT

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

import sys
sys.path.insert(0, str(_PF_ROOT))
from core.conversation_models import (
    ConversationStore, Conversation,
    ChangePackage, ChangeItem,
    ConversationStatus, IntentType, ChangeType, ChangePackageStatus
)
from core.conversation_compiler import ConversationCompiler


def product_forge_improvements_dir(products_dir: str = "products") -> str:
    """Product Forge improvements dir; migrates the legacy ``.factory_improvements`` name."""
    root = os.path.dirname(products_dir) or "."
    new = os.path.join(root, ".product_forge_improvements")
    legacy = os.path.join(root, ".factory_improvements")
    if not os.path.exists(new) and os.path.exists(legacy):
        try:
            os.rename(legacy, new)
        except OSError:
            return legacy
    os.makedirs(new, exist_ok=True)
    return new


# ─── Intent Router ───────────────────────────────────────────────

class IntentRouter:
    """Routes conversations based on intent."""

    def __init__(self):
        self.store = ConversationStore()
        self.compiler = ConversationCompiler()
        self.products_dir = os.path.join(
            str(_PF_ROOT),
            "products"
        )

    def process_conversation(self, conv_id: str) -> Dict[str, Any]:
        """Process a conversation based on its intent."""
        conv = self.store.get_conversation(conv_id)
        if not conv:
            return {"error": "Conversation not found"}

        # Step 1: Compile conversation (extract ideas/requirements)
        if conv.status == ConversationStatus.RECEIVED.value:
            success = self.compiler.compile_conversation(conv_id)
            if not success:
                return {"error": "Compilation failed", "status": conv.status}

        # Reload conversation after compilation
        conv = self.store.get_conversation(conv_id)

        # Step 2: Route by intent
        intent = conv.intent
        if intent == IntentType.SAVE_IDEA.value:
            result = self._route_save_idea(conv)
        elif intent == IntentType.NEW_PROJECT.value:
            result = self._route_new_project(conv)
        elif intent == IntentType.NEW_PROJECT_QUICK.value:
            result = self._route_new_project_quick(conv)
        elif intent == IntentType.MODIFY_PROJECT.value:
            result = self._route_modify_project(conv)
        elif intent == IntentType.ADD_CONTEXT.value:
            result = self._route_add_context(conv)
        elif intent == IntentType.PRODUCT_FORGE_IMPROVEMENT.value:
            result = self._route_product_forge_improvement(conv)
        else:
            result = {"error": f"Unknown intent: {intent}"}

        # B2 bridge: promote the conversation into its backlog item (non-fatal).
        try:
            from core.backlog_link import promote_conversation
            item = promote_conversation(conv)
            if item and isinstance(result, dict):
                result.setdefault("backlog_item", {
                    "id": item.get("id"), "label": item.get("label"),
                    "status": item.get("status"), "scope": item.get("scope")})
        except Exception:
            pass
        return result

    def _route_save_idea(self, conv: Conversation) -> Dict[str, Any]:
        """Route: save_idea - Just store extracted ideas."""
        conv.status = ConversationStatus.COMPILED.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        return {
            "action": "save_idea",
            "status": "completed",
            "ideas_saved": len(conv.extracted_ideas),
            "requirements_saved": len(conv.extracted_requirements),
            "decisions_saved": len(conv.extracted_decisions),
            "message": f"Saved {len(conv.extracted_ideas)} ideas"
        }

    def _route_new_project(self, conv: Conversation) -> Dict[str, Any]:
        """Route: new_project - Create project + start pipeline."""
        project_name = conv.project_name
        if not project_name:
            return {"error": "project_name is required"}

        # Create project folder
        project_path = os.path.join(self.products_dir, project_name)
        if os.path.exists(project_path):
            return {"error": f"Project '{project_name}' already exists"}

        os.makedirs(project_path, exist_ok=True)

        # Create project structure
        self._init_project_structure(project_path, conv)

        # Store project reference in conversation
        conv.target_project_id = project_name
        conv.status = ConversationStatus.BUILDING.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        # Start pipeline execution in background
        pipeline_result = self._start_pipeline(project_name, conv)

        return {
            "action": "new_project",
            "status": "created",
            "project_name": project_name,
            "project_path": project_path,
            "pipeline_status": pipeline_result.get("status", "started"),
            "message": f"Project '{project_name}' created. Pipeline started."
        }

    def _route_new_project_quick(self, conv: Conversation) -> Dict[str, Any]:
        """Route: new_project_quick - Create project + just prototype."""
        project_name = conv.project_name
        if not project_name:
            return {"error": "project_name is required"}

        project_path = os.path.join(self.products_dir, project_name)
        if os.path.exists(project_path):
            return {"error": f"Project '{project_name}' already exists"}

        os.makedirs(project_path, exist_ok=True)

        # Create minimal project structure (prototype only)
        self._init_project_structure(project_path, conv, quick=True)

        conv.target_project_id = project_name
        conv.status = ConversationStatus.BUILDING.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        return {
            "action": "new_project_quick",
            "status": "created",
            "project_name": project_name,
            "project_path": project_path,
            "pipeline_status": "prototype_ready",
            "message": f"Project '{project_name}' created. Prototype mode."
        }

    def _route_modify_project(self, conv: Conversation) -> Dict[str, Any]:
        """Route: modify_project - Create change package + start pipeline."""
        target = conv.target_project_id or conv.target_project_name
        if not target:
            return {"error": "target_project_id or target_project_name is required"}

        # Find project
        project_path = os.path.join(self.products_dir, target)
        if not os.path.exists(project_path):
            return {"error": f"Project '{target}' not found"}

        # Create change package
        change_package = self._create_change_package(conv, target)

        # Store change package
        self.store.save_change_package(change_package)

        # Update conversation
        conv.change_package = change_package
        conv.status = ConversationStatus.BUILDING.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        return {
            "action": "modify_project",
            "status": "change_package_created",
            "project_name": target,
            "change_package_id": change_package.id,
            "changes_count": len(change_package.changes),
            "risks_count": len(change_package.risks),
            "message": f"Change package created for '{target}'. Pending approval."
        }

    def _route_add_context(self, conv: Conversation) -> Dict[str, Any]:
        """Route: add_context - Attach context to project."""
        target = conv.target_project_id or conv.target_project_name
        if not target:
            return {"error": "target_project_id or target_project_name is required"}

        project_path = os.path.join(self.products_dir, target)
        if not os.path.exists(project_path):
            return {"error": f"Project '{target}' not found"}

        # Store context in project
        context_dir = os.path.join(project_path, "context")
        os.makedirs(context_dir, exist_ok=True)

        context_file = os.path.join(context_dir, f"conv-{conv.id[:8]}.json")
        context_data = {
            "conversation_id": conv.id,
            "source": conv.source_platform,
            "title": conv.title,
            "compiled_summary": conv.compiled_summary,
            "ideas": [i.title for i in conv.extracted_ideas],
            "requirements": [r.requirement_text for r in conv.extracted_requirements],
            "decisions": [d.decision_text for d in conv.extracted_decisions],
            "added_at": datetime.utcnow().isoformat()
        }

        with open(context_file, 'w', encoding='utf-8') as f:
            json.dump(context_data, f, indent=2, ensure_ascii=False)

        conv.status = ConversationStatus.COMPILED.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        return {
            "action": "add_context",
            "status": "completed",
            "project_name": target,
            "context_file": context_file,
            "message": f"Context added to '{target}'"
        }

    def _route_product_forge_improvement(self, conv: Conversation) -> Dict[str, Any]:
        """Route: product_forge_improvement - Improve Product Forge itself."""
        # Store Product Forge improvement in a special directory
        product_forge_improvements = product_forge_improvements_dir(self.products_dir)

        # Create improvement file
        improvement_file = os.path.join(product_forge_improvements, f"conv-{conv.id[:8]}.json")
        improvement_data = {
            "conversation_id": conv.id,
            "source": conv.source_platform,
            "title": conv.title,
            "compiled_summary": conv.compiled_summary,
            "ideas": [i.title for i in conv.extracted_ideas],
            "requirements": [r.requirement_text for r in conv.extracted_requirements],
            "decisions": [d.decision_text for d in conv.extracted_decisions],
            "status": "pending_analysis",
            "created_at": datetime.utcnow().isoformat()
        }

        with open(improvement_file, 'w', encoding='utf-8') as f:
            json.dump(improvement_data, f, indent=2, ensure_ascii=False)

        conv.status = ConversationStatus.COMPILED.value
        conv.updated_at = datetime.utcnow().isoformat()
        self.store.update_conversation(conv)

        return {
            "action": "product_forge_improvement",
            "status": "pending_analysis",
            "improvement_file": improvement_file,
            "ideas_count": len(conv.extracted_ideas),
            "requirements_count": len(conv.extracted_requirements),
            "decisions_count": len(conv.extracted_decisions),
            "message": f"Product Forge improvement recorded. Will analyze {len(conv.extracted_ideas)} ideas."
        }

    def implement_product_forge_improvement(self, conv: Conversation) -> Dict[str, Any]:
        """Implement approved Product Forge improvements."""
        from datetime import datetime
        
        # Track implementation results
        implemented = []
        skipped = []
        errors = []
        
        # Analyze each extracted idea
        for idea in conv.extracted_ideas:
            try:
                # Determine what type of improvement this is
                improvement_type = self._categorize_improvement(idea.title, idea.description)
                
                # Create implementation record
                record = {
                    "idea_title": idea.title,
                    "description": idea.description,
                    "improvement_type": improvement_type,
                    "status": "planned",
                    "files_affected": [],
                    "implemented_at": None
                }
                
                # Based on improvement type, determine what files would be affected
                if improvement_type == "dashboard":
                    record["files_affected"] = ["dashboard/static/"]
                    record["status"] = "ready_for_implementation"
                elif improvement_type == "api":
                    record["files_affected"] = ["dashboard/api/app.py"]
                    record["status"] = "ready_for_implementation"
                elif improvement_type == "core":
                    record["files_affected"] = ["core/intent_router.py", "core/conversation_models.py"]
                    record["status"] = "ready_for_implementation"
                elif improvement_type == "pipeline":
                    record["files_affected"] = ["core/pipeline_executor.py", "pipeline-definition.json"]
                    record["status"] = "ready_for_implementation"
                elif improvement_type == "adapter":
                    record["files_affected"] = ["adapters/chatgpt/instructions.md", "adapters/chatgpt/schema.yaml"]
                    record["status"] = "ready_for_implementation"
                else:
                    record["files_affected"] = ["To be determined"]
                    record["status"] = "needs_analysis"
                
                implemented.append(record)
                
            except Exception as e:
                errors.append({"idea": idea.title, "error": str(e)})
        
        # Analyze requirements
        for req in conv.extracted_requirements:
            try:
                record = {
                    "requirement": req.requirement_text,
                    "type": req.requirement_type,
                    "priority": req.priority,
                    "status": "planned"
                }
                implemented.append(record)
            except Exception as e:
                errors.append({"requirement": req.requirement_text, "error": str(e)})
        
        # Store implementation plan
        improvement_file = os.path.join(
            product_forge_improvements_dir(self.products_dir),
            f"impl-{conv.id[:8]}.json"
        )
        
        implementation_data = {
            "conversation_id": conv.id,
            "title": conv.title,
            "implemented_at": datetime.utcnow().isoformat(),
            "ideas": [i.title for i in conv.extracted_ideas],
            "requirements": [r.requirement_text for r in conv.extracted_requirements],
            "decisions": [d.decision_text for d in conv.extracted_decisions],
            "implementation_plan": implemented,
            "errors": errors,
            "status": "implementation_planned"
        }
        
        with open(improvement_file, 'w', encoding='utf-8') as f:
            json.dump(implementation_data, f, indent=2, ensure_ascii=False)
        
        return {
            "status": "implementation_planned",
            "items_planned": len(implemented),
            "errors": len(errors),
            "implementation_plan": implemented,
            "message": f"Implementation planned for {len(implemented)} items. Ready for execution."
        }

    def _categorize_improvement(self, title: str, description: str) -> str:
        """Categorize what type of improvement this is."""
        text = f"{title} {description}".lower()
        
        if any(word in text for word in ["dashboard", "ui", "frontend", "page", "tab", "button"]):
            return "dashboard"
        elif any(word in text for word in ["api", "endpoint", "route", "http"]):
            return "api"
        elif any(word in text for word in ["pipeline", "stage", "orchestrat", "agent"]):
            return "pipeline"
        elif any(word in text for word in ["adapter", "chatgpt", "gemini", "claude", "mcp"]):
            return "adapter"
        elif any(word in text for word in ["core", "model", "store", "database", "compiler"]):
            return "core"
        else:
            return "general"

    def create_project_from_idea(self, idea) -> Dict[str, Any]:
        """Create a new project from a promoted idea."""
        from core.conversation_models import ExtractedIdea

        # Generate project name from idea title
        project_name = idea.title.lower().replace(" ", "-").replace("_", "-")
        project_name = ''.join(c for c in project_name if c.isalnum() or c == '-')
        project_name = project_name[:50]  # Limit length

        # Check if project already exists
        project_path = os.path.join(self.products_dir, project_name)
        if os.path.exists(project_path):
            return {"error": f"Project '{project_name}' already exists"}

        # Create project folder
        os.makedirs(project_path, exist_ok=True)

        # Create project structure
        dirs = ["discovery", "design", "implement", "test", "artifacts",
                "context", "memory", "messages", "compliance", "docs", "forge_state"]
        for d in dirs:
            os.makedirs(os.path.join(project_path, d), exist_ok=True)

        # Create project config
        from datetime import datetime
        config = {
            "name": project_name,
            "description": idea.description or f"Created from idea: {idea.title}",
            "source_idea_id": idea.id,
            "source_conversation_id": idea.conversation_id,
            "created_at": datetime.utcnow().isoformat(),
            "created_from": "idea_promotion",
            "pipeline_mode": "full"
        }

        with open(os.path.join(project_path, "project-config.json"), 'w') as f:
            json.dump(config, f, indent=2)

        # Store initial context with the idea
        context = {
            "idea_id": idea.id,
            "title": idea.title,
            "description": idea.description,
            "confidence": idea.confidence,
            "created_at": datetime.utcnow().isoformat()
        }

        with open(os.path.join(project_path, "context", "initial-context.json"), 'w') as f:
            json.dump(context, f, indent=2)

        return {
            "status": "project_created",
            "project_name": project_name,
            "project_path": project_path,
            "message": f"Project '{project_name}' created from idea"
        }

    def apply_change_package(self, cp) -> Dict[str, Any]:
        """Apply an approved change package to its target project."""
        project_id = cp.project_id
        if not project_id:
            return {"error": "No project_id on change package"}

        project_path = os.path.join(self.products_dir, project_id)
        if not os.path.exists(project_path):
            return {"error": f"Project '{project_id}' not found"}

        applied_changes = []
        errors = []

        for change in cp.changes:
            try:
                target = change.target
                change_type = change.change_type

                if change_type == "add" and target == "requirement":
                    # Add requirement to project context
                    context_dir = os.path.join(project_path, "context")
                    os.makedirs(context_dir, exist_ok=True)
                    req_file = os.path.join(context_dir, "requirements.json")
                    reqs = []
                    if os.path.exists(req_file):
                        with open(req_file, 'r') as f:
                            reqs = json.load(f)
                    reqs.append({
                        "id": change.id,
                        "description": change.description,
                        "priority": change.priority,
                        "added_at": datetime.utcnow().isoformat()
                    })
                    with open(req_file, 'w') as f:
                        json.dump(reqs, f, indent=2)
                    applied_changes.append({"change_id": change.id, "action": "added_requirement"})

                elif change_type == "add" and target == "idea":
                    # Add idea to project context
                    context_dir = os.path.join(project_path, "context")
                    os.makedirs(context_dir, exist_ok=True)
                    idea_file = os.path.join(context_dir, "ideas.json")
                    ideas = []
                    if os.path.exists(idea_file):
                        with open(idea_file, 'r') as f:
                            ideas = json.load(f)
                    ideas.append({
                        "id": change.id,
                        "description": change.description,
                        "priority": change.priority,
                        "added_at": datetime.utcnow().isoformat()
                    })
                    with open(idea_file, 'w') as f:
                        json.dump(ideas, f, indent=2)
                    applied_changes.append({"change_id": change.id, "action": "added_idea"})

                else:
                    applied_changes.append({"change_id": change.id, "action": f"skipped_{change_type}_{target}"})

            except Exception as e:
                errors.append({"change_id": change.id, "error": str(e)})

        return {
            "applied_count": len(applied_changes),
            "error_count": len(errors),
            "applied": applied_changes,
            "errors": errors
        }

    def _init_project_structure(self, project_path: str, conv: Conversation, quick: bool = False):
        """Initialize project folder structure."""
        # Create directories
        dirs = ["discovery", "design", "implement", "test", "artifacts",
                "context", "memory", "messages", "compliance", "docs", "forge_state"]
        if not quick:
            dirs.extend(["architecture", "security", "performance"])

        for d in dirs:
            os.makedirs(os.path.join(project_path, d), exist_ok=True)

        # Create project config
        config = {
            "name": conv.project_name,
            "description": conv.project_description or f"Created from conversation {conv.id[:8]}",
            "source_conversation_id": conv.id,
            "source_platform": conv.source_platform,
            "created_at": datetime.utcnow().isoformat(),
            "created_from": "conversation_ingestion",
            "pipeline_mode": "quick" if quick else "full"
        }

        with open(os.path.join(project_path, "project-config.json"), 'w') as f:
            json.dump(config, f, indent=2)

        # Store initial context
        context = {
            "conversation_id": conv.id,
            "ideas": [asdict(i) for i in conv.extracted_ideas],
            "requirements": [asdict(r) for r in conv.extracted_requirements],
            "decisions": [asdict(d) for d in conv.extracted_decisions],
            "compiled_summary": conv.compiled_summary
        }

        with open(os.path.join(project_path, "context", "initial-context.json"), 'w') as f:
            json.dump(context, f, indent=2, default=str)

    def _start_pipeline(self, project_name: str, conv: Conversation) -> Dict[str, Any]:
        """Start pipeline execution for a project."""
        try:
            from core.pipeline_executor import PipelineExecutor

            executor = PipelineExecutor(
                products_dir=self.products_dir,
                project=project_name
            )

            # Load pipeline definition
            pipeline_def = os.path.join(
                os.path.dirname(self.products_dir),
                "pipeline-definition.json"
            )
            if os.path.exists(pipeline_def):
                executor.load_pipeline(pipeline_def)
                # Start pipeline in background thread
                import threading
                thread = threading.Thread(
                    target=self._run_pipeline_thread,
                    args=(executor, project_name, conv.id),
                    daemon=True
                )
                thread.start()
                return {"status": "started", "project": project_name}
            else:
                return {"status": "pipeline_def_not_found", "error": "pipeline-definition.json not found"}
        except ImportError as e:
            return {"status": "error", "error": f"Pipeline executor not available: {e}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _run_pipeline_thread(self, executor, project_name: str, conv_id: str):
        """Run pipeline in background thread."""
        try:
            success = executor.execute_pipeline()
            # Update conversation status based on result
            conv = self.store.get_conversation(conv_id)
            if conv:
                if success:
                    conv.status = ConversationStatus.BUILD_COMPLETE.value
                else:
                    conv.status = ConversationStatus.BUILD_FAILED.value
                conv.updated_at = datetime.utcnow().isoformat()
                self.store.update_conversation(conv)
        except Exception as e:
            print(f"[IntentRouter] Pipeline error for {project_name}: {e}")
            conv = self.store.get_conversation(conv_id)
            if conv:
                conv.status = ConversationStatus.BUILD_FAILED.value
                conv.updated_at = datetime.utcnow().isoformat()
                self.store.update_conversation(conv)

    def _create_change_package(self, conv: Conversation, project_name: str) -> ChangePackage:
        """Create a change package from conversation."""
        changes = []

        # Convert requirements to change items
        for req in conv.extracted_requirements:
            changes.append(ChangeItem(
                change_type=ChangeType.ADD.value,
                target="requirement",
                description=req.requirement_text,
                priority=req.priority,
                confidence=req.confidence,
                metadata={"requirement_type": req.requirement_type}
            ))

        # Convert ideas to change items
        for idea in conv.extracted_ideas:
            changes.append(ChangeItem(
                change_type=ChangeType.ADD.value,
                target="idea",
                description=f"{idea.title}: {idea.description}",
                priority="medium",
                confidence=idea.confidence
            ))

        return ChangePackage(
            conversation_id=conv.id,
            project_id=project_name,
            status=ChangePackageStatus.PENDING.value,
            changes=changes,
            risks=[],
            open_questions=[],
            impact_analysis={
                "files_affected": [],
                "risk_level": "medium",
                "estimated_effort": "unknown"
            }
        )


# ─── Helper imports ──────────────────────────────────────────────
from dataclasses import asdict
