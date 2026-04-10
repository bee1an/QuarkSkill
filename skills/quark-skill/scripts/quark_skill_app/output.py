from __future__ import annotations

import json
from typing import Any


def emit(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False))


def ok(results: dict[str, Any], hint: str) -> int:
    emit({"ok": True, "status": "ok", "hint": hint, "results": results})
    return 0


def fail(code: str, message: str, hint: str, recoverable: bool = True) -> int:
    emit(
        {
            "ok": False,
            "error": code,
            "message": message,
            "detail": message,
            "hint": hint,
            "recoverable": recoverable,
        }
    )
    return 1 if recoverable else 2
