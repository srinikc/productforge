import json

with open('pipeline-definition.json', 'r', encoding='utf-8') as f:
    pipeline = json.load(f)

print('Stage | Name | Agents')
print('-' * 60)
for stage_id, stage in pipeline['stages'].items():
    agents = stage.get('ideal_flow', [])
    sub_agents = list(stage.get('sub_agents', {}).keys())
    all_agents = agents + [a for a in sub_agents if a not in agents]
    name = stage.get('name', stage_id)
    agent_str = ', '.join(all_agents) if all_agents else '(none)'
    print(f'  {stage_id:6} | {name:30} | {agent_str}')

total = len(pipeline['stages'])
print(f'\nTotal stages: {total}')
