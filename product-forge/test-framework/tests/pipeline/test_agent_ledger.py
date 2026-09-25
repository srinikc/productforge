"""
Tests for the Agent Ledger
"""
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class TestAgentLedger:
    def test_create_ledger(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        assert ledger.ledger["version"] == "1.0.0"
        assert ledger.ledger["work_items"] == []

    def test_record_work(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        work = ledger.record_work(
            agent="implement",
            project="test-proj",
            stage=1,
            action="Built core module",
            files_written=["core/main.py"],
            files_read=["core/config.yaml"],
            inputs_used={"config": "test"},
            output_produced={"main": "built"},
        )

        assert work.agent == "implement"
        assert work.project == "test-proj"
        assert work.stage == 1
        assert work.status == "completed"
        assert work.files_written == ["core/main.py"]
        assert work.files_read == ["core/config.yaml"]
        assert len(ledger.ledger["work_items"]) == 1

    def test_record_work_with_error(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        work = ledger.record_work(
            agent="implement",
            project="test-proj",
            stage=1,
            action="Build failed",
            files_written=[],
            status="failed",
            error="Syntax error in main.py",
        )

        assert work.status == "failed"
        assert work.error == "Syntax error in main.py"

    def test_update_work(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        work = ledger.record_work(
            agent="implement",
            project="test-proj",
            stage=1,
            action="Build module",
            files_written=[],
            status="in_progress",
        )

        ledger.update_work(
            work.id,
            status="completed",
            output_produced={"main": "built"},
        )

        updated = ledger.ledger["work_items"][0]
        assert updated["status"] == "completed"
        assert updated["output_produced"] == {"main": "built"}
        assert updated["completed_at"] is not None

    def test_get_work_by_agent(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])
        ledger.record_work(agent="design", project="p1", stage=1, action="a2", files_written=[])
        ledger.record_work(agent="implement", project="p2", stage=2, action="a3", files_written=[])

        impl_work = ledger.get_work_by_agent("implement")
        assert len(impl_work) == 2

    def test_get_work_by_project(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])
        ledger.record_work(agent="implement", project="p2", stage=1, action="a2", files_written=[])

        p1_work = ledger.get_work_by_project("p1")
        assert len(p1_work) == 1

    def test_get_work_by_stage(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])
        ledger.record_work(agent="implement", project="p1", stage=2, action="a2", files_written=[])

        stage1 = ledger.get_work_by_stage(1)
        assert len(stage1) == 1

    def test_get_work_by_status(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[], status="completed")
        ledger.record_work(agent="implement", project="p1", stage=1, action="a2", files_written=[], status="failed")

        completed = ledger.get_work_by_status("completed")
        assert len(completed) == 1

    def test_get_agent_summary(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=["core/main.py"], status="completed")
        ledger.record_work(agent="implement", project="p2", stage=2, action="a2", files_written=["core/auth.py"], status="completed")
        ledger.record_work(agent="implement", project="p1", stage=1, action="a3", files_written=[], status="failed")

        summary = ledger.get_agent_summary("implement")
        assert summary["total"] == 3
        assert summary["completed"] == 2
        assert summary["failed"] == 1
        assert summary["files_written"] == 2
        assert "p1" in summary["projects"]
        assert "p2" in summary["projects"]

    def test_get_project_summary(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[], status="completed")
        ledger.record_work(agent="design", project="p1", stage=1, action="a2", files_written=[], status="completed")

        summary = ledger.get_project_summary("p1")
        assert summary["total"] == 2
        assert "implement" in summary["agents"]
        assert "design" in summary["agents"]

    def test_get_all_agents(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])
        ledger.record_work(agent="design", project="p1", stage=1, action="a2", files_written=[])

        agents = ledger.get_all_agents()
        assert set(agents) == {"implement", "design"}

    def test_get_all_projects(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])
        ledger.record_work(agent="implement", project="p2", stage=1, action="a2", files_written=[])

        projects = ledger.get_all_projects()
        assert set(projects) == {"p1", "p2"}

    def test_get_recent_work(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        for i in range(15):
            ledger.record_work(agent="implement", project="p1", stage=1, action=f"a{i}", files_written=[])

        recent = ledger.get_recent_work(limit=5)
        assert len(recent) == 5
        assert recent[-1]["action"] == "a14"

    def test_get_failed_work(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[], status="completed")
        ledger.record_work(agent="implement", project="p1", stage=1, action="a2", files_written=[], status="failed")

        failed = ledger.get_failed_work()
        assert len(failed) == 1

    def test_generate_markdown(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(
            agent="implement",
            project="test-proj",
            stage=1,
            action="Built core module",
            files_written=["core/main.py"],
            status="completed",
        )

        md = ledger.generate_markdown()
        assert "Agent Ledger" in md
        assert "implement" in md
        assert "core/main.py" in md
        assert "Auto-generated" in md

    def test_persistence(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=[])

        # Load from disk
        ledger2 = AgentLedger(str(temp_products_dir))
        assert len(ledger2.ledger["work_items"]) == 1
        assert ledger2.ledger["work_items"][0]["agent"] == "implement"

    def test_summary_updated(self, temp_products_dir):
        from core.agent_ledger import AgentLedger

        ledger = AgentLedger(str(temp_products_dir))
        ledger.record_work(agent="implement", project="p1", stage=1, action="a1", files_written=["core/main.py"])
        ledger.record_work(agent="design", project="p2", stage=1, action="a2", files_written=["docs/readme.md"])

        summary = ledger.ledger["summary"]
        assert summary["total_work_items"] == 2
        assert summary["total_agents"] == 2
        assert summary["total_projects"] == 2
        assert summary["total_files_written"] == 2


class TestAgentWork:
    def test_work_creation(self):
        from core.agent_ledger import AgentWork

        work = AgentWork(
            id="w1",
            agent="implement",
            project="p1",
            stage=1,
            action="Build",
            files_written=["core/main.py"],
            files_read=["core/config.yaml"],
            inputs_used={},
            output_produced={},
            status="completed",
            started_at="2026-08-28T00:00:00Z",
        )

        assert work.id == "w1"
        assert work.agent == "implement"
        assert work.status == "completed"

    def test_work_serialization(self):
        from core.agent_ledger import AgentWork

        work = AgentWork(
            id="w1",
            agent="implement",
            project="p1",
            stage=1,
            action="Build",
            files_written=["core/main.py"],
            files_read=[],
            inputs_used={},
            output_produced={},
            status="completed",
            started_at="2026-08-28T00:00:00Z",
        )

        data = work.to_dict()
        work2 = AgentWork.from_dict(data)

        assert work2.id == work.id
        assert work2.agent == work.agent
        assert work2.files_written == work.files_written
