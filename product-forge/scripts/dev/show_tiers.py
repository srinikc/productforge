import json

with open('config/model-tier.json', encoding='utf-8-sig') as f:
    tier = json.load(f)

with open('pipeline-definition.json', encoding='utf-8-sig') as f:
    pipe = json.load(f)

print('default_tier:', tier.get('default_tier'))
print('\n=== AGENT -> MODEL (from model-tier.json "agents") ===')
for agent, cfg in tier.get('agents', {}).items():
    print('  %-22s %s (%s)' % (agent, cfg.get('model'), cfg.get('provider')))

print('\n=== STAGE -> MODEL (from model-tier.json "stages") ===')
for stage, cfg in tier.get('stages', {}).items():
    print('  %-8s %s' % (stage, cfg.get('model')))

print('\n=== EFFECTIVE PER-STAGE MODEL (stage wins, else agent) ===')
for stage, sdef in pipe.get('stages', {}).items():
    agents = sdef.get('ideal_flow', [])
    stage_model = tier.get('stages', {}).get(stage, {}).get('model')
    for a in agents:
        agent_model = tier.get('agents', {}).get(a, {}).get('model')
        eff = stage_model or agent_model or tier.get('default_tier')
        src = 'stage' if stage_model else ('agent' if agent_model else 'default')
        print('  stage %-8s agent %-22s -> %-18s (%s)' % (stage, a, eff, src))
