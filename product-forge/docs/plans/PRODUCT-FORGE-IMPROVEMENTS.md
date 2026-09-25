# Product Forge Pipeline Improvements

> **Date:** 2026-08-31
> **Purpose:** Document the system-level improvements made to Product Forge pipeline to make it truly general-purpose (not hardcoded to any specific product)

---

## Problem Statement

The original `scripts/pipeline.py` had **hardcoded "myworld"** in:
- 20 function definitions (`def show_X(project="myworld"):`)
- 20 command-parsing blocks (`project = args[0] if args else "myworld"`)

This violated the principle that **Product Forge is a general multi-product pipeline** that should work for ANY product, not just "myworld".

The issue was exposed when adding a new "phases" command which used "myworld" as default - this was a symptom of a deeper problem.

---

## Solution: System-Level Project Resolution

Created `scripts/pipeline_helpers.py` with general utilities:

```python
# scripts/pipeline_helpers.py

def get_all_projects(products_dir) -> list[str]:
    """Read all projects from products/index.json - no hardcoding."""

def get_default_project(products_dir) -> Optional[str]:
    """Return default project if exactly 1 exists, else None."""

def resolve_project(products_dir, requested) -> Optional[str]:
    """
    Resolve which project to use.
    - 0 projects: error
    - 1 project: use it
    - >1 projects: ask user to specify
    - requested matches: use it
    - requested doesn't match: error
    """

def ensure_product_completion(products_dir, project) -> dict:
    """Ensure product_completion exists in pipeline.json (uses system schema)."""

def migrate_all_projects(products_dir) -> dict:
    """Migrate all existing projects to add product_completion if missing."""
```

---

## Changes Applied

### 1. Created `scripts/pipeline_helpers.py`
- System-level utilities for project resolution
- No hardcoded project names
- Uses `products/index.json` as source of truth

### 2. Updated `scripts/pipeline.py`
**Removed all hardcoded "myworld" defaults:**
- 20 function definitions changed from `project="myworld"` to `project=None`
- 20 command-parsing blocks changed from `args[0] if args else "myworld"` to `args[0] if args else None`
- Added `resolve_project_arg()` helper that calls `_resolve_project()` from helpers
- All command handlers now use the helper to resolve the project

**Updated usage docs:**
- `/pipeline continue` now says "default: auto-detect" instead of "default: myworld"
- Examples show `continue` works for any project name

### 3. System-Level Schema (`products/.pipeline/system_config.json`)
- Defines the `product_completion_schema` template
- Defines `phases_template` (mvp, phase_2, phase_3, phase_4, phase_5)
- Any new project can be initialized from this schema

---

## Behavior

### Single Project (current state - 1 product)
```bash
$ python pipeline.py status
PROJECT STATUS: myworld
...
```

### Multiple Projects (hypothetical)
```bash
$ python pipeline.py status
ERROR: Multiple projects exist. Please specify which one:
  - myworld
  - another-product

Usage: python pipeline.py <command> <project>
```

### No Projects
```bash
$ python pipeline.py status
ERROR: No products found.
Create one with: python pipeline.py new <idea>
```

### Invalid Project
```bash
$ python pipeline.py status nonexistent
ERROR: Project 'nonexistent' not found.
Available projects: myworld
```

---

## What This Fixes

1. **No more hardcoded "myworld"** - The pipeline is truly general
2. **Any new product works** - Just add to `products/index.json`
3. **Multi-project support** - Can run commands on any product
4. **Clear errors** - User knows what to do when there's ambiguity
5. **System-level schema** - product_completion is consistent across products

---

## Tests

- **366/366 tests pass** (no regressions)
- Manual test: single project auto-selects correctly
- Manual test: multi-project asks user to specify
- Manual test: invalid project shows clear error

---

## Files Modified

| File | Change |
|------|--------|
| `scripts/pipeline_helpers.py` | **NEW** - System-level utilities |
| `scripts/pipeline.py` | **MODIFIED** - Removed 40 hardcoded "myworld" references |

---

## What Still Needs Work (Future)

1. **Auto-migration for existing projects** - The migration helper exists but isn't called automatically
2. **Agent contracts** - `.opencode/agent/*.md` files still have "myworld" examples
3. **Documentation** - User-facing docs need updating

---

## Usage

```bash
# Single project (auto-detected)
python pipeline.py status

# Explicit project
python pipeline.py status myworld
python pipeline.py phases myworld

# Any new product
python pipeline.py status any-new-product
python pipeline.py phases any-new-product
```
