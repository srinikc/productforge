import json
import copy
import collections

PATH = 'pipeline-definition.json'

with open(PATH, 'r', encoding='utf-8-sig') as f:
    data = json.load(f, object_pairs_hook=collections.OrderedDict)

stages = data['stages']

# Base implementation phase to clone (4c is a complete phase def).
base_impl = stages['4c']
base_vqa = stages['4c-vqa']

new_order = collections.OrderedDict()
for sid, sdef in stages.items():
    new_order[sid] = sdef
    if sid == '4c-vqa':
        # add 4d/4e/4f + vqa right after 4c-vqa
        for i, letter in enumerate(['d', 'e', 'f'], start=4):
            impl_id = f'4{letter}'
            vqa_id = f'4{letter}-vqa'
            impl = copy.deepcopy(base_impl)
            impl['name'] = f'Phase {i} Implementation'
            impl['depends_on'] = [f'4{chr(ord(letter)-1)}-vqa']
            impl['runs_after'] = impl['depends_on'][0]
            new_order[impl_id] = impl

            vqa = copy.deepcopy(base_vqa)
            vqa['name'] = f'Visual QA (Phase {i})'
            vqa['depends_on'] = [impl_id]
            vqa['runs_after'] = impl_id
            new_order[vqa_id] = vqa

# Re-point stage 5 to run after the last phase vqa (4f-vqa)
if '5' in new_order:
    new_order['5']['depends_on'] = ['4f-vqa']
    new_order['5'].pop('runs_after', None)

data['stages'] = new_order

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')

print('stages now:', list(new_order.keys()))
