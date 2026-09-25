import os, re, glob, json

rows = []
for f in sorted(glob.glob('.opencode/agent/*.md')):
    name = os.path.basename(f)[:-3]
    txt = open(f, encoding='utf-8', errors='ignore').read()
    m = re.match(r'^---\n(.*?)\n---', txt, re.S)
    fm = {}
    if m:
        for line in m.group(1).splitlines():
            if ':' in line and not line.strip().startswith('-'):
                k, v = line.split(':', 1)
                fm[k.strip()] = v.strip()
    body = txt[m.end():] if m else txt
    heads = re.findall(r'^##\s+(.+)$', body, re.M)
    rows.append({
        'name': name,
        'frontmatter': bool(m),
        'keys': sorted(fm.keys()),
        'mode': fm.get('mode', ''),
        'model': fm.get('model', ''),
        'oc_model': ('opencode/' in fm.get('model', '') or 'opencode-go/' in fm.get('model', '')),
        'permission': 'permission' in fm,
        'task_tool': bool(re.search(r'Task tool|\bTask\(|sub-agent|subagent', body, re.I)),
        'arguments': '$ARGUMENTS' in body,
        'sections': len(heads),
        'chars': len(body),
    })

no_fm = [r['name'] for r in rows if not r['frontmatter']]
no_mode = [r['name'] for r in rows if not r['mode']]
oc_model = [r['name'] for r in rows if r['oc_model']]
no_perm = [r['name'] for r in rows if not r['permission']]
task_ref = [r['name'] for r in rows if r['task_tool']]
args_ref = [r['name'] for r in rows if r['arguments']]
few_sections = [r['name'] for r in rows if r['sections'] < 3]

print("AGENT CARDS:", len(rows))
print("\nNO frontmatter (%d):" % len(no_fm), ", ".join(no_fm))
print("NO mode (%d):" % len(no_mode), ", ".join(no_mode[:20]))
print("opencode-specific model ids (%d):" % len(oc_model), ", ".join(oc_model[:15]), "...")
print("NO permission block (%d):" % len(no_perm), ", ".join(no_perm))
print("\nReferences 'Task tool/sub-agent' (%d):" % len(task_ref), ", ".join(task_ref[:20]), "...")
print("Uses $ARGUMENTS (%d):" % len(args_ref), ", ".join(args_ref))
print("Thin (<3 sections) (%d):" % len(few_sections), ", ".join(few_sections[:20]))

# section-name consistency
from collections import Counter
all_heads = Counter()
for f in glob.glob('.opencode/agent/*.md'):
    txt = open(f, encoding='utf-8', errors='ignore').read()
    for h in re.findall(r'^##\s+(.+)$', txt, re.M):
        all_heads[h.strip().lower()] += 1
print("\nTop common section headings:", [h for h, _ in all_heads.most_common(12)])
