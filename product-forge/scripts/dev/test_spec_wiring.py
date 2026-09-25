import os
from core.pipeline_executor import PipelineExecutor

ex = PipelineExecutor(products_dir='products', project='test-pipeline')
print("specs loaded:", len(getattr(ex, 'agent_specs', {})))
print("implement spec present:", 'implement' in ex.agent_specs)

print("\n== tools for agents ==")
for a in ['implement', 'validate', 'design', 'code-review']:
    schemas = ex.get_tools_for_agent(a)
    print(f"  {a}: {[s['function']['name'] for s in schemas]}")

print("\n== execute_agent_tool (sandboxed) ==")
print("  write:", ex.execute_agent_tool('implement', 'write_file', {'path': 'src/demo.txt', 'content': 'hello'}))
print("  read :", ex.execute_agent_tool('implement', 'read_file', {'path': 'src/demo.txt'}))
print("  list :", ex.execute_agent_tool('implement', 'list_dir', {'path': 'src'})['output'])
print("  escape attempt:", ex.execute_agent_tool('implement', 'write_file', {'path': '../../evil.txt', 'content': 'x'}))
print("  disallowed tool for design:", ex.execute_agent_tool('design', 'run_command', {'command': 'echo hi'}))

print("\n== prompt from spec (implement) ==")
prompt = ex._build_agent_prompt('implement', '4a', 'Implement F-1', {'allowed_inputs': [], 'max_input_tokens': 16000}, os.path.join(ex.project_dir, 'artifacts', '4a', 'implement-output.md'))
print("  prompt starts with spec text:", prompt.strip().startswith('You are the Implement agent'))
print("  contains TASK:", 'TASK: Implement F-1' in prompt)
print("  prompt length:", len(prompt))
