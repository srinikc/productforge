"""Dev CLI: migrate legacy agent .md cards to the standardized AgentSpec format.

Usage:
  python scripts/dev/migrate_agents.py            # dry-run (show plan)
  python scripts/dev/migrate_agents.py --apply    # apply migration (backs up)
"""
import os
import sys

sys.path.insert(0, os.getcwd())


def main():
    from core.agent_migrator import show_migration_plan
    dry = "--apply" not in sys.argv
    show_migration_plan(dry_run=dry)


if __name__ == "__main__":
    main()
