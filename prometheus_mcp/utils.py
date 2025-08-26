from __future__ import annotations

import math
from typing import Optional

# 新增
import re
import calendar


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


# 新增：解析 RFC3339Nano 为纳秒
_RFC3339_NANO_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?([Zz]|[+-]\d{2}:\d{2})$")


def parse_rfc3339_nano_to_ns(text: str) -> int:
    """将 RFC3339Nano 格式(如 2025-08-26T12:34:56.123456789Z) 解析为纳秒级 Unix 时间戳(int)。
    支持 Z 或 ±HH:MM 偏移。若小数位不足9位，将右侧补0。"""
    if not isinstance(text, str):
        raise ValueError("时间必须为 RFC3339Nano 字符串")
    m = _RFC3339_NANO_RE.match(text.strip())
    if not m:
        raise ValueError("时间格式不合法，需为 RFC3339Nano，例如 2025-08-26T12:34:56.123456789Z")
    y, mo, d, h, mi, s, frac, tz = m.groups()
    y = int(y); mo = int(mo); d = int(d); h = int(h); mi = int(mi); s = int(s)
    frac_str = frac or ""
    # 右补零至9位
    if len(frac_str) < 9:
        frac_str = frac_str + ("0" * (9 - len(frac_str)))
    fraction_ns = int(frac_str or "0")

    # 偏移量(秒)
    if tz in ("Z", "z"):
        offset_sec = 0
    else:
        sign = 1 if tz[0] == '+' else -1
        th = int(tz[1:3])
        tm = int(tz[4:6])
        offset_sec = sign * (th * 3600 + tm * 60)

    # 将本地(带偏移)时间转换为 UTC epoch 秒
    # calendar.timegm 将传入元组按 UTC 解释
    epoch_sec_as_if_utc = calendar.timegm((y, mo, d, h, mi, s, 0, 0, 0))
    epoch_sec_utc = epoch_sec_as_if_utc - offset_sec

    ns = epoch_sec_utc * 1_000_000_000 + fraction_ns
    return ns
