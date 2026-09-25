import sys
sys.path.insert(0, '.')
from core.product_plan import ProductPlan
import tempfile
from pathlib import Path

temp_dir = tempfile.mkdtemp()
products_dir = Path(temp_dir) / 'products'
products_dir.mkdir()

plan = ProductPlan('test', str(products_dir))
plan.add_module('MOD-1', 'Core', 1)
plan.add_feature('F-001', 'Feature 1', 'MOD-1', 'must-have', 1)

print('Before record_testing:')
for mod_data in plan.plan['modules']:
    for feat_data in mod_data.get('features', []):
        print(f"  id={feat_data['id']}, testing={feat_data.get('testing')}")

result = plan.record_testing('F-001', 'failing', test_count=10, pass_rate=0.5)
print(f'result: {result}')
print(f'result.testing: {result.testing if result else None}')

print('After record_testing (direct access):')
for mod_data in plan.plan['modules']:
    for feat_data in mod_data.get('features', []):
        print(f"  id={feat_data['id']}, testing={feat_data.get('testing')}")

print('get_all_features:')
for f in plan.get_all_features():
    print(f"  id={f.id}, testing={f.testing}")
