from __future__ import annotations

import httpx
from typing import Any, Dict, Optional
from datetime import datetime, timedelta, UTC

from loguru import logger


class LokiRestClient:
    def __init__(self, base_url: str, request_timeout: Optional[str] = None):
        from utils import parse_duration_to_seconds  # 延迟导入以避免循环
        self.base_url = base_url.rstrip("/")
        timeout_seconds = parse_duration_to_seconds(request_timeout, 30.0)
        logger.debug(f"初始化 LokiRestClient base_url={self.base_url} timeout={timeout_seconds}s")
        self.client = httpx.Client(timeout=timeout_seconds)

    @staticmethod
    def _ns_to_beijing_str(ns_str: str) -> str:
        try:
            # Loki 返回的时间戳是纳秒字符串
            ns = int(ns_str)
            ts_sec = ns / 1_000_000_000
        except Exception:
            return str(ns_str)
        dt = datetime.fromtimestamp(ts_sec, UTC) + timedelta(hours=8)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # 毫秒精度

    def _convert_streams_timestamps(self, data: Dict[str, Any]) -> None:
        if not data:
            return
        if data.get("resultType") != "streams":
            return
        result = data.get("result")
        if not isinstance(result, list):
            return
        for stream in result:
            values = stream.get("values")
            if isinstance(values, list):
                for pair in values:
                    if isinstance(pair, list) and len(pair) >= 1:
                        pair[0] = self._ns_to_beijing_str(pair[0])

    def query_range(self, query: str, start_ns: int, end_ns: int) -> Dict[str, Any]:
        """调用 Loki 范围查询 /loki/api/v1/query_range，返回完整 JSON，并将 values 时间戳转为北京时间字符串。"""
        params = {
            "query": query,
            "start": str(start_ns),  # Loki 接受纳秒级字符串
            "end": str(end_ns),
        }
        url = f"{self.base_url}/loki/api/v1/query_range"
        logger.debug(f"Loki 范围查询 url={url} params={params} query={query[:120]}")
        r = self.client.get(url, params=params)
        try:
            r.raise_for_status()
            resp_json = r.json()
        except Exception:
            logger.exception("Loki 查询失败")
            raise
        if not isinstance(resp_json, dict):
            logger.error(f"Loki 返回非 JSON 对象: {type(resp_json)}")
            raise RuntimeError("Invalid Loki response")
        if resp_json.get("status") != "success":
            logger.error(f"Loki 返回非 success: {resp_json}")
            # 仍返回以便上层可见错误
            return resp_json
        data = resp_json.get("data") or {}
        self._convert_streams_timestamps(data)
        size = len(data.get("result") or [])
        logger.info(f"Loki 查询完成 type={data.get('resultType')} size={size}")
        return resp_json
