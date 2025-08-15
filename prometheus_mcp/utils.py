from __future__ import annotations

def parse_duration_to_seconds(text: str | None, default: float = 30.0) -> float:
    if not text:
        return default
    t = text.strip().lower()
    try:
        if t.endswith("ms"):
            return float(t[:-2]) / 1000.0
        if t.endswith("s"):
            return float(t[:-1])
        if t.endswith("m"):
            return float(t[:-1]) * 60.0
        if t.endswith("h"):
            return float(t[:-1]) * 3600.0
        return float(t)
    except Exception:
        return default
