from core.pipeline_executor import PipelineExecutor

ex = PipelineExecutor(products_dir='products', project='test-pipeline')

print("=== test 1: small output cap forces truncation + continuation ===")
content, info = ex._call_llm_single(
    "Write the integers from 1 to 60 separated by spaces. Nothing else.",
    'deepseek-v4-flash', 'opencode-go',
    'https://opencode.ai/zen/go/v1/chat/completions',
    'smoke-session', 'smoketest', '0', 30)
print('finish_reason:', info.get('finish_reason'))
print('truncated:', info.get('truncated'))
print('continuations:', info.get('continuations'))
print('out_tokens:', info.get('output_tokens'), 'cost:', info.get('cost'))
print('content_len:', len(content or ''))
nums = [n for n in (content or '').replace('\n', ' ').split() if n.strip().isdigit()]
print('numbers found:', len(nums), 'last:', nums[-1] if nums else None)

print("\n=== test 2: normal call, no truncation ===")
content2, info2 = ex._call_llm_single(
    "Reply with exactly: DONE",
    'deepseek-v4-flash', 'opencode-go',
    'https://opencode.ai/zen/go/v1/chat/completions',
    'smoke-session2', 'smoketest', '0', 2000)
print('finish_reason:', info2.get('finish_reason'), '| truncated:', info2.get('truncated'))
print('content:', (content2 or '').strip()[:40])

print("\n=== test 3: contract-driven cap for implement ===")
from core.context_manager import get_contract
print('implement contract out cap:', get_contract('implement')['max_output_tokens'])
print('validate contract out cap:', get_contract('validate')['max_output_tokens'])
print('design contract out cap:', get_contract('design')['max_output_tokens'])
