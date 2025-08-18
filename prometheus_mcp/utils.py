from __future__ import annotations

import math
from typing import Optional


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
        if t.endswith("d"):
            return float(t[:-1]) * 86400.0
        return float(t)
    except Exception:
        return default


def _seconds_to_prom_duration(sec: float) -> str:
    # 选择最简单位表示
    sec_int = int(sec)
    if sec_int % 3600 == 0:
        return f"{sec_int // 3600}h"
    if sec_int % 60 == 0:
        return f"{sec_int // 60}m"
    return f"{max(1, sec_int)}s"


def compute_adaptive_step(start: int, end: int, *, max_points: Optional[int], default_step: Optional[str]) -> str:
    """根据时间范围与配置计算自适应步长（不再使用最小步长配置）。
    1. 若未配置 max_points => 使用 default_step 或 60s。
    2. ideal = range_seconds / max_points。
    3. ideal 下限为 1 秒。
    4. 在候选表中选择 >= ideal 的最小值，若超出则按天放大。
    5. 返回 Prometheus 步长字符串。
    """
    range_seconds = end - start
    if range_seconds <= 0:
        raise ValueError("时间范围无效: end 必须大于 start")
    if not max_points or max_points <= 0:
        return default_step or "60s"
    ideal = range_seconds / max_points
    if ideal < 1:
        ideal = 1
    candidates = [
        1, 2, 5, 10, 15, 30,
        60, 120, 300, 600, 900, 1200, 1800,
        3600, 7200, 10800, 21600, 43200,
        86400, 172800, 259200, 604800
    ]
    chosen = None
    for c in candidates:
        if c >= ideal:
            chosen = c
            break
    if chosen is None:
        # 超出最大候选，按天向上取整
        days = math.ceil(ideal / 86400)
        chosen = days * 86400
    return _seconds_to_prom_duration(chosen)
