from typing import Any, Dict

from core import events


def test_bus_status_type_hints_resolve():
    assert events.bus_status.__annotations__["return"] == Dict[str, Any]
