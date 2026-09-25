"""Product Forge Dashboard API package (FastAPI).

The single API layer the new dashboard (Next.js) talks to. Read-only over the
pipeline's truths; actions are routed through the owning core modules
(core/backlog.py, core/intake.py, core/model_fit.py, ...). No store is written
directly from this layer.
"""
