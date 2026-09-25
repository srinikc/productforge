import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.pipeline_executor import execute_pipeline

if __name__ == "__main__":
    print("PIPELINE RUNNER STARTED", flush=True)
    try:
        success = execute_pipeline("test-pipeline", "pipeline-definition.json", "products")
        print(f"PIPELINE RUNNER FINISHED success={success}", flush=True)
    except Exception as e:
        import traceback
        print(f"PIPELINE RUNNER CRASHED: {e}", flush=True)
        traceback.print_exc()
