import json
from core.knowledge_compliance_checker import GuidelineContentLoader
from core.pipeline_executor import PipelineExecutor
from core.dag_executor import DAGExecutor

gl = GuidelineContentLoader('docs/guidelines')
out = gl.load_guidelines_for_layers(['api', 'database'], max_tokens=3000)
print('GUIDELINE LOADER: len =', len(out))

ex = PipelineExecutor(products_dir='products', project='test-pipeline')
for agent, stage in [('ideation', '0'), ('design', '1'), ('discovery', '0a'),
                     ('architect', '2'), ('implement', '4a'), ('security', '5')]:
    cfg = ex._get_agent_model_config(agent, stage)
    print('  %s@%s: model=%s provider=%s' % (agent, stage, cfg.get('model'), cfg.get('provider')))

with open('pipeline-definition.json', encoding='utf-8-sig') as f:
    d = json.load(f)

dag = DAGExecutor(d)
print('DAG ready (iteration 1):', dag.get_ready_stages())
print('4b depends_on:', dag.stages['4b'].depends_on)
print('12 depends_on:', dag.stages['12'].depends_on)
