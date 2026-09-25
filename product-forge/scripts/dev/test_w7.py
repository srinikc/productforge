import json
from core.delegation import DelegationRouter, DelegationBudget

d = json.load(open('pipeline-definition.json', encoding='utf-8-sig'))
r = DelegationRouter(d, budget=DelegationBudget())

print('resolve code-review@4a code_issue       ->', r.resolve('4a', 'code-review', ['code_issue']))
print('resolve implement@4a architecture_issue ->', r.resolve('4a', 'implement', ['architecture_issue']))
print('resolve security@5 issues_found         ->', r.resolve('5', 'security', ['issues_found']))
print('resolve devops@4a build_needed          ->', r.resolve('4a', 'devops', ['build_needed']))
print('resolve package@9 fix (none expected)   ->', r.resolve('9', 'package', ['fix']))

big = 'X' * 10000
capped = r.cap_payload(big)
print('cap_payload: input=10000 output=%d' % len(capped))

b = DelegationBudget(max_invocations_per_stage=1, max_total_invocations=1)
print('budget can_invoke(4a):', b.can_invoke('4a'))
b.record('4a')
print('budget can_invoke(4a) after 1:', b.can_invoke('4a'))

from core.pipeline_executor import PipelineExecutor
ex = PipelineExecutor(products_dir='products', project='test-pipeline')
ok = ex.load_pipeline('pipeline-definition.json')
print('load_pipeline:', ok, '| delegation_enabled(default):', ex.delegation_enabled,
      '| router:', ex.delegation_router is not None)
