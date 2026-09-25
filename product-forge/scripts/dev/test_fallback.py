from core.pipeline_executor import PipelineExecutor

ex = PipelineExecutor(products_dir='products', project='test-pipeline')

# Simulate an LLM fallback (template) from _call_llm
ex._call_llm = lambda prompt, agent_id, stage_id: ("STUB", {"fallback": True, "selected_model": "", "total_tokens": 0})

artifacts, execu = ex._generate_agent_artifacts('implement', '4a', 'Execute Phase 1')
print('generate artifacts -> status:', execu.status, '| artifacts:', len(artifacts), '| error:', execu.error)

res = ex.execute_agent('implement', '4a', 'Execute Phase 1')
print('execute_agent     -> status:', res.status, '| error:', res.error, '| tokens:', res.total_tokens)
