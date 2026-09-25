import sys
import os
sys.path.insert(0, '.')
sys.path.insert(0, 'core')

from core.pipeline_executor import PipelineExecutor

executor = PipelineExecutor(products_dir='products', project='test-e2e')
executor.load_pipeline('pipeline-definition.json')

# Test every agent individually - quick single call
test_cases = [
    ("0", "ideation", "Create a brief ideation doc for a hello world API"),
    ("0a", "discovery", "Brief discovery analysis for a hello world API"),
    ("1", "design", "Brief design doc for a hello world API. Be concise."),
    ("1a", "product-design-spec", "Brief spec for a hello world API"),
    ("1b", "design_critic", "Brief design review for a hello world API"),
    ("1c", "ux-ia", "Brief UX review for a hello world API"),
    ("2", "architect", "Brief architecture for a hello world API"),
    ("3", "orchestrator", "Refine requirements for hello world API"),
    ("4-0", "implement", "Skeleton for hello world API"),
    ("4-0", "devops", "Devops setup for hello world API"),
    ("4a", "code-review", "Code review for hello world API"),
    ("4a", "validate", "Validate hello world API"),
    ("5", "security", "Security scan for hello world API"),
    ("8", "document", "Document hello world API"),
    ("9", "package", "Package hello world API"),
    ("11", "devops", "Deploy hello world API"),
]

results = []
for stage_id, agent_id, task in test_cases:
    print(f"Testing {agent_id} (stage {stage_id})...", end=" ", flush=True)
    try:
        execution = executor.execute_agent(agent_id, stage_id, task)
        src = "LLM" if execution.total_tokens > 100 else "TEMPLATE"
        print(f"{src} | {execution.total_tokens} tok | ${execution.cost:.6f} | {execution.selected_model}")
        results.append({
            "stage": stage_id,
            "agent": agent_id,
            "model": execution.selected_model,
            "provider": execution.selected_provider,
            "input_tok": execution.input_tokens,
            "output_tok": execution.output_tokens,
            "cached_tok": execution.cached_tokens,
            "total_tok": execution.total_tokens,
            "cost": execution.cost,
            "source": src,
        })
    except Exception as e:
        print(f"ERROR: {e}")
        results.append({
            "stage": stage_id,
            "agent": agent_id,
            "model": "N/A",
            "provider": "N/A",
            "input_tok": 0,
            "output_tok": 0,
            "cached_tok": 0,
            "total_tok": 0,
            "cost": 0,
            "source": "ERROR",
        })

print("\n" + "=" * 80)
print("SUMMARY TABLE")
print("=" * 80)
print(f"{'Stage':<8} {'Agent':<22} {'Model':<20} {'In':>6} {'Out':>6} {'Cache':>6} {'Total':>7} {'Cost':>10} {'Source':<8}")
print("-" * 80)
total_in = total_out = total_cache = total_all = 0
total_cost = 0
for r in results:
    print(f"{r['stage']:<8} {r['agent']:<22} {r['model']:<20} {r['input_tok']:>6} {r['output_tok']:>6} {r['cached_tok']:>6} {r['total_tok']:>7} ${r['cost']:.6f} {r['source']:<8}")
    total_in += r['input_tok']
    total_out += r['output_tok']
    total_cache += r['cached_tok']
    total_all += r['total_tok']
    total_cost += r['cost']
print("-" * 80)
print(f"{'TOTAL':<8} {'':<22} {'':<20} {total_in:>6} {total_out:>6} {total_cache:>6} {total_all:>7} ${total_cost:.6f}")

llm_count = sum(1 for r in results if r['source'] == 'LLM')
tmpl_count = sum(1 for r in results if r['source'] == 'TEMPLATE')
err_count = sum(1 for r in results if r['source'] == 'ERROR')
print(f"\nLLM: {llm_count} | Template: {tmpl_count} | Error: {err_count} | Total: {len(results)}")
