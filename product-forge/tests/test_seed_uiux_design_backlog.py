"""Contract + idempotency tests for the UIUX design-system seed (BI-PF-1436)."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _seed_module():
    spec = importlib.util.spec_from_file_location(
        "seed_uiux_design_backlog", ROOT / "scripts" / "dev" / "seed_uiux_design_backlog.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_should_write_only_for_new_or_empty_deps():
    seed = _seed_module()
    prior = {"uiux-design-system-inclusion:skills-registry"}
    assert seed._should_write("uiux-design-system-inclusion:new", prior, []) is True
    assert seed._should_write("uiux-design-system-inclusion:skills-registry", prior, []) is True
    assert seed._should_write(
        "uiux-design-system-inclusion:skills-registry", prior, [{"task_id": "BI-PF-1"}]) is False


def test_seed_contract_and_rerun(tmp_path, monkeypatch):
    import core.backlog as backlog
    import core.id_allocator as id_allocator

    seed = _seed_module()
    d = tmp_path / "backlog"
    (d / "history").mkdir(parents=True)
    for name in ("open.json", "closed.json"):
        (d / name).write_text("[]", encoding="utf-8")
    (d / "counters.json").write_text("{}", encoding="utf-8")
    paths = (str(d), str(d / "open.json"), str(d / "closed.json"),
             str(d / "history"), str(d / "counters.json"))
    monkeypatch.setattr(backlog, "_paths", lambda scope, project=None: paths)
    monkeypatch.setattr(seed, "S", "product_forge")
    monkeypatch.setattr(seed, "P", None)
    monkeypatch.setattr(id_allocator, "enabled", lambda: False)
    monkeypatch.setenv("PF_GROOMING_AI", "0")

    assert seed.main() == 0
    items = backlog.list_open("product_forge", None)
    assert len(items) == 10

    epic = next(i for i in items if i["external_id"].endswith(":epic"))
    kids = [i for i in items if i.get("epic") == epic["id"]]
    assert epic["type"] == "epic"
    assert len(kids) == 9
    assert all(k["type"] == "feature" and not k.get("execution_order") for k in kids)
    assert all(k["status"] == "new" for k in kids)
    assert all((i.get("api_impact") or {}).get("reason") for i in [epic, *kids])
    assert all(i.get("acceptance_criteria")
               and all(len(a) >= 40 for a in i["acceptance_criteria"]) for i in [epic, *kids])
    assert not any("## Acceptance criteria" in (i.get("body") or "") for i in [epic, *kids])

    order = epic.get("execution_order") or []
    assert len(order) == 9
    assert {r["wave"] for r in order} == {1, 2, 3, 4}

    by_ext = {i["external_id"].split(":")[-1]: i for i in kids}
    dep_ids = {d["task_id"] for d in by_ext["catalog-engine"].get("dependencies", [])}
    assert by_ext["knowledge-ingestion"]["id"] in dep_ids

    sentinel = kids[0]
    backlog.update("product_forge", None, sentinel["id"],
                   affected_files=["sentinel"], verification=["sentinel"])
    assert seed.main() == 0
    again = backlog.get("product_forge", None, sentinel["id"])
    assert again["affected_files"] == ["sentinel"]
    assert again["verification"] == ["sentinel"]
    assert len(backlog.list_open("product_forge", None)) == 10
