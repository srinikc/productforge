from typing import Any, Dict, get_type_hints

from core import events


def test_bus_status_type_hints_resolve():
    hints = get_type_hints(events.bus_status)
    assert hints["return"] == Dict[str, Any]
