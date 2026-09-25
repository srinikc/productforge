import os, re, json, glob

def parse_card(path):
    txt = open(path, encoding='utf-8', errors='ignore').read()
    fm = {}
    m = re.match(r'^---\n(.*?)\n---', txt, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ':' in line and not line.strip().startswith('-'):
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip()
    heads = re.findall(r'^##\s+(.+)$', txt, re.M)
    return fm, heads

oc = {}
for f in glob.glob('.opencode/agent/*.md'):
    name = os.path.basename(f)[:-3]
    fm, heads = parse_card(f)
    oc[name] = {'model': fm.get('model', ''), 'mode': fm.get('mode', ''),
                'desc': fm.get('description', '')[:70], 'sections': len(heads),
                'perm': 'permission' in fm}

from core.context_manager import AGENT_CONTRACTS
py_contracts = sorted(AGENT_CONTRACTS.keys())

src = open('core/pipeline_executor.py', encoding='utf-8').read()
i = src.find('instruction_templates = {')
block = src[i:i+4000]
py_templates = sorted(set(re.findall(r'"([a-z0-9_\-]+)":\s*"""', block)))

pdef = json.load(open('pipeline-definition.json', encoding='utf-8-sig'))
pipeline_agents = set()
for s in pdef.get('stages', {}).values():
    for a in s.get('ideal_flow', []) or []:
        pipeline_agents.add(a)
pipeline_agents = sorted(pipeline_agents)

print('OPENCODE agent cards:', len(oc))
print('PY AGENT_CONTRACTS (%d): %s' % (len(py_contracts), ', '.join(py_contracts)))
print('PY prompt templates (%d): %s' % (len(py_templates), ', '.join(py_templates)))
print('PIPELINE agents (%d): %s' % (len(pipeline_agents), ', '.join(pipeline_agents)))
print()
oc_names = set(oc.keys())
print('In PIPELINE but NO opencode card:', sorted(set(pipeline_agents) - oc_names))
extra = sorted(oc_names - set(pipeline_agents))
print('opencode cards NOT in pipeline (%d): %s' % (len(extra), ', '.join(extra)))
print()
print('Example card fields (implement):', oc.get('implement'))
print('Opencode frontmatter keys used:', sorted({k for v in oc.values() for k in v}))
