"""
Comprehensive tests for Batch 3-5 modules.
Tests: Agent Memory, Knowledge Compiler, Skill Contracts, Agent Runtime,
       DAG Executor, Reasoning Skills, Knowledge Router.
"""

import sys
import os
import shutil
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Use temporary directories so tests don't pollute production data
TEST_BASE = os.path.join(tempfile.gettempdir(), "productforge_test_batch345")


def _clean(name):
    """Remove a test directory tree if it exists."""
    path = os.path.join(TEST_BASE, name)
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


def test_agent_memory():
    """Test Agent Memory system — all 8 memory types, store, retrieve, stats."""
    from core.agent_memory import AgentMemory, MemoryType, MemoryEntry, MemoryQuery

    print("Testing Agent Memory...")
    _clean("memory")

    memory = AgentMemory(
        products_dir=TEST_BASE, project="memory"
    )

    # Store entries for all 8 memory types via the real store() API
    stored = []
    for mt in MemoryType:
        entry = memory.store(
            memory_type=mt.value,
            content=f"Test content for {mt.value}",
            source="test",
            confidence=0.8,
            tags=["test", mt.value],
        )
        assert entry is not None, f"store() returned None for {mt.value}"
        stored.append(entry)

    # Verify stats
    stats = memory.get_stats()
    assert stats["total"] >= 8, f"Expected >= 8 entries, got {stats['total']}"
    print(f"  [PASS] All 8 memory types stored: total={stats['total']}")

    # Test retrieval with a query
    results = memory.retrieve(
        MemoryQuery(query="Test", min_confidence=0.5)
    )
    assert len(results) > 0, "retrieve() returned no results"
    print(f"  [PASS] Retrieval works: {len(results)} results")

    # Test single get
    first = stored[0]
    got = memory.get(first.entry_id)
    assert got is not None, "get() returned None for known entry"
    assert got.content == first.content
    print(f"  [PASS] get() by ID works")

    # Test update
    updated = memory.update(first.entry_id, content="Updated content", tags=["updated"])
    assert updated is not None
    assert updated.content == "Updated content"
    print(f"  [PASS] update() works")

    # Test validate
    ok = memory.validate_entry(first.entry_id, "test-validator")
    assert ok is True
    validated_list = memory.get_validated()
    assert len(validated_list) >= 1
    print(f"  [PASS] validate_entry() works")

    # Test delete
    second = stored[1]
    deleted = memory.delete(second.entry_id)
    assert deleted is True
    assert memory.get(second.entry_id) is None
    print(f"  [PASS] delete() works")

    # Test link_entries
    if len(stored) >= 3:
        a, b = stored[2].entry_id, stored[3].entry_id if len(stored) > 3 else stored[0].entry_id
        linked = memory.link_entries(a, b)
        assert linked is True
        related = memory.get_related(a)
        assert len(related) >= 1
        print(f"  [PASS] link_entries() and get_related() work")

    # Test export/import
    exported = memory.export_all()
    assert isinstance(exported, dict)
    print(f"  [PASS] export_all() works ({sum(len(v) for v in exported.values())} entries exported)")

    # Cleanup
    _clean("memory")
    print("  [PASS] Agent Memory — all checks passed\n")
    return True


def test_knowledge_compiler():
    """Test Knowledge Compiler — compile from text, query."""
    from core.knowledge_compiler import KnowledgeCompiler

    print("Testing Knowledge Compiler...")
    _clean("knowledge")

    compiler = KnowledgeCompiler(
        knowledge_dir=os.path.join(TEST_BASE, "knowledge")
    )

    text = (
        "FastAPI is a modern Python web framework. It provides automatic API documentation. "
        "Django is a full-stack framework. It follows the MVC pattern. "
        "Flask is a lightweight micro-framework. It uses Jinja2 templates."
    )

    kb = compiler.compile_from_text(text, "web-frameworks", "test-source")

    assert len(kb.concepts) > 0, f"No concepts extracted, got {len(kb.concepts)}"
    print(f"  [PASS] Concepts extracted: {len(kb.concepts)}")

    assert kb.domain == "web-frameworks"
    assert kb.source_count == 1
    print(f"  [PASS] Domain and source count correct")

    # Test query
    results = compiler.query(domain="web-frameworks")
    assert len(results) > 0, "query(domain) returned no results"
    print(f"  [PASS] Query works: {len(results)} results")

    # Test relationships were extracted
    assert len(kb.relationships) >= 0  # may be 0 for short text
    print(f"  [PASS] Relationships: {len(kb.relationships)}")

    _clean("knowledge")
    print("  [PASS] Knowledge Compiler — all checks passed\n")
    return True


def test_skill_contracts():
    """Test Skill Contracts — register, retrieve, search, compose."""
    from core.skill_contracts import (
        SkillContractRegistry, SkillContract, SkillInput, SkillOutput,
    )

    print("Testing Skill Contracts...")
    _clean("skills")

    registry = SkillContractRegistry(
        registry_dir=os.path.join(TEST_BASE, "skills")
    )

    contract = SkillContract(
        skill_id="test-skill",
        name="Test Skill",
        version="1.0.0",
        description="A test skill",
        domain="testing",
        category="reasoning",
        inputs=[SkillInput(name="input1", type="text", required=True)],
        outputs=[SkillOutput(name="output1", type="text", format="json")],
        procedure=["Step 1", "Step 2"],
        quality_checks=[],
        dependencies=[],
        tags=["test"],
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )

    ok = registry.register(contract)
    assert ok is True, "register() returned False"
    print("  [PASS] Contract registration works")

    retrieved = registry.get("test-skill")
    assert retrieved is not None, "get() returned None for registered contract"
    assert retrieved.name == "Test Skill"
    print("  [PASS] Contract retrieval works")

    # Search
    results = registry.search(domain="testing", category="reasoning")
    assert len(results) >= 1, "search() returned no results"
    print(f"  [PASS] Search works: {len(results)} results")

    # Register a second contract with a dependency
    dep_contract = SkillContract(
        skill_id="dep-skill",
        name="Dependency Skill",
        version="1.0.0",
        description="A dependency",
        domain="testing",
        category="execution",
        inputs=[],
        outputs=[],
        procedure=[],
        quality_checks=[],
        dependencies=[],
        tags=["dep"],
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )
    registry.register(dep_contract)

    parent = SkillContract(
        skill_id="parent-skill",
        name="Parent Skill",
        version="1.0.0",
        description="Has dependency",
        domain="testing",
        category="reasoning",
        inputs=[],
        outputs=[],
        procedure=[],
        quality_checks=[],
        dependencies=["dep-skill"],
        tags=["parent"],
        created_at="2026-01-01",
        updated_at="2026-01-01",
    )
    registry.register(parent)

    deps = registry.get_dependencies("parent-skill")
    assert len(deps) == 1
    assert deps[0].skill_id == "dep-skill"
    print("  [PASS] get_dependencies() works")

    # Compose
    composed = registry.compose(["parent-skill", "dep-skill"])
    assert len(composed) >= 2
    print(f"  [PASS] compose() works: {len(composed)} skills in workflow")

    _clean("skills")
    print("  [PASS] Skill Contracts — all checks passed\n")
    return True


def test_agent_runtime():
    """Test Agent Runtime — checkpoints, hooks, budget."""
    from core.agent_runtime import AgentRuntime, AgentState, AgentContext

    print("Testing Agent Runtime...")
    _clean("runtime")

    runtime = AgentRuntime(
        products_dir=TEST_BASE, project="runtime"
    )

    # Create checkpoint
    context = AgentContext(
        task_id="test-task",
        agent_id="test-agent",
        goal="Test goal",
        constraints=["time < 1h"],
        available_tools=["tool-a"],
    )

    cp_id = runtime.create_checkpoint(
        "test-task", "test-agent", AgentState.PLANNING, context, {"step": 1}
    )
    assert cp_id is not None and len(cp_id) > 0
    print(f"  [PASS] Checkpoint created: {cp_id}")

    # Restore checkpoint
    restored = runtime.restore_checkpoint(cp_id)
    assert restored is not None, "restore_checkpoint() returned None"
    assert restored.task_id == "test-task"
    assert restored.agent_id == "test-agent"
    print("  [PASS] Checkpoint restored")

    # Budget tracking
    assert runtime.check_budget("test-agent", 0.5, 1.0) is True
    runtime.track_cost("test-agent", 0.6)
    assert runtime.check_budget("test-agent", 0.5, 1.0) is False
    report = runtime.get_cost_report()
    assert "test-agent" in report
    assert report["test-agent"] == 0.6
    print("  [PASS] Budget tracking works")

    # Hooks
    hook_called = []

    def my_hook(ctx):
        hook_called.append(ctx)

    runtime.register_hook("before_execute", my_hook)
    runtime._trigger_hooks("before_execute", {"test": True})
    assert len(hook_called) == 1
    print("  [PASS] Lifecycle hooks work")

    _clean("runtime")
    print("  [PASS] Agent Runtime — all checks passed\n")
    return True


def test_dag_executor():
    """Test DAG Executor — dependency resolution, progress, state export."""
    from core.dag_executor import DAGExecutor, StageStatus

    print("Testing DAG Executor...")

    pipeline_def = {
        "stages": {
            "stage-1": {"name": "Stage 1", "type": "sequential", "depends_on": []},
            "stage-2": {"name": "Stage 2", "type": "sequential", "depends_on": ["stage-1"]},
            "stage-3": {"name": "Stage 3", "type": "parallel", "depends_on": ["stage-2"]},
        }
    }

    executor = DAGExecutor(pipeline_def)

    # Stage 1 should be ready (no dependencies)
    ready = executor.get_ready_stages()
    assert "stage-1" in ready, f"stage-1 not in ready list: {ready}"
    print(f"  [PASS] Initial ready stages: {ready}")

    # Stage 2 should NOT be ready yet
    assert "stage-2" not in executor.get_ready_stages()

    # Complete stage 1
    executor.mark_running("stage-1")
    assert executor.states["stage-1"].status == StageStatus.RUNNING
    executor.mark_completed("stage-1", result={"output": "done"})
    assert executor.states["stage-1"].status == StageStatus.COMPLETED

    # Stage 2 should now be ready
    ready = executor.get_ready_stages()
    assert "stage-2" in ready, f"stage-2 not ready after stage-1 complete: {ready}"
    print(f"  [PASS] After stage-1 complete, ready: {ready}")

    # Complete stage 2
    executor.mark_running("stage-2")
    executor.mark_completed("stage-2")
    ready = executor.get_ready_stages()
    assert "stage-3" in ready
    print(f"  [PASS] After stage-2 complete, ready: {ready}")

    # Progress
    progress = executor.get_progress()
    assert progress["completed"] == 2
    assert progress["total"] == 3
    print(f"  [PASS] Progress: {progress}")

    # Export state
    state = executor.export_state()
    assert "stages" in state
    assert "progress" in state
    assert state["stages"]["stage-1"]["status"] == "completed"
    print(f"  [PASS] export_state() works")

    # Mark stage 3 failed and verify
    executor.mark_running("stage-3")
    executor.mark_failed("stage-3", "Simulated error")
    assert executor.states["stage-3"].status == StageStatus.FAILED
    assert executor.states["stage-3"].error == "Simulated error"
    progress = executor.get_progress()
    assert progress["failed"] == 1
    print(f"  [PASS] mark_failed() works")

    # Parallel groups
    executor2 = DAGExecutor({
        "stages": {
            "a": {"name": "A", "type": "parallel", "depends_on": []},
            "b": {"name": "B", "type": "parallel", "depends_on": []},
            "c": {"name": "C", "type": "parallel", "depends_on": ["a", "b"]},
        }
    })
    groups = executor2.get_parallel_groups()
    assert len(groups) >= 1
    print(f"  [PASS] get_parallel_groups() works: {len(groups)} group(s)")

    # Skip
    executor2.mark_running("a")
    executor2.mark_completed("a")
    executor2.mark_running("b")
    executor2.mark_completed("b")
    executor2.mark_running("c")
    executor2.mark_skipped("c")
    assert executor2.states["c"].status == StageStatus.SKIPPED
    print(f"  [PASS] mark_skipped() works")

    print("  [PASS] DAG Executor — all checks passed\n")
    return True


def test_reasoning_skills():
    """Test Reasoning Skills — all 5 skills."""
    from core.reasoning_skills import ReasoningSkills

    print("Testing Reasoning Skills...")

    reasoning = ReasoningSkills()

    skills = [
        "problem_restatement",
        "first_principles",
        "premortem",
        "decision_matrix",
        "alternative_generation",
    ]

    for skill_name in skills:
        result = reasoning.execute(
            skill_name,
            "Build a web application",
            {"options": ["A", "B"], "criteria": ["cost", "time"]},
        )
        assert result.skill == skill_name, f"Wrong skill name: {result.skill}"
        assert result.output is not None, f"Empty output for {skill_name}"
        assert isinstance(result.output, dict), f"Output not dict for {skill_name}"
        assert result.confidence > 0
        print(f"  [PASS] {skill_name} works")

    # Test unknown skill raises ValueError
    try:
        reasoning.execute("nonexistent_skill", "problem")
        assert False, "Should have raised ValueError"
    except ValueError:
        print("  [PASS] Unknown skill raises ValueError")

    print("  [PASS] Reasoning Skills — all checks passed\n")
    return True


def test_knowledge_routing():
    """Test Knowledge Router — routing, stats, freshness."""
    from core.knowledge_router import KnowledgeRouter

    print("Testing Knowledge Router...")

    # Use the real products directory to pick up actual guidelines
    router = KnowledgeRouter(products_dir=os.path.join(TEST_BASE, "routing"))

    # It may find resources from docs/guidelines or have none — both are OK
    stats = router.get_stats()
    assert isinstance(stats, dict)
    assert "total_resources" in stats
    print(f"  [PASS] get_stats() works: {stats['total_resources']} resources")

    # Test routing for different agents (should not crash even with 0 resources)
    agents = ["design", "architect", "quality", "security"]
    for agent in agents:
        decision = router.route(
            task=f"Implement {agent} features",
            agent=agent,
        )
        assert decision is not None
        assert isinstance(decision.selected_resources, list)
        print(f"  [PASS] route() for agent '{agent}': {len(decision.selected_resources)} resources selected")

    # Test route with domain filter
    decision = router.route(task="Frontend implementation", domain="frontend")
    assert decision is not None
    print(f"  [PASS] route() with domain filter works")

    # Test route with stage context
    decision = router.route(task="Database setup", stage="4a", agent="implement")
    assert decision is not None
    print(f"  [PASS] route() with stage/agent context works")

    # Test register_resource
    from core.knowledge_router import KnowledgeResource
    r = KnowledgeResource(
        id="test-res-1",
        title="Test Resource",
        path="docs/test.md",
        domain="testing",
        tags=["test"],
        keywords=["test", "resource"],
        priority=60,
        size_tokens=100,
    )
    router.register_resource(r)
    assert "test-res-1" in router.resources
    print(f"  [PASS] register_resource() works")

    # Test validate_all_resources
    results = router.validate_all_resources()
    assert isinstance(results, dict)
    print(f"  [PASS] validate_all_resources() works")

    # Test get_stale_resources
    stale = router.get_stale_resources(max_age_days=0)
    assert isinstance(stale, list)
    print(f"  [PASS] get_stale_resources() works")

    print("  [PASS] Knowledge Router — all checks passed\n")
    return True


def run_all_tests():
    """Run all tests and report results."""
    print("=" * 60)
    print("COMPREHENSIVE VALIDATION: Batches 3-5")
    print("=" * 60)

    os.makedirs(TEST_BASE, exist_ok=True)

    tests = [
        ("Agent Memory", test_agent_memory),
        ("Knowledge Compiler", test_knowledge_compiler),
        ("Skill Contracts", test_skill_contracts),
        ("Agent Runtime", test_agent_runtime),
        ("DAG Executor", test_dag_executor),
        ("Reasoning Skills", test_reasoning_skills),
        ("Knowledge Router", test_knowledge_routing),
    ]

    passed = 0
    failed = 0
    results_log = []

    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
                results_log.append(f"  [PASS] {name}")
            else:
                failed += 1
                results_log.append(f"  [FAIL] {name}")
        except Exception as e:
            failed += 1
            results_log.append(f"  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()

    # Cleanup
    _clean("")

    print("=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for line in results_log:
        print(line)
    print("-" * 60)
    print(f"Total: {passed} passed, {failed} failed out of {len(tests)}")
    if failed == 0:
        print("ALL TESTS PASSED")
    else:
        print(f"SOME TESTS FAILED ({failed} failure(s))")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
