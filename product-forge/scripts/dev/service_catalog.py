"""Dev CLI: list the service catalog (required/optional) and config questions.

Usage:
  python scripts/dev/service_catalog.py               # list services
  python scripts/dev/service_catalog.py --questions   # include config questions
"""
import os
import sys

sys.path.insert(0, os.getcwd())


def _name(c):
    return str(getattr(c, "name", None) or getattr(c, "key", None) or c)


def main():
    from core.service_catalog import (get_all_required_services, get_optional_services,
                                      format_service_question)
    for label, cats in (("REQUIRED", get_all_required_services()),
                        ("OPTIONAL", get_optional_services())):
        print(f"== {label} ==")
        for c in cats or []:
            print(" -", _name(c))
    if "--questions" in sys.argv:
        print("\n== CONFIG QUESTIONS ==")
        for c in get_all_required_services() or []:
            try:
                print(format_service_question(c))
            except Exception as e:
                print(f"[{_name(c)}] {e}")


if __name__ == "__main__":
    main()
