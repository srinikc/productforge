import json
import collections

PATH = 'pipeline-definition.json'
with open(PATH, 'r', encoding='utf-8-sig') as f:
    data = json.load(f, object_pairs_hook=collections.OrderedDict)

stages = data['stages']
letters = ['a', 'b', 'c', 'd', 'e', 'f']
for i, L in enumerate(letters, start=1):
    impl = f'4{L}'
    vqa = f'4{L}-vqa'
    if impl in stages:
        stages[impl]['name'] = f'Implementation Iteration {i}'
    if vqa in stages:
        stages[vqa]['name'] = f'Visual QA (Iteration {i})'

# Realistic per-stage USD budgets (observed costs are cents, not dollars).
budgets = {
    '0': 0.05, '0a': 0.05, '1': 0.15, '1a': 0.05, '1b': 0.03, '1c': 0.05,
    '2': 0.10, '3': 0.05, '4-0': 0.10,
    '4a': 0.20, '4b': 0.20, '4c': 0.20, '4d': 0.20, '4e': 0.20, '4f': 0.20,
    '4a-vqa': 0.03, '4b-vqa': 0.03, '4c-vqa': 0.03, '4d-vqa': 0.03, '4e-vqa': 0.03, '4f-vqa': 0.03,
    '5': 0.05, '6': 0.05, '7': 0.05, '8': 0.05, '9': 0.03, '10': 0.05, '11': 0.05, '12': 0.01,
}
for sid, val in budgets.items():
    if sid in stages:
        stages[sid]['budget_limit'] = val

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('updated', len(stages), 'stages')
print('4a name:', stages['4a']['name'], '| budget:', stages['4a']['budget_limit'])
print('4f name:', stages['4f']['name'], '| 5 budget:', stages['5']['budget_limit'])
