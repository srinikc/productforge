import os, json
from core.tech_stack import (detect_tech_from_text, stack_to_layers,
                             parse_tech_stack_block, build_decision)
from core.pipeline_executor import PipelineExecutor
from core.orchestrator.types import AgentExecution

print("detect:", detect_tech_from_text("A command-line TODO app in Python using SQLite and click"))
print("layers(python+postgres):", stack_to_layers({"languages": ["python"], "database": "postgresql"}))
print("layers(fastapi+react):", stack_to_layers({"languages": ["python"], "frameworks": ["fastapi", "react"]}))

block = ('## Tech Stack\n```json\n'
         '{"kind":"cli","languages":["python"],"frameworks":[],"database":null,'
         '"requested":["python"],"changed_from_request":false,"rationale":"CLI fits"}\n```\n')
print("parse:", parse_tech_stack_block(block))
print("decision agree:", build_decision(["python"], {"kind": "cli", "languages": ["python"], "frameworks": []}))
print("decision change:", build_decision(["python"], {"kind": "web-app", "languages": ["python"], "frameworks": ["fastapi"]}))

# --- executor integration ---
ex = PipelineExecutor(products_dir="products", project="test-pipeline")
ex.requested_tech_stack = ["python"]
os.makedirs("products/test-pipeline/artifacts/2", exist_ok=True)
p = "products/test-pipeline/artifacts/2/architect-output.md"
open(p, "w", encoding="utf-8").write("# Architecture\n" + block)
execu = AgentExecution(agent_id="architect", stage_id="2", status="completed", artifacts=[p])
dec = ex._finalize_tech_stack([execu])
print("\npersisted decision:", json.dumps(dec["chosen"]), "changed:", dec["changed_from_request"])
print("tech-stack.json exists:", os.path.exists("products/test-pipeline/docs/tech-stack.json"))
k = ex._load_knowledge_for_agent("implement", "4a", {})
print("implement knowledge len:", len(k), "| has FastAPI:", "FastAPI" in k or "fastapi" in k)

os.makedirs("products/test-pipeline/src", exist_ok=True)
open("products/test-pipeline/src/bad.py", "w", encoding="utf-8").write("import fastapi\n")
print("stack violations (expect bad.py/fastapi):", ex._stack_compliance())
