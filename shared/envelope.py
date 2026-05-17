from typing import Any


def ok(data: Any = None, **kwargs: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": True}
    if data is not None:
        result["data"] = data
    result.update(kwargs)
    return result


def err(code: str, message: str, **kwargs: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"ok": False, "error": {"code": code, "message": message}}
    result.update(kwargs)
    return result
