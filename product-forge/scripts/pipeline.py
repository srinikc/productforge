#!/usr/bin/env python3
"""
Pipeline Command Helper Script
Handles deterministic commands without LLM involvement.
Usage: python pipeline.py <command> [args]
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

import json
import os
import re
import sys
from pathlib import Path
from datetime import datetime

# Get project root (parent of scripts/)
ROOT = _PF_ROOT
PRODUCTS_DIR = ROOT / "products"
AGENTS_DIR = ROOT / ".opencode" / "agent"

# Add root to path for core/ imports (Phase 1 features)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

# Import pipeline helpers (system-level utilities - no hardcoded project names)
try:
    from pipeline_helpers import (
        get_products_dir as _get_products_dir,
        get_all_projects as _get_all_projects,
        get_default_project as _get_default_project,
        resolve_project as _resolve_project,
        ensure_product_completion as _ensure_product_completion,
        migrate_all_projects as _migrate_all_projects,
    )
    PIPELINE_HELPERS_AVAILABLE = True
except ImportError as e:
    PIPELINE_HELPERS_AVAILABLE = False
    print(f"Warning: Pipeline helpers not available: {e}", file=sys.stderr)

# Try to import core modules (Phase 1 features)
CORE_AVAILABLE = False
CoreImports = {}

try:
    from core.lock_manager import LockManager
    CoreImports['LockManager'] = LockManager
    CORE_AVAILABLE = True
except ImportError:
    pass

try:
    from core.queue_manager import QueueManager
    CoreImports['QueueManager'] = QueueManager
except ImportError:
    pass

try:
    from core.budget_tracker import BudgetTracker
    CoreImports['BudgetTracker'] = BudgetTracker
except ImportError:
    pass

try:
    from core.circuit_breaker import CircuitBreakerRegistry
    CoreImports['CircuitBreakerRegistry'] = CircuitBreakerRegistry
except ImportError:
    pass

try:
    from core.version_manager import VersionManager
    CoreImports['VersionManager'] = VersionManager
except ImportError:
    pass

try:
    from core.logging_manager import ProductLogger, PipelineLogger
    CoreImports['ProductLogger'] = ProductLogger
    CoreImports['PipelineLogger'] = PipelineLogger
except ImportError:
    pass

try:
    from core.cross_review import CrossReviewManager
    CoreImports['CrossReviewManager'] = CrossReviewManager
except ImportError:
    pass

try:
    from core.skills_registry import SkillsRegistry
    CoreImports['SkillsRegistry'] = SkillsRegistry
except ImportError:
    pass

try:
    from core.agent_ledger import AgentLedger
    CoreImports['AgentLedger'] = AgentLedger
except ImportError:
    pass

# Phase 1.1, 1.7, 1.8 - CRITICAL
try:
    from core.model_registry import ModelCapabilityRegistry
    CoreImports['ModelCapabilityRegistry'] = ModelCapabilityRegistry
except ImportError:
    pass

try:
    from core.context_engine import ContextEngine
    CoreImports['ContextEngine'] = ContextEngine
except ImportError:
    pass

try:
    from core.stop_conditions import StopConditionManager
    CoreImports['StopConditionManager'] = StopConditionManager
except ImportError:
    pass

# Phase 2.2, 2.3, 2.4, 2.7 - IMPORTANT
try:
    from core.tool_cache import ToolResultCache
    CoreImports['ToolResultCache'] = ToolResultCache
except ImportError:
    pass

try:
    from core.knowledge_router import KnowledgeRouter
    CoreImports['KnowledgeRouter'] = KnowledgeRouter
except ImportError:
    pass

try:
    from core.budget_allocator import TokenBudgetAllocator
    CoreImports['TokenBudgetAllocator'] = TokenBudgetAllocator
except ImportError:
    pass

try:
    from core.cost_kpi import CostKPITracker
    CoreImports['CostKPITracker'] = CostKPITracker
except ImportError:
    pass

# Phase 3 - ADVANCED
try:
    from core.loop_modes import LoopController
    CoreImports['LoopController'] = LoopController
except ImportError:
    pass

try:
    from core.phase3_advanced import (
        ToolResultCompressor,
        AdaptiveReasoningController,
        KnowledgeGraph,
        SemanticCache,
    )
    CoreImports['ToolResultCompressor'] = ToolResultCompressor
    CoreImports['AdaptiveReasoningController'] = AdaptiveReasoningController
    CoreImports['KnowledgeGraph'] = KnowledgeGraph
    CoreImports['SemanticCache'] = SemanticCache
except ImportError:
    pass

# Optional modules (may not exist)
try:
    from core.checkpoints import CheckpointManager
    CoreImports['CheckpointManager'] = CheckpointManager
except ImportError:
    pass

try:
    from core.dlq import DeadLetterQueue
    CoreImports['DeadLetterQueue'] = DeadLetterQueue
except ImportError:
    pass

if CORE_AVAILABLE:
    print(f"Core modules loaded: {len(CoreImports)}", file=sys.stderr)


def resolve_project_arg(arg_value=None):
    """
    Resolve project name from CLI argument using system-level helpers.
    Returns project name string, or None if cannot resolve.
    """
    if PIPELINE_HELPERS_AVAILABLE:
        return _resolve_project(_get_products_dir(), arg_value)
    # Legacy fallback - only used if helpers unavailable
    if arg_value is not None:
        return arg_value
    # Check products/index.json directly
    index_file = PRODUCTS_DIR / "index.json"
    if index_file.exists():
        try:
            data = json.loads(index_file.read_text())
            products = data.get("products", [])
            if len(products) == 1:
                return products[0]
        except (json.JSONDecodeError, OSError):
            pass
    return None


def show_usage():
    """Display usage information."""
    print("""
MULTI-AGENT PIPELINE SYSTEM
============================

USAGE
-----
  /pipeline                         Show this usage message
  /pipeline new <idea>              Start full pipeline from ideation (Stage 0)
  /pipeline continue [project]      Resume from last incomplete stage (default: auto-detect)
  /pipeline fix <desc>              Fix a specific bug through the pipeline
  /pipeline changes <desc>          Validate changes made outside pipeline

SELECTIVE EXECUTION
-------------------
  /pipeline run <agent>             Run specific agent(s) selectively
  /pipeline run <agent1>,<agent2>   Run multiple agents
  /pipeline run <agent> --model X   Run with model override
  /pipeline run <agent> --from Y    Run with input source

MANAGEMENT
----------
  /pipeline list                    Show projects with agents and status
  /pipeline agents                  List available agents
  /pipeline runs                    List selective runs
  /pipeline test                    Test pipeline infrastructure
  /pipeline health                  Show detailed health status
  /pipeline status [project]        Show detailed project status
  /pipeline queue                   Show project execution queue
  /pipeline budget                  Show budget status

PARALLEL EXECUTION
------------------
  /pipeline queue-add <project> [priority]  Add project to execution queue
  /pipeline run-parallel [N]        Run up to N projects in parallel (default: 3)
  /pipeline status-all              Show status of all projects

RECOVERY
--------
  /pipeline dlq                     Show dead letter queue
  /pipeline checkpoints             List checkpoints
  /pipeline resume <checkpoint>     Resume from checkpoint
  /pipeline retry <agent>           Retry failed agent
  /pipeline abort <agent>           Abort stuck agent
  /pipeline run-agent <agent>       Auto-diagnose and fix agent
  /pipeline circuit-reset           Reset circuit breakers and locks
  /pipeline mark-complete <project> <stage> [verdict]  Mark stage as complete

MODELS
------
  /models list                      See current model tier
  /models recommended               Switch to recommended tier
  /models cheap                     Switch to cheap tier
  /models hybrid                    Switch to hybrid tier
  /models zenfree                   Switch to ZenFree tier
  /models orouterfree               Switch to OpenRouter free tier
  /models premium                   Switch to premium tier (NEW)
  /models education                 Switch to education tier (NEW)

EXAMPLES
--------
  /pipeline new "Build a task management app"
  /pipeline run documentation
  /pipeline run documentation,deploy
  /pipeline run architect --model openrouter/claude-sonnet
  /pipeline continue                (auto-detects project)
  /pipeline continue <project>       (explicit)
  /pipeline continue <any-project>   (any product)
  /pipeline fix "login button not responding"

PIPELINE STAGES (9 total)
----------------------
  Stage 0: Ideation      - Capture idea, platform preferences
  Stage 1: Design        - Wireframes, user flows, components
  Stage 2: Architect     - Tech stack, deployment architecture
  Stage 3: Review       - Design & architecture validation
  Stage 4: Implement     - Code across API/DB/UI/UX/Logic layers
  Stage 5: Validate     - Unit, integration, E2E tests, security
  Stage 6: Fix          - Resolve validation failures
  Stage 7: Document     - README, guides, API docs, PDF (NEW)
  Stage 8: Package      - BOM, installers, security audit (NEW)

VIEW ARCHITECTURE
----------------
  /pipeline architecture            Show pipeline architecture overview
  products/<project>/architecture/  Contains:
    - pipeline-architecture.drawio  Draw.io diagram
    - architecture-overview.html     HTML overview (print to PDF)
    - generate_pdf.py              PDF generator script
""")


def list_projects():
    """List all projects with their status."""
    print("PROJECTS\n========\n")
    
    index_file = PRODUCTS_DIR / "index.json"
    if not index_file.exists():
        print("No projects found. Create one with: /pipeline new <idea>")
        return
    
    with open(index_file) as f:
        data = json.load(f)
    
    projects = data.get("products", [])
    
    if not projects:
        print("No projects found. Create one with: /pipeline new <idea>")
        return
    
    for project_name in projects:
        project_dir = PRODUCTS_DIR / project_name
        pipeline_file = project_dir / "pipeline.json"
        
        print(f"Project: {project_name}")
        
        if pipeline_file.exists():
            with open(pipeline_file) as f:
                config = json.load(f)
            
            current_stage = config.get("current_stage", "Not started")
            model_tier = config.get("model_tier", "recommended")
            
            print(f"|-- Current Stage: {current_stage}")
            print(f"|-- Model Tier: {model_tier}")
            
            # Count checkpoints, selective runs, DLQ
            checkpoints_dir = project_dir / "checkpoints"
            selective_dir = project_dir / "selective_runs"
            dlq_dir = project_dir / "dlq"
            
            checkpoint_count = len(list(checkpoints_dir.glob("*.json"))) if checkpoints_dir.exists() else 0
            selective_count = len(list(selective_dir.glob("*.json"))) if selective_dir.exists() else 0
            dlq_count = len(list(dlq_dir.glob("*.json"))) if dlq_dir.exists() else 0
            
            print(f"|-- Checkpoints: {checkpoint_count}")
            print(f"|-- Selective Runs: {selective_count}")
            print(f"-- Dead Letter Queue: {dlq_count}")
        else:
            print("-- No pipeline configuration found")
        
        print()


def list_agents():
    """List available agents."""
    print("AVAILABLE AGENTS\n================\n")
    
    if not AGENTS_DIR.exists():
        print("No agents found. Check .opencode/agent/ directory.")
        return
    
    # Define correct order for pipeline agents
    agent_order = ["ideation", "design", "architect", "review", "implement", "validate", "fix", "document", "package"]
    
    # Get all agent files
    agent_files = {}
    for agent_file in AGENTS_DIR.glob("*.md"):
        agent_files[agent_file.stem] = agent_file
    
    if not agent_files:
        print("No agents found. Check .opencode/agent/ directory.")
        return
    
    print(f"{'#':<4} {'Agent':<15} {'Model':<40} {'Status':<10}")
    print("-" * 70)
    
    for i, agent_name in enumerate(agent_order):
        if agent_name not in agent_files:
            continue
            
        agent_file = agent_files[agent_name]
        
        # Read YAML frontmatter to get model
        model = "unknown"
        try:
            with open(agent_file, encoding='utf-8') as f:
                content = f.read()
                for line in content.split("\n"):
                    if line.startswith("model:"):
                        model = line.split(":", 1)[1].strip()
                        break
        except:
            pass
        
        print(f"{i:<4} {agent_name:<15} {model:<40} enabled")
    
    print(f"\nUSAGE\n=====")
    print("  /pipeline run <agent>             Run single agent")
    print("  /pipeline run <agent1>,<agent2>   Run multiple agents")
    print("  /pipeline run <agent> --model X   Run with model override")


def list_selective_runs(project=None):
    """List selective runs for a project."""
    print("SELECTIVE RUNS\n==============\n")
    
    selective_dir = PRODUCTS_DIR / project / "selective_runs"
    
    if not selective_dir.exists():
        print("No selective runs yet. Use /pipeline run <agent> to run specific agents.")
        return
    
    run_files = list(selective_dir.glob("*.json"))
    
    if not run_files:
        print("No selective runs yet. Use /pipeline run <agent> to run specific agents.")
        return
    
    print(f"{'Run ID':<20} {'Agent(s)':<20} {'Status':<15} {'Timestamp':<25}")
    print("-" * 80)
    
    for run_file in sorted(run_files):
        try:
            with open(run_file) as f:
                data = json.load(f)
            
            run_id = data.get("id", run_file.stem)
            agents = ", ".join(data.get("agents", ["unknown"]))
            status = data.get("status", "unknown")
            timestamp = data.get("timestamp", "unknown")
            
            print(f"{run_id:<20} {agents:<20} {status:<15} {timestamp:<25}")
        except:
            print(f"{run_file.stem:<20} {'unknown':<20} {'error':<15} {'unknown':<25}")


def test_infrastructure(project=None):
    """Test pipeline infrastructure."""
    print("PIPELINE INFRASTRUCTURE TEST\n============================\n")
    
    checks = []
    
    # Check project structure
    project_dir = PRODUCTS_DIR / project
    dirs_to_check = ["docs", "reports", "checkpoints", "selective_runs", "dlq"]
    
    print("Project Structure:")
    for d in dirs_to_check:
        dir_path = project_dir / d
        exists = dir_path.exists()
        status = "EXISTS" if exists else "MISSING"
        print(f"  - products/{project}/{d}/: {status}")
        checks.append(exists)
    
    # Check pipeline.json
    pipeline_file = project_dir / "pipeline.json"
    print(f"\nPipeline Configuration:")
    if pipeline_file.exists():
        try:
            with open(pipeline_file) as f:
                json.load(f)
            print(f"  - pipeline.json: VALID")
            checks.append(True)
        except:
            print(f"  - pipeline.json: INVALID")
            checks.append(False)
    else:
        print(f"  - pipeline.json: MISSING")
        checks.append(False)
    
    # Check agent files
    print(f"\nAgent Files:")
    required_agents = ["ideation", "design", "architect", "review", "implement", "code-review", "validate", "fix", "document", "package"]
    for agent in required_agents:
        agent_file = AGENTS_DIR / f"{agent}.md"
        exists = agent_file.exists()
        status = "EXISTS" if exists else "MISSING"
        print(f"  - {agent}.md: {status}")
        checks.append(exists)
    
    # Overall result
    overall = all(checks)
    print(f"\nOverall: {'PASS' if overall else 'FAIL'}")


def show_health(project=None):
    """Show health status."""
    print("HEALTH STATUS\n=============\n")
    
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not pipeline_file.exists():
        print(f"Project: {project}")
        print("No pipeline configuration found.")
        return
    
    with open(pipeline_file) as f:
        config = json.load(f)
    
    print(f"Project: {project}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    # Circuit breakers
    print("Circuit Breakers")
    print("----------------")
    circuit_breakers = config.get("circuit_breakers", {})
    if circuit_breakers:
        for agent, state in circuit_breakers.items():
            status = state.get("state", "unknown").upper()
            failures = state.get("failures", 0)
            print(f"  {agent:<15} {status:<15} (failures: {failures})")
    else:
        print("  No circuit breakers configured")
    
    # Checkpoints
    checkpoints_dir = PRODUCTS_DIR / project / "checkpoints"
    checkpoint_count = len(list(checkpoints_dir.glob("*.json"))) if checkpoints_dir.exists() else 0
    
    print(f"\nCheckpoints")
    print("-----------")
    print(f"  Total: {checkpoint_count}")
    
    # Selective runs
    selective_dir = PRODUCTS_DIR / project / "selective_runs"
    selective_count = len(list(selective_dir.glob("*.json"))) if selective_dir.exists() else 0
    
    print(f"\nSelective Runs")
    print("--------------")
    print(f"  Total: {selective_count}")
    
    # DLQ
    dlq_dir = PRODUCTS_DIR / project / "dlq"
    dlq_count = len(list(dlq_dir.glob("*.json"))) if dlq_dir.exists() else 0
    
    print(f"\nDead Letter Queue")
    print("-----------------")
    print(f"  Total: {dlq_count}")


def list_checkpoints(project=None):
    """List checkpoints (Phase 1.2: Checkpoint/Resume System)."""
    print("CHECKPOINTS")
    print("===========")
    print()
    
    if CORE_AVAILABLE and 'CheckpointManager' in CoreImports:
        # Use Phase 1.2 CheckpointManager
        try:
            mgr = CoreImports['CheckpointManager'](project, str(PRODUCTS_DIR))
            checkpoints = mgr.list_checkpoints()
            
            print(f"Project: {project}")
            print(f"Total: {len(checkpoints)}")
            print()
            
            if not checkpoints:
                print("No checkpoints found.")
                return
            
            print(f"{'Checkpoint ID':<35} {'Stage':<8} {'Stage Name':<20} {'Created'}")
            print("-" * 90)
            
            for ckpt in checkpoints:
                print(f"{ckpt['id']:<35} {ckpt['stage']:<8} {ckpt.get('stage_name', 'unknown'):<20} {ckpt['created_at'][:19]}")
            return
        except Exception as e:
            print(f"Core module error: {e}, falling back to legacy")
    
    # Legacy implementation
    checkpoints_dir = PRODUCTS_DIR / project / "checkpoints"
    
    if not checkpoints_dir.exists():
        print(f"Project: {project}")
        print("No checkpoints found.")
        return
    
    checkpoint_files = list(checkpoints_dir.glob("*.json"))
    
    print(f"Project: {project}")
    print(f"Total: {len(checkpoint_files)}")
    print()
    
    if not checkpoint_files:
        print("No checkpoints found.")
        return
    
    print(f"{'Checkpoint ID':<35} {'Agent':<15} {'Timestamp':<25} {'Status':<10}")
    print("-" * 85)
    
    for cf in sorted(checkpoint_files):
        try:
            with open(cf) as f:
                data = json.load(f)
            
            cp_id = data.get("id", cf.stem)
            agent = data.get("agent", "unknown")
            timestamp = data.get("timestamp", "unknown")
            status = data.get("status", "unknown")
            
            print(f"{cp_id:<35} {agent:<15} {timestamp:<25} {status:<10}")
        except:
            print(f"{cf.stem:<35} {'unknown':<15} {'unknown':<25} {'error':<10}")


def list_dlq(project=None):
    """List dead letter queue (Phase 1.3)."""
    print("DEAD LETTER QUEUE")
    print("=================")
    print()
    
    if CORE_AVAILABLE and 'DeadLetterQueue' in CoreImports:
        try:
            dlq = CoreImports['DeadLetterQueue'](project, str(PRODUCTS_DIR))
            stats = dlq.get_stats()
            items = dlq.list_items()
            
            print(f"Project: {project}")
            print(f"Total: {stats['total']}")
            print(f"  Pending: {stats['pending']}")
            print(f"  In Review: {stats['in_review']}")
            print(f"  Retry Scheduled: {stats['retry_scheduled']}")
            print(f"  Resolved: {stats['resolved']}")
            print(f"  Abandoned: {stats['abandoned']}")
            print()
            
            if not items:
                print("No failed tasks in queue.")
                return
            
            print(f"{'Item ID':<30} {'Stage':<8} {'Agent':<15} {'Error Type':<15} {'Status'}")
            print("-" * 90)
            
            for item in items[:20]:
                print(f"{item.id:<30} {item.stage:<8} {item.agent:<15} {item.error_type:<15} {item.status}")
            
            if len(items) > 20:
                print(f"\n... and {len(items) - 20} more")
            return
        except Exception as e:
            print(f"Core module error: {e}, falling back to legacy")
    
    # Legacy
    dlq_dir = PRODUCTS_DIR / project / "dlq"
    
    print(f"Project: {project}")
    
    if not dlq_dir.exists():
        print("Total: 0")
        return
    
    dlq_files = list(dlq_dir.glob("*.json"))
    print(f"Total: {len(dlq_files)}")
    print()
    
    if not dlq_files:
        print("No failed tasks in queue.")
        return
    
    print(f"{'Task ID':<20} {'Agent':<15} {'Error':<30} {'Retries':<10} {'Timestamp':<25}")
    print("-" * 100)
    
    for df in sorted(dlq_files):
        try:
            with open(df) as f:
                data = json.load(f)
            
            task_id = data.get("id", df.stem)
            agent = data.get("agent", "unknown")
            error = data.get("error", {}).get("message", "unknown")[:30]
            attempts = data.get("attempts", 0)
            timestamps = data.get("timestamps", [])
            timestamp = timestamps[-1] if timestamps else "unknown"
            
            print(f"{task_id:<20} {agent:<15} {error:<30} {attempts:<10} {timestamp:<25}")
        except:
            print(f"{df.stem:<20} {'unknown':<15} {'error':<30} {'0':<10} {'unknown':<25}")


def acquire_lock(project):
    """Acquire execution lock for a project. Prevents concurrent execution."""
    if CORE_AVAILABLE:
        # Use Phase 1.2 LockManager (file-based, distributed-safe)
        lock_mgr = LockManager(str(PRODUCTS_DIR))
        return lock_mgr.acquire(project, holder="pipeline-cli", timeout=5)
    
    # Fallback to legacy implementation
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not pipeline_file.exists():
        return False
    
    with open(pipeline_file) as f:
        config = json.load(f)
    
    lock_info = config.get("lock", {})
    if lock_info.get("state") == "locked":
        return False
    
    # Set lock
    config["lock"] = {
        "state": "locked",
        "agent": "orchestrator",
        "timestamp": datetime.now().isoformat(),
        "ttl_seconds": 3600
    }
    with open(pipeline_file, 'w') as f:
        json.dump(config, f, indent=2)
    return True


def release_lock(project):
    """Release execution lock for a project."""
    if CORE_AVAILABLE:
        lock_mgr = LockManager(str(PRODUCTS_DIR))
        return lock_mgr.release(project)
    
    # Fallback
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not pipeline_file.exists():
        return False
    
    with open(pipeline_file) as f:
        config = json.load(f)
    
    config["lock"] = {
        "state": "unlocked",
        "agent": None,
        "timestamp": datetime.now().isoformat(),
        "ttl_seconds": 3600
    }
    with open(pipeline_file, 'w') as f:
        json.dump(config, f, indent=2)
    return True


def check_budget(project):
    """Check if project has sufficient budget to run."""
    budget_file = PRODUCTS_DIR / "budget.json"
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not budget_file.exists():
        return True  # No budget tracking = unlimited
    
    with open(budget_file) as f:
        budget = json.load(f)
    
    per_project = budget.get("per_project", {})
    if project not in per_project:
        # No budget set = unlimited
        return True
    
    project_budget = per_project[project]
    spent = project_budget.get("spent", 0)
    limit = project_budget.get("limit", 0)
    
    return spent < limit


def queue_project(project, priority=1):
    """Add a project to the execution queue (Phase 1.1)."""
    if CORE_AVAILABLE and 'QueueManager' in CoreImports:
        try:
            qm = CoreImports['QueueManager'](str(PRODUCTS_DIR))
            item = qm.enqueue(project, priority=priority)
            print(f"Project '{project}' added to queue with priority {priority}")
            pos = qm.is_in_queue(project) if hasattr(qm, 'is_in_queue') else None
            if pos:
                print(f"  Status: {pos}")
            return
        except Exception as e:
            print(f"Core module error: {e}, using legacy")
    
    # Legacy
    queue_file = PRODUCTS_DIR / "queue.json"
    
    if not queue_file.exists():
        queue_data = {"queue": [], "max_parallel": 3}
    else:
        with open(queue_file) as f:
            queue_data = json.load(f)
    
    # Check if already queued
    for item in queue_data.get("queue", []):
        if item.get("project") == project:
            print(f"Project '{project}' is already in queue")
            return
    
    queue_data.setdefault("queue", []).append({
        "project": project,
        "priority": priority,
        "timestamp": datetime.now().isoformat(),
        "status": "queued"
    })
    
    # Sort by priority (higher first), then timestamp
    queue_data["queue"].sort(key=lambda x: (-x.get("priority", 0), x.get("timestamp", "")))
    
    with open(queue_file, 'w') as f:
        json.dump(queue_data, f, indent=2)
    
    print(f"Project '{project}' added to queue with priority {priority}")


def show_queue(project=None):
    """Show the project queue (Phase 1.1)."""
    print("PROJECT QUEUE")
    print("=============")
    print()
    
    if CORE_AVAILABLE and 'QueueManager' in CoreImports:
        try:
            qm = CoreImports['QueueManager'](str(PRODUCTS_DIR))
            queue = qm.get_queue() if hasattr(qm, 'get_queue') else []
            size = qm.get_queue_size() if hasattr(qm, 'get_queue_size') else 0
            stats = qm.get_statistics() if hasattr(qm, 'get_statistics') else {}
            
            print(f"Max Parallel: {stats.get('max_parallel', 3)}")
            print(f"Total Queued: {size}")
            
            if stats:
                for k, v in stats.items():
                    if k not in ['max_parallel', 'queue']:
                        print(f"  {k.replace('_', ' ').title()}: {v}")
            print()
            
            if not queue:
                print("Queue is empty.")
                return
            
            # Show queue items
            if isinstance(queue, list):
                print(f"{'Project':<20} {'Priority':<10} {'Status'}")
                print("-" * 50)
                for item in queue:
                    if isinstance(item, dict):
                        proj = item.get("project", "unknown")
                        priority = item.get("priority", 1)
                        status = item.get("status", "queued")
                        print(f"{proj:<20} {priority:<10} {status}")
            else:
                print(f"Queue: {queue}")
            return
        except Exception as e:
            print(f"Core module error: {e}, using legacy")
    
    # Legacy
    queue_file = PRODUCTS_DIR / "queue.json"
    
    if not queue_file.exists():
        print("No queue file found. No projects queued.")
        return
    
    with open(queue_file) as f:
        queue_data = json.load(f)
    
    max_parallel = queue_data.get("max_parallel", 3)
    queue = queue_data.get("queue", [])
    
    print(f"Max Parallel: {max_parallel}")
    print(f"Queued Projects: {len(queue)}")
    print()
    
    if not queue:
        print("Queue is empty.")
        return
    
    print(f"{'Project':<20} {'Priority':<10} {'Status':<12} {'Queued At'}")
    print("-" * 70)
    
    for item in queue:
        proj = item.get("project", "unknown")
        priority = item.get("priority", 1)
        status = item.get("status", "queued")
        timestamp = item.get("timestamp", "unknown")
        print(f"{proj:<20} {priority:<10} {status:<12} {timestamp}")


def show_budget(project=None):
    """Show budget status (Phase 1.6: Token Telemetry)."""
    if CORE_AVAILABLE and 'BudgetTracker' in CoreImports:
        # Use Phase 1.6 BudgetTracker (real API)
        try:
            tracker = CoreImports['BudgetTracker'](str(PRODUCTS_DIR))
            
            print("BUDGET STATUS")
            print("=============")
            print()
            
            # Try to get window status (Phase 1.6 native API)
            try:
                windows = tracker.get_window_status()
                print("Time Window Budget:")
                for period_key, status in windows.items():
                    label = period_key.capitalize().ljust(10)
                    spent = status.get("spent", 0) if isinstance(status, dict) else status
                    limit = status.get("limit", 0) if isinstance(status, dict) else 0
                    pct = (spent / limit * 100) if limit > 0 else 0
                    print(f"  {label}: ${spent:.2f}/${limit:.2f} ({pct:.1f}%)")
            except (KeyError, AttributeError, TypeError):
                # Fallback: read budget.json directly
                _show_legacy_budget()
                return
            
            print("\nPer-Project Budget:")
            try:
                project_spend = tracker.get_project_spend(project)
                remaining = tracker.get_remaining_budget(project)
                print(f"  {'Project':<20} {'Spent':<12} {'Remaining':<12} {'Status'}")
                print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}")
                print(f"  {project:<20} ${project_spend:<11.2f} ${remaining:<11.2f} {'OK' if remaining > 0 else 'EXCEEDED'}")
            except (KeyError, AttributeError, TypeError):
                _show_legacy_budget()
                return
            
            # Show alerts
            try:
                alerts = tracker.get_alerts()
                if alerts:
                    print("\nAlerts:")
                    for alert in alerts:
                        print(f"  - {alert}")
            except (KeyError, AttributeError, TypeError):
                pass
            return
        except Exception as e:
            # Core module error, use legacy
            print(f"Core module error: {e}, using legacy mode")
    
    _show_legacy_budget()


def _show_legacy_budget():
    """Legacy budget display from products/budget.json."""
    budget_file = PRODUCTS_DIR / "budget.json"
    
    print("BUDGET STATUS")
    print("=============")
    print()
    
    if not budget_file.exists():
        print("No budget tracking configured.")
        return
    
    with open(budget_file) as f:
        budget = json.load(f)
    
    print("Time Window Budget:")
    for window in ["hourly", "daily", "weekly"]:
        if window in budget:
            w = budget[window]
            spent = w.get("spent", 0)
            limit = w.get("limit", 0)
            pct = (spent / limit * 100) if limit > 0 else 0
            print(f"  {window.capitalize():10}: ${spent}/${limit} ({pct:.1f}%)")
    
    print("\nPer-Project Budget:")
    per_project = budget.get("per_project", {})
    if per_project:
        print(f"  {'Project':<20} {'Spent':<12} {'Limit':<12} {'Usage'}")
        print(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}")
        for proj, info in per_project.items():
            spent = info.get("spent", 0)
            limit = info.get("limit", 0)
            pct = (spent / limit * 100) if limit > 0 else 0
            print(f"  {proj:<20} ${spent:<11.2f} ${limit:<11.2f} {pct:.1f}%")
    else:
        print("  No per-project budgets set")


def show_project_status(project=None):
    """Show detailed project status."""
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not pipeline_file.exists():
        print(f"Project '{project}' not found.")
        return
    
    with open(pipeline_file) as f:
        config = json.load(f)
    
    print(f"PROJECT STATUS: {project}")
    print("=" * 50)
    
    print(f"Product Type: {config.get('product_type', 'unknown')}")
    print(f"Current Stage: {config.get('current_stage', 'unknown')}")
    print(f"Model Tier: {config.get('model_tier', 'recommended')}")
    print(f"Quality Tier: {config.get('quality_tier', 'standard')}")
    
    lock_info = config.get("lock", {})
    lock_state = lock_info.get("state", "unlocked")
    print(f"\nLock Status: {lock_state}")
    if lock_info.get("timestamp"):
        print(f"  Locked at: {lock_info['timestamp']}")
    
    print("\nStage Progress:")
    stages = config.get("stages", {})
    # Sort stages: numeric first, then alphanumeric (7a, 7b, 7c, 10, 11, 12)
    def stage_sort_key(s):
        # Try to extract numeric prefix
        import re
        m = re.match(r'(\d+)', s)
        if m:
            return (int(m.group(1)), s)
        return (999, s)
    for stage_num in sorted(stages.keys(), key=stage_sort_key):
        stage = stages[stage_num]
        name = stage.get("name", "unknown")
        status = stage.get("status", "pending")
        agent = stage.get("agent", "none")
        print(f"  Stage {stage_num}: {name} ({agent}) - {status}")
    
    print("\nCircuit Breakers:")
    breakers = config.get("circuit_breakers", {})
    for agent, state in breakers.items():
        status = state.get("state", "closed")
        failures = state.get("failures", 0)
        marker = "[OPEN]" if status == "open" else "[OK]"
        print(f"  {marker} {agent:<15} {status:<10} (failures: {failures})")
    
    # Check checkpoints
    checkpoints_dir = PRODUCTS_DIR / project / "checkpoints"
    checkpoint_count = len(list(checkpoints_dir.glob("*.json"))) if checkpoints_dir.exists() else 0
    print(f"\nCheckpoints: {checkpoint_count}")
    
    # Check DLQ
    dlq_dir = PRODUCTS_DIR / project / "dlq"
    dlq_count = len(list(dlq_dir.glob("*.json"))) if dlq_dir.exists() else 0
    print(f"DLQ Items: {dlq_count}")


def circuit_reset(project=None):
    """Reset all circuit breakers and locks for a project (Phase 1.7)."""
    if CORE_AVAILABLE and 'CircuitBreakerRegistry' in CoreImports:
        # Use core CircuitBreakerRegistry and LockManager
        try:
            registry = CoreImports['CircuitBreakerRegistry']()
            registry.reset_all() if hasattr(registry, 'reset_all') else None
            
            if 'LockManager' in CoreImports:
                lock_mgr = CoreImports['LockManager'](str(PRODUCTS_DIR))
                lock_released = lock_mgr.release(project) if hasattr(lock_mgr, 'release') else False
            else:
                lock_released = False
            
            print(f"Circuit breakers reset for '{project}'")
            if lock_released:
                print(f"Lock released for '{project}'")
            else:
                print(f"No lock to release for '{project}'")
            return
        except Exception as e:
            print(f"Core module error: {e}, using legacy")
    
    # Fallback to legacy
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    
    if not pipeline_file.exists():
        print(f"Project '{project}' not found.")
        return
    
    with open(pipeline_file) as f:
        config = json.load(f)
    
    # Reset all circuit breakers
    if "circuit_breakers" in config:
        for agent in config["circuit_breakers"]:
            config["circuit_breakers"][agent]["state"] = "closed"
            config["circuit_breakers"][agent]["failures"] = 0
            config["circuit_breakers"][agent]["last_failure"] = None
    
    # Clear lock
    config["lock"] = {
        "state": "unlocked",
        "agent": None,
        "timestamp": datetime.now().isoformat(),
        "ttl_seconds": 3600
    }
    
    with open(pipeline_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Circuit breakers reset for '{project}'")
    print(f"Lock released for '{project}'")


def show_architecture():
    """Show pipeline architecture (the system itself, not per-project)."""
    print("""
PIPELINE ARCHITECTURE (The Multi-Agent Pipeline System)
=======================================================

This shows the architecture of the PIPELINE ITSELF - how the system works.

Pipeline Architecture Files:
  .opencode/pipeline-architecture/
    - pipeline-architecture.drawio    Visual architecture diagram
    - architecture-overview.html     HTML overview (print to PDF)
    - README.md                      Documentation
    - generate_pdf.py                PDF generator script
    - pipeline-architecture.pdf      Generated PDF

PIPELINE SYSTEM OVERVIEW:
  - 9 Stages (0-8): Ideation -> Design -> Architect -> Review ->
                     Implement -> Validate -> Fix -> Document -> Package
  - 15+ Agents including sub-agents for implementation
  - 7 Model Tiers: recommended, cheap, hybrid, zenfree, orouterfree, premium, education
  - Supports multiple projects with per-project configuration
  - Parallel execution with locks, queue, and budget tracking

DOCUMENTATION REFERENCE:
  .opencode/docs/
    - product-type-classification.md  Product type taxonomy & adaptive questions

TO GENERATE PDF:
  cd .opencode/pipeline-architecture
  python generate_pdf.py
  OR
  Open pipeline-architecture.drawio in draw.io app -> Export as PDF
""")
    architecture_dir = ROOT / ".opencode" / "pipeline-architecture"
    if architecture_dir.exists():
        print("Pipeline architecture files:")
        for f in architecture_dir.iterdir():
            size = f.stat().st_size if f.is_file() else 0
            size_kb = size / 1024 if size > 0 else 0
            print(f"  - {f.name:<50} {size_kb:>8.1f} KB")
    else:
        print("No architecture files found.")


def show_project_architecture(project=None):
    """Show project architecture (the product being built)."""
    project_dir = PRODUCTS_DIR / project
    architecture_dir = project_dir / "architecture"
    
    print(f"""
PROJECT ARCHITECTURE: {project}
=====================

This shows the architecture of the PRODUCT being built for project '{project}'.
Project architecture files are in: products/{project}/architecture/

PRODUCT CONFIGURATION:
  - project-config.json     Project decisions, platform, model tier
  - pipeline.json          Pipeline state, stage progress, agents
  - design/                Wireframes, user flows, components
  - docs/                  Requirements, review, documentation
  - architecture/          Product architecture diagrams
  - src/                   Source code
  - reports/               Test results, code review, issues
  - dist/                  Distribution packages
""")
    
    if architecture_dir.exists():
        files = list(architecture_dir.iterdir())
        if files:
            print("Project architecture files:")
            for f in files:
                size = f.stat().st_size if f.is_file() else 0
                size_kb = size / 1024 if size > 0 else 0
                print(f"  - {f.name:<50} {size_kb:>8.1f} KB")
        else:
            print("No project architecture files yet (generated during design stage).")
    else:
        print(f"No architecture directory for project '{project}' yet.")
        print("Run /pipeline new or continue to generate architecture.")


def continue_pipeline(project=None):
    """Resume an interrupted pipeline for a specific project."""
    print(f"PIPELINE CONTINUE - {project}")
    print("=" * 50)
    print()

    project_dir = PRODUCTS_DIR / project
    pipeline_file = project_dir / "pipeline.json"
    pipeline_state_file = project_dir / "docs" / "pipeline-state.md"
    agent_context_file = project_dir / "docs" / "agent-context.md"

    # Check if project exists
    if not project_dir.exists():
        print(f"ERROR: Project '{project}' not found.")
        print(f"Available projects:")
        list_projects()
        print()
        print(f"To start a new pipeline:")
        print(f"  /pipeline new <idea>")
        return

    # Check pipeline config
    if not pipeline_file.exists():
        print(f"ERROR: No pipeline configuration for project '{project}'.")
        print(f"Start a new pipeline with: /pipeline new <idea>")
        return

    with open(pipeline_file) as f:
        config = json.load(f)

    current_stage = config.get("current_stage", 0)
    model_tier = config.get("model_tier", "recommended")
    product_type = config.get("product_type", "general")

    print(f"Project: {project}")
    print(f"Product Type: {product_type}")
    print(f"Model Tier: {model_tier}")
    print()

    # Try to read pipeline state
    stage_names = {
        0: "Ideation",
        1: "Design",
        2: "Architect",
        3: "Review",
        4: "Implement",
        5: "Code Review",
        6: "Validate",
        7: "Fix",
        8: "Document",
        9: "Package"
    }

    if pipeline_state_file.exists():
        print("Pipeline State File Found")
        print("-" * 30)

        with open(pipeline_state_file, encoding='utf-8') as f:
            content = f.read()

        # Parse the pipeline state to find last completed stage
        lines = content.split('\n')
        last_completed_stage = -1
        last_agent = "unknown"
        last_status = "unknown"
        completed_stages = []

        for line in lines:
            if line.startswith('|') and not line.startswith('|---'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 5:
                    # Check if this looks like a pipeline state row
                    stage_str = parts[2] if len(parts) > 2 else ""
                    agent_str = parts[3] if len(parts) > 3 else ""
                    status_str = parts[4] if len(parts) > 4 else ""

                    # Try to extract stage number
                    if "Stage" in stage_str:
                        match = re.search(r'Stage\s+(\d+)', stage_str)
                        if match:
                            stage_num = int(match.group(1))
                            if status_str.lower() in ("completed", "done", "passed"):
                                if stage_num > last_completed_stage:
                                    last_completed_stage = stage_num
                                    last_agent = agent_str
                                    last_status = status_str
                                completed_stages.append((stage_num, agent_str, status_str))

        if last_completed_stage >= 0:
            next_stage = last_completed_stage + 1
            if next_stage in stage_names:
                print(f"  Last Completed: Stage {last_completed_stage} - {stage_names.get(last_completed_stage, 'Unknown')} ({last_agent})")
                print(f"  Resume From: Stage {next_stage} - {stage_names[next_stage]}")
                print(f"  Completed Stages: {len(completed_stages)}")
            else:
                print(f"  Pipeline appears COMPLETE (all {last_completed_stage} stages done)")
                print(f"  To start a new pipeline: /pipeline new <idea>")
                return
        else:
            print("  No completed stages found in pipeline state.")
            print(f"  Starting from: Stage 0 - Ideation")
            next_stage = 0
    else:
        print("No pipeline state file found.")
        print(f"  Starting from: Stage 0 - Ideation")
        next_stage = 0

    # Check checkpoints
    checkpoints_dir = project_dir / "checkpoints"
    if checkpoints_dir.exists():
        checkpoint_files = list(checkpoints_dir.glob("*.json"))
        print(f"  Checkpoints: {len(checkpoint_files)}")
    else:
        print(f"  Checkpoints: 0")

    # Check agent context
    if agent_context_file.exists():
        print()
        print("Agent Context Found")
        print("-" * 30)
        with open(agent_context_file, encoding='utf-8') as f:
            context = f.read()
        # Show first few lines
        context_lines = context.split('\n')[:10]
        for line in context_lines:
            if line.strip():
                print(f"  {line}")
    else:
        print("No agent context file found.")

    # Provide instructions
    print()
    print("=" * 50)
    print("CONTINUE INSTRUCTIONS")
    print("=" * 50)
    print()
    print("To continue this pipeline, run:")
    print()
    if next_stage == 0:
        print(f"  /pipeline new \"<your idea>\"")
    else:
        print(f"  /pipeline continue  (or tell the AI: 'Continue the {project} pipeline')")
    print()
    print("This will resume from the last completed stage.")
    print()

    # Show what each remaining stage does
    remaining_stages = list(range(next_stage, min(10, 10)))
    if remaining_stages:
        print("Remaining Stages:")
        for stage in remaining_stages:
            if stage in stage_names:
                status = "DONE" if stage < next_stage else "PENDING"
                print(f"  Stage {stage}: {stage_names[stage]} - {status}")
        print()

    # Check for any issues
    dlq_dir = project_dir / "dlq"
    if dlq_dir.exists():
        dlq_files = list(dlq_dir.glob("*.json"))
        if dlq_files:
            print(f"WARNING: {len(dlq_files)} tasks in dead letter queue.")
            print(f"  Run /pipeline dlq {project} to review.")
            print()


def mark_stage_complete(project, stage_num, verdict=None):
    """Mark a stage as complete in pipeline.json."""
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    if not pipeline_file.exists():
        print(f"Pipeline file not found for {project}")
        return

    with open(pipeline_file) as f:
        config = json.load(f)

    stages = config.get("stages", {})
    stage_key = str(stage_num)

    if stage_key in stages:
        stages[stage_key]["status"] = "completed"
        stages[stage_key]["timestamp"] = datetime.now().isoformat()
        if verdict:
            stages[stage_key]["verdict"] = verdict

    # Check if all stages are done
    all_done = all(
        s.get("status") == "completed"
        for s in stages.values()
    )
    if all_done:
        config["current_stage"] = "complete"
        config["pipeline_complete"] = True
        config["completed_at"] = datetime.now().isoformat()

    with open(pipeline_file, 'w') as f:
        json.dump(config, f, indent=2)

    print(f"Stage {stage_num} marked as complete for {project}")


# ======================================================================
# Phase 1 Feature Commands (version, log, review, ledger, skills, report)
# ======================================================================

def show_version(project=None):
    """Show project version (Phase 1.10: Semantic Versioning)."""
    if CORE_AVAILABLE and 'VersionManager' in CoreImports:
        try:
            vm = CoreImports['VersionManager'](project, str(PRODUCTS_DIR))
            info = vm.get_version_info() if hasattr(vm, 'get_version_info') else {"version": vm.get_current_version()}
            
            print("VERSION INFO")
            print("============")
            print()
            print(f"Project: {project}")
            print(f"Version: {info.get('version', 'unknown')}")
            print(f"Git Tag: {info.get('git_tag', 'unknown')}")
            if info.get('last_bump'):
                print(f"Last Bump: {info['last_bump']} at {info.get('last_bump_at', 'unknown')}")
            if info.get('changelog_entries'):
                print(f"Changelog Entries: {info['changelog_entries']}")
            return
        except Exception as e:
            print(f"Core module error: {e}")
    
    print(f"No version info available for {project}")


def show_log(project=None, options=None):
    """Show project log (Phase 1.5: Logging)."""
    options = options or []
    level = options[0] if options else "INFO"
    limit = int(options[1]) if len(options) > 1 else 20
    
    if CORE_AVAILABLE and 'ProductLogger' in CoreImports:
        try:
            logger = CoreImports['ProductLogger'](project, str(PRODUCTS_DIR))
            logs = logger.get_logs(level=level, limit=limit) if hasattr(logger, 'get_logs') else []
            
            print("PROJECT LOG")
            print("===========")
            print(f"Level: {level} | Limit: {limit}")
            print()
            
            if not logs:
                print("No log entries.")
                return
            
            for entry in logs:
                print(f"[{entry.level}] Stage {entry.stage} {entry.stage_name} | {entry.agent}: {entry.message}")
            return
        except Exception as e:
            print(f"Core module error: {e}")
    
    print(f"No log available for {project}")


def show_reviews(project=None):
    """Show cross-review status (Phase 1.4)."""
    if CORE_AVAILABLE and 'CrossReviewManager' in CoreImports:
        try:
            crm = CoreImports['CrossReviewManager'](project, str(PRODUCTS_DIR))
            
            print("CROSS REVIEWS")
            print("=============")
            print()
            
            metrics = crm.get_review_metrics() if hasattr(crm, 'get_review_metrics') else {}
            if metrics:
                print(f"Total Reviews: {metrics.get('total_reviews', 0)}")
                print(f"Completed: {metrics.get('completed', 0)}")
                print(f"Approved: {metrics.get('approved', 0)}")
                print(f"Changes Required: {metrics.get('changes_required', 0)}")
                print(f"Total Feedback: {metrics.get('total_feedback', 0)}")
                print(f"Open Feedback: {metrics.get('open_feedback', 0)}")
                print()
            
            # List pending reviews
            if hasattr(crm, 'list_reviews'):
                pending = crm.list_reviews(status="pending")
                if pending:
                    print("Pending Reviews:")
                    for r in pending:
                        print(f"  {r.id}: {r.target_agent} -> {r.reviewer_agent} (stage {r.stage})")
            return
        except Exception as e:
            print(f"Core module error: {e}")
    
    print(f"No review data available for {project}")


def show_ledger(project=None):
    """Show agent ledger (Phase 1.4: Independent Evaluator)."""
    if CORE_AVAILABLE and 'AgentLedger' in CoreImports:
        try:
            ledger = CoreImports['AgentLedger'](str(PRODUCTS_DIR))
            
            print("AGENT LEDGER")
            print("============")
            print()
            
            summary = ledger.get_project_summary(project) if hasattr(ledger, 'get_project_summary') else {}
            if summary:
                print(f"Project: {project}")
                print(f"Total Work: {summary.get('total_work', 0)}")
                print(f"Completed: {summary.get('completed', 0)}")
                print(f"Failed: {summary.get('failed', 0)}")
                print(f"Success Rate: {summary.get('success_rate', 0)}%")
                print(f"Total Cost: ${summary.get('total_cost', 0):.4f}")
                print(f"Total Tokens: {summary.get('total_tokens', 0)}")
                
                if summary.get('agents_used'):
                    print(f"Agents Used: {', '.join(summary['agents_used'])}")
            print()
            
            # Recent work
            recent = ledger.get_recent_work(limit=10) if hasattr(ledger, 'get_recent_work') else []
            if recent:
                print("Recent Work:")
                for w in recent:
                    if w.project == project:
                        print(f"  [{w.timestamp[:19]}] {w.agent} - {w.action} ({w.status})")
            return
        except Exception as e:
            print(f"Core module error: {e}")
    
    print(f"No ledger data for {project}")


def show_skills():
    """Show skills registry (Phase 2.6: Skill Validation)."""
    if CORE_AVAILABLE and 'SkillsRegistry' in CoreImports:
        try:
            registry = CoreImports['SkillsRegistry'](str(PRODUCTS_DIR))
            
            print("SKILLS REGISTRY")
            print("===============")
            print()
            
            skills = registry.list_skills() if hasattr(registry, 'list_skills') else []
            print(f"Total Skills: {len(skills)}")
            
            # Group by category
            by_category: dict = {}
            for s in skills:
                by_category.setdefault(s.category, []).append(s)
            
            for category, items in sorted(by_category.items()):
                print(f"\n  [{category.upper()}] ({len(items)} skills)")
                for s in items[:3]:
                    print(f"    - {s.id}: {s.name}")
                if len(items) > 3:
                    print(f"    ... and {len(items) - 3} more")
            
            # MCP servers
            mcps = registry.list_mcp_servers() if hasattr(registry, 'list_mcp_servers') else []
            print(f"\nMCP Servers: {len(mcps)}")
            for m in mcps:
                print(f"  - {m.id}: {m.name}")
            
            # Model recommendations
            models = registry.list_model_recommendations() if hasattr(registry, 'list_model_recommendations') else []
            print(f"\nModel Recommendations: {len(models)}")
            for m in models:
                print(f"  - {m.use_case}: {m.recommended_model} (provider: {m.provider})")
            return
        except Exception as e:
            print(f"Core module error: {e}")
    
    print("Skills registry not available")


def show_full_report(project=None):
    """Show comprehensive project report combining all Phase 1 features."""
    print("=" * 60)
    print(f"  COMPREHENSIVE REPORT: {project}")
    print("=" * 60)
    print()
    
    show_project_status(project)
    print()
    print("-" * 60)
    print()
    show_budget(project)
    print()
    print("-" * 60)
    print()
    show_ledger(project)
    print()
    print("-" * 60)
    print()
    show_reviews(project)
    print()
    print("=" * 60)


# ======================================================================
# Phase 1-3 Feature Commands
# ======================================================================

def show_models():
    """Show model registry (Phase 1.1: Model Capability Registry)."""
    if CORE_AVAILABLE and 'ModelCapabilityRegistry' in CoreImports:
        try:
            registry = CoreImports['ModelCapabilityRegistry'](str(PRODUCTS_DIR))
            summary = registry.get_summary()
            
            print("MODEL REGISTRY (Phase 1.1)")
            print("==========================")
            print()
            print(f"Total Models: {summary['total_models']}")
            print(f"Enabled: {summary['enabled']}")
            print(f"Disabled: {summary['disabled']}")
            print()
            print("By Tier:")
            for tier, count in summary.get('by_tier', {}).items():
                print(f"  {tier:12}: {count} models")
            print()
            print("By Capability:")
            for cap, count in summary.get('by_capability', {}).items():
                print(f"  {cap:20}: {count} models")
            print()
            
            # Show fallback chains
            print("Fallback Chains:")
            for cap in summary.get('fallback_chains', []):
                chain = registry.get_fallback_chain(cap)
                names = [m.name for m in chain[:3]]
                print(f"  {cap}: {' -> '.join(names)}" + ("..." if len(chain) > 3 else ""))
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Model registry not available")


def show_context(project=None):
    """Show context engine status (Phase 1.7: Context Engine)."""
    if CORE_AVAILABLE and 'ContextEngine' in CoreImports:
        try:
            engine = CoreImports['ContextEngine'](str(PRODUCTS_DIR))
            status = engine.get_budget_status()
            
            print("CONTEXT ENGINE (Phase 1.7)")
            print("==========================")
            print()
            print(f"Total Tokens: {engine.get_total_tokens()} / {engine.get_max_tokens()}")
            print()
            print("Budget by Type:")
            print(f"  {'Type':<20} {'Used':<10} {'Max':<10} {'Remaining':<10} {'Util'}")
            print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10} {'-'*6}")
            for ctx_type, info in status.items():
                print(f"  {ctx_type:<20} {info['current_tokens']:<10} {info['max_tokens']:<10} {info['remaining']:<10} {info['utilization']}%")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Context engine not available")


def show_stop_conditions():
    """Show stop conditions (Phase 1.8)."""
    if CORE_AVAILABLE and 'StopConditionManager' in CoreImports:
        try:
            mgr = CoreImports['StopConditionManager'](str(PRODUCTS_DIR))
            
            print("STOP CONDITIONS (Phase 1.8)")
            print("===========================")
            print()
            for c in mgr.conditions:
                status = "ON" if c.enabled else "OFF"
                print(f"  [{status}] {c.name}")
                print(f"       Metric: {c.metric}, Threshold: {c.threshold}, Action: {c.action}")
                if c.message:
                    print(f"       Message: {c.message}")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Stop conditions not available")


def show_escalations(project=None):
    """Show escalation requests (Phase 1.8)."""
    if CORE_AVAILABLE and 'StopConditionManager' in CoreImports:
        try:
            mgr = CoreImports['StopConditionManager'](str(PRODUCTS_DIR))
            stats = mgr.get_escalation_stats()
            
            print("ESCALATIONS (Phase 1.8)")
            print("========================")
            print()
            print(f"Total: {stats['total']}")
            print(f"Pending: {stats['pending']}")
            print(f"Resolved: {stats['resolved']}")
            print()
            print("By Priority:")
            for prio, count in stats.get('by_priority', {}).items():
                print(f"  {prio:10}: {count}")
            print()
            
            # List pending for project
            pending = mgr.list_escalations(project=project, status="pending")
            if pending:
                print(f"Pending Escalations" + (f" for {project}" if project else "") + ":")
                for e in pending[:10]:
                    print(f"  [{e.priority:8}] {e.id} - {e.agent} (stage {e.stage}): {e.reason}")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Escalations not available")


def show_tool_cache():
    """Show tool result cache (Phase 2.2)."""
    if CORE_AVAILABLE and 'ToolResultCache' in CoreImports:
        try:
            cache = CoreImports['ToolResultCache'](str(PRODUCTS_DIR))
            stats = cache.get_stats()
            
            print("TOOL RESULT CACHE (Phase 2.2)")
            print("=============================")
            print()
            print(f"Total Entries: {stats['total_entries']}")
            print(f"Total Hits: {stats['total_hits']}")
            print(f"Total Size: {stats['total_size_bytes']} bytes")
            print(f"Expired: {stats['expired_entries']}")
            print(f"Hit Rate: {stats['hit_rate']}")
            print(f"Max Entries: {stats['max_entries']}")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Tool cache not available")


def show_knowledge_router():
    """Show knowledge router status (Phase 2.3)."""
    if CORE_AVAILABLE and 'KnowledgeRouter' in CoreImports:
        try:
            router = CoreImports['KnowledgeRouter'](str(PRODUCTS_DIR))
            stats = router.get_stats()
            
            print("KNOWLEDGE ROUTER (Phase 2.3)")
            print("============================")
            print()
            print(f"Total Resources: {stats['total_resources']}")
            print(f"Total Tokens: {stats['total_tokens']}")
            print(f"Used: {stats['used_resources']}")
            print(f"Unused: {stats['unused_resources']}")
            print()
            print("By Domain:")
            for domain, count in stats.get('by_domain', {}).items():
                print(f"  {domain:15}: {count} resources")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Knowledge router not available")


def show_budget_allocation(project=None):
    """Show token budget allocation (Phase 2.4)."""
    if CORE_AVAILABLE and 'TokenBudgetAllocator' in CoreImports:
        try:
            allocator = CoreImports['TokenBudgetAllocator'](project, str(PRODUCTS_DIR))
            
            if not allocator.allocations:
                allocator.initialize_allocations()
            
            summary = allocator.get_summary()
            
            print("TOKEN BUDGET ALLOCATION (Phase 2.4)")
            print("====================================")
            print()
            print(f"Total Allocated: {summary['total_allocated']:,}")
            print(f"Total Used: {summary['total_used']:,}")
            print(f"Utilization: {summary['utilization']}%")
            print(f"Reallocations: {summary['reallocation_count']}")
            print()
            print("Per Stage:")
            print(f"  {'Stage':<25} {'Allocated':<12} {'Used':<12} {'Util'}")
            print(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*6}")
            for stage_num, data in summary.get('stages', {}).items():
                print(f"  {data['name']:<25} {data['allocated']:<12,} {data['used']:<12,} {data['utilization']}%")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Budget allocator not available")


def exit_pipeline(project):
    """Exit pipeline: release lock, cleanup, show final summary."""
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"
    if not pipeline_file.exists():
        print(f"Pipeline file not found for {project}")
        return

    with open(pipeline_file) as f:
        config = json.load(f)

    # Check if pipeline is complete
    if not config.get("pipeline_complete"):
        print(f"WARNING: Pipeline for {project} is not complete!")
        print("Are you sure you want to exit? (yes/no)")
        response = input("> ").strip().lower()
        if response != "yes":
            print("Exit cancelled.")
            return

    # Release lock
    lock_file = PRODUCTS_DIR / project / ".lock"
    if lock_file.exists():
        lock_file.unlink()
        print(f"Lock released for {project}")

    # Show final summary location
    summary_file = PRODUCTS_DIR / project / "docs" / "FINAL_SUMMARY.md"
    if summary_file.exists():
        print(f"\nFinal summary: {summary_file}")
    else:
        print(f"\nNo final summary found at {summary_file}")

    # Show pipeline stats
    stages = config.get("stages", {})
    completed = sum(1 for s in stages.values() if s.get("status") == "completed")
    total = len(stages)
    print(f"\nPipeline stages completed: {completed}/{total}")

    if config.get("completed_at"):
        print(f"Completed at: {config['completed_at']}")

    print(f"\nPipeline exited for {project}")
    print("To restart: /pipeline continue {project}")


def show_compliance(project=None, agent=None, stage=None):
    """
    Run compliance check for one or all agents in a project.

    Usage:
        pipeline.py compliance                     # All agents (current project)
        pipeline.py compliance <project>          # All agents for specific project
        pipeline.py compliance <project> <agent>  # Specific agent
        pipeline.py compliance <project> <agent> <stage>  # Specific agent + stage
    """
    project = resolve_project_arg(project)
    if not project:
        return
    
    try:
        from core.compliance_check import run_compliance_check
    except ImportError as e:
        print(f"Could not import compliance_check: {e}")
        return
    
    # Run the check
    result = run_compliance_check(project, agent, stage, products_dir=str(PRODUCTS_DIR))
    
    # Print formatted output
    if "summary" in result:
        summary = result["summary"]
        print(f"\n{'='*60}")
        print(f"  COMPLIANCE REPORT: {result.get('project', project)}")
        if agent:
            print(f"  Agent: {result.get('agent', agent)} | Stage: {result.get('stage', stage or 'N/A')}")
        print(f"{'='*60}")
        print(f"  Total checks:   {summary.get('total', 0)}")
        print(f"  [PASS] Passed:  {summary.get('passed', summary.get('total_passed', 0))}")
        print(f"  [FAIL] Failed:  {summary.get('failed', summary.get('total_failed', 0))}")
        print(f"  [WARN] Partial: {summary.get('partial', summary.get('total_partial', 0))}")
        score = result.get('overall_score', summary.get('overall_score', 0))
        print(f"  Score:          {score:.1f}%")
        status = result.get('overall_status', 'unknown')
        print(f"  Status:         {status.upper()}")
        print(f"{'='*60}\n")
        
        if "categories" in result:
            for cat in result["categories"]:
                stats = cat.get("stats", {})
                print(f"  [{cat['name']}] {stats.get('passed', 0)}/{stats.get('total', 0)} passed")
                for item in cat.get("items", []):
                    icon = {"pass": "[OK]", "fail": "[FAIL]", "partial": "[WARN]", 
                            "unknown": "[?]", "skipped": "[SKIP]"}.get(item["status"], "[?]")
                    print(f"    {icon} {item['name']}")
                    if item["status"] in ("fail", "partial") and item.get("details"):
                        details = item['details'][:100]
                        print(f"        {details}")
        elif "agents" in result:
            for a in result["agents"]:
                icon = {"pass": "[OK]", "fail": "[FAIL]", "partial": "[WARN]"}.get(a["status"], "[?]")
                print(f"  {icon} {a['agent']} ({a['stage']}): {a['score']:.1f}% - {a['passed']} pass, {a['failed']} fail")
            
            anomalies = result.get("anomalies", [])
            if anomalies:
                print(f"\n  [WARN] ANOMALIES ({len(anomalies)}):")
                for anom in anomalies[:10]:
                    print(f"    - [{anom['severity'].upper()}] {anom['agent']}/{anom['stage']}: {anom['item']}")
                if len(anomalies) > 10:
                    print(f"    ... and {len(anomalies) - 10} more")
        
        # Show where report is saved
        compliance_dir = PRODUCTS_DIR / project / "compliance"
        print(f"\nReport saved to: {compliance_dir}")
    else:
        print(json.dumps(result, indent=2))
    
    # Return exit code based on status
    status = result.get("overall_status", "unknown")
    if status == "fail":
        return 2  # Critical issues
    elif status == "partial":
        return 1  # Warnings
    return 0


def show_cost_kpi(project=None):
    """Show Cost per Successful Task KPI (Phase 2.7)."""
    if CORE_AVAILABLE and 'CostKPITracker' in CoreImports:
        try:
            tracker = CoreImports['CostKPITracker'](str(PRODUCTS_DIR))
            
            if project:
                kpi = tracker.calculate_cps(project=project, period_days=30)
                print(f"COST KPI: {project} (Phase 2.7)")
            else:
                kpi = tracker.calculate_cps(period_days=30)
                print("COST KPI (Phase 2.7)")
            print("=" * 60)
            print()
            print(f"Period: {kpi.period}")
            print(f"Total Tasks: {kpi.total_tasks}")
            print(f"Successful: {kpi.successful_tasks}")
            print(f"Failed: {kpi.failed_tasks}")
            print(f"Success Rate: {kpi.success_rate}%")
            print()
            print(f"Total Cost: ${kpi.total_cost:.4f}")
            print(f"** Cost Per Successful Task: ${kpi.cost_per_successful_task:.4f} **")
            print(f"Cost Per Failed Task: ${kpi.cost_per_failed_task:.4f}")
            print()
            print(f"Avg Tokens/Task: {kpi.avg_tokens_per_task}")
            print()
            
            # Top expensive agents
            top_agents = tracker.get_top_expensive_agents(project=project, limit=5)
            if top_agents:
                print("Top Agents by CPS:")
                print(f"  {'Agent':<20} {'Tasks':<8} {'Success':<8} {'CPS'}")
                for a in top_agents:
                    print(f"  {a['agent']:<20} {a['tasks']:<8} {a['success']:<8} ${a['cps']:.4f}")
            return
        except Exception as e:
            print(f"Error: {e}")
    
    print("Cost KPI not available")


def show_phases(project=None):
    """Show product completion phases (MVP + Post-MVP)."""
    pipeline_file = PRODUCTS_DIR / project / "pipeline.json"

    if not pipeline_file.exists():
        print(f"Project '{project}' not found.")
        return

    try:
        with open(pipeline_file) as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"Error reading pipeline.json for {project}")
        return

    completion = config.get("product_completion")
    if not completion:
        print(f"No product_completion tracking for {project}")
        print("Run: /pipeline update-phases to add tracking")
        return

    print(f"PRODUCT COMPLETION: {project}")
    print("=" * 60)
    print()
    print(f"Total Features: {completion.get('total_features', 0)}")
    print(f"Completed: {completion.get('completed', 0)}")
    print(f"Remaining: {completion.get('remaining', 0)}")
    print(f"** Progress: {completion.get('percent_complete', 0):.1f}% **")
    print()

    # Progress bar
    pct = completion.get('percent_complete', 0)
    bar_len = 40
    filled = int(bar_len * pct / 100)
    bar = "#" * filled + "." * (bar_len - filled)
    print(f"  [{bar}] {pct:.1f}%")
    print()

    # Phases
    phases = completion.get("phases", {})
    if phases:
        print("PHASES:")
        print(f"  {'Phase':<35} {'Status':<12} {'Features'}")
        print(f"  {'-'*35} {'-'*12} {'-'*20}")
        for phase_id, phase in phases.items():
            label = phase.get("label", phase_id)
            status = phase.get("status", "unknown")
            features = phase.get("features", [])
            completed = phase.get("completed_features", [])
            feat_str = f"{len(completed)}/{len(features)}" if features else "0/0"

            status_marker = {
                "in_progress": "[ACTIVE]",
                "completed": "[DONE]",
                "not_started": "[WAITING]",
                "blocked": "[BLOCKED]"
            }.get(status, "[?]")

            print(f"  {label:<35} {status_marker:<12} {feat_str}")

            # Show blocked by
            if phase.get("blocked_by"):
                print(f"    Blocked by: {phase['blocked_by']}")
            if phase.get("trigger"):
                print(f"    Trigger: {phase['trigger']}")
            if phase.get("depends_on_inputs"):
                print(f"    Needs inputs: {', '.join(phase['depends_on_inputs'])}")
        print()

    # Completion definition
    if completion.get("completion_definition"):
        print("PRODUCT COMPLETION DEFINITION:")
        print(f"  {completion['completion_definition']}")
        print()

    # MVP decision log
    decision = completion.get("mvp_decision_log", {})
    if decision:
        print("MVP DECISION LOG:")
        print(f"  Decided by: {decision.get('decided_by', 'unknown')}")
        print(f"  Decided at: {decision.get('decided_at', 'unknown')}")
        print(f"  User approved: {'YES' if decision.get('explicit_user_approval') else 'NO (implicit)'}")
        print(f"  Rationale: {decision.get('rationale', 'unknown')}")
        if decision.get("follow_up_plan"):
            print(f"  Follow-up plan: {decision['follow_up_plan']}")


def adopt_external(args):
    """Adopt a project built OUTSIDE the pipeline (BI-0143)."""
    import json
    from core import adopt_project
    if not args:
        print("usage: adopt <name> <path> [--reference]  |  adopt scan <path>")
        return
    if args[0] == "scan":
        if len(args) < 2:
            print("usage: adopt scan <path>")
            return
        print(json.dumps(adopt_project.scan(args[1]), indent=2, ensure_ascii=False)[:3000])
        return
    if len(args) < 2:
        print("usage: adopt <name> <path> [--reference]")
        return
    res = adopt_project.adopt(args[0], args[1], copy=("--reference" not in args))
    print(json.dumps(res, indent=2, ensure_ascii=False))


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        show_usage()
        return
    
    command = sys.argv[1].lower()
    args = sys.argv[2:] if len(sys.argv) > 2 else []
    
    if command == "list":
        list_projects()
    elif command == "agents":
        list_agents()
    elif command == "runs":
        project = resolve_project_arg(args[0] if args else None)
        if project: list_selective_runs(project)
    elif command == "test":
        project = resolve_project_arg(args[0] if args else None)
        if project: test_infrastructure(project)
    elif command == "health":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_health(project)
    elif command == "checkpoints":
        project = resolve_project_arg(args[0] if args else None)
        if project: list_checkpoints(project)
    elif command == "dlq":
        project = resolve_project_arg(args[0] if args else None)
        if project: list_dlq(project)
    elif command == "usage":
        show_usage()
    elif command == "architecture":
        show_architecture()
    elif command == "project-architecture":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_project_architecture(project)
    elif command == "continue":
        project = resolve_project_arg(args[0] if args else None)
        if project: continue_pipeline(project)
    elif command == "queue":
        show_queue()
    elif command == "queue-add":
        project = resolve_project_arg(args[0] if args else None)
        if project:
            priority = int(args[1]) if len(args) > 1 else 1
            queue_project(project, priority)
    elif command == "budget":
        show_budget()
    elif command == "status":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_project_status(project)
    elif command == "circuit-reset":
        project = resolve_project_arg(args[0] if args else None)
        if project: circuit_reset(project)
    elif command == "lock":
        project = resolve_project_arg(args[0] if args else None)
        if project:
            if acquire_lock(project):
                print(f"Lock acquired for {project}")
            else:
                print(f"Could not acquire lock for {project} (already locked or project not found)")
    elif command == "unlock":
        project = resolve_project_arg(args[0] if args else None)
        if project:
            if release_lock(project):
                print(f"Lock released for {project}")
            else:
                print(f"Could not release lock for {project}")
    elif command == "version":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_version(project)
    elif command == "log":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_log(project, args[1:])
    elif command == "review":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_reviews(project)
    elif command == "ledger":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_ledger(project)
    elif command == "skills":
        show_skills()
    elif command == "report":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_full_report(project)
    elif command == "models":
        show_models()
    elif command == "context":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_context(project)
    elif command == "stop-conditions":
        show_stop_conditions()
    elif command == "escalations":
        show_escalations(args[0] if args else None)
    elif command == "cache":
        show_tool_cache()
    elif command == "knowledge":
        show_knowledge_router()
    elif command == "budget-alloc":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_budget_allocation(project)
    elif command == "cost-kpi":
        show_cost_kpi(args[0] if args else None)
    elif command == "kpi":
        show_cost_kpi(args[0] if args else None)
    elif command == "phases":
        project = resolve_project_arg(args[0] if args else None)
        if project: show_phases(project)
    elif command == "mark-complete":
        project = resolve_project_arg(args[0] if args else None)
        if project:
            stage = int(args[1]) if len(args) > 1 else None
            verdict = args[2] if len(args) > 2 else None
            mark_stage_complete(project, stage, verdict)
    elif command == "exit":
        project = resolve_project_arg(args[0] if args else None)
        if project:
            exit_pipeline(project)
    elif command == "compliance":
        # compliance [project] [agent] [stage]
        project = resolve_project_arg(args[0] if args else None)
        agent = args[1] if len(args) > 1 else None
        stage = args[2] if len(args) > 2 else None
        if project:
            sys.exit(show_compliance(project, agent, stage) or 0)
    elif command == "adopt":
        adopt_external(args)
    else:
        print(f"Unknown command: {command}")
        print("Run without arguments to see usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
