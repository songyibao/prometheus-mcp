from __future__ import annotations

import httpx
from typing import Any, Dict, Optional, List
from datetime import datetime, timedelta,UTC

from models import QueryParams
from utils import parse_duration_to_seconds
from loguru import logger


class PrometheusRestClient:
    def __init__(self, base_url: str, request_timeout: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        timeout_seconds = parse_duration_to_seconds(request_timeout, 30.0)
        logger.debug(f"初始化 PrometheusRestClient base_url={self.base_url} timeout={timeout_seconds}s (no auth)")
        self.client = httpx.Client(timeout=timeout_seconds)

    def _extract_data(self, resp_json: Dict[str, Any]) -> Dict[str, Any]:
        if resp_json.get("status") != "success":
            logger.error(f"Prometheus 返回非 success: {resp_json}")
            raise RuntimeError(f"Prometheus error: {resp_json}")
        return resp_json.get("data") or {}

    @staticmethod
    def _apply_optional(params: Dict[str, Any], *, timeout: Optional[str], limit: Optional[int]) -> None:
        if timeout is not None:
            params["timeout"] = timeout
        if limit is not None:
            params["limit"] = limit

    @staticmethod
    def _to_beijing(ts: Any) -> str:
        try:
            t = float(ts)
        except Exception:
            return str(ts)
        dt = datetime.fromtimestamp(t,UTC) + timedelta(hours=8)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def _convert_timestamps(self, result_type: str, result: List[Dict[str, Any]]) -> None:
        """就地修改 result 中的时间戳为北京时间字符串。
        支持两种结构：
        - vector: item.value / item.histogram
        - matrix: item.values[] / item.histograms[]
        以及可选 histograms/histogram（若存在）。
        """
        if not result:
            return
        if result_type == "vector":
            for item in result:
                val = item.get("value")
                if isinstance(val, list) and len(val) >= 1:
                    val[0] = self._to_beijing(val[0])
                hist = item.get("histogram")
                if isinstance(hist, list) and len(hist) >= 1:
                    hist[0] = self._to_beijing(hist[0])
        elif result_type == "matrix":
            for item in result:
                vals = item.get("values")
                if isinstance(vals, list):
                    for pair in vals:
                        if isinstance(pair, list) and len(pair) >= 1:
                            pair[0] = self._to_beijing(pair[0])
                hists = item.get("histograms")
                if isinstance(hists, list):
                    for pair in hists:
                        if isinstance(pair, list) and len(pair) >= 1:
                            pair[0] = self._to_beijing(pair[0])
        else:
            # 其它类型(如 scalar/string)暂不处理
            pass

    def execute(self, qp: QueryParams) -> Dict[str, Any]:
        """根据 QueryParams 判定执行瞬时或范围查询，返回 {'resultType','result'}，并将时间戳转为北京时间。"""
        is_range = qp.start is not None and qp.end is not None and qp.step is not None
        if is_range:
            params: Dict[str, Any] = {
                "query": qp.query,
                "start": qp.start,
                "end": qp.end,
                "step": qp.step,
            }
        else:
            params = {"query": qp.query}
            if qp.time is not None:
                params["time"] = qp.time
        self._apply_optional(params, timeout=qp.timeout, limit=qp.limit)
        endpoint = "/api/v1/query_range" if is_range else "/api/v1/query"
        logger.debug(f"执行{'范围' if is_range else '瞬时'}查询 endpoint={endpoint} params={{k: params[k] for k in params if k!='query'}} query={qp.query[:120]}")
        r = self.client.get(f"{self.base_url}{endpoint}", params=params)
        try:
            r.raise_for_status()
            data = self._extract_data(r.json())
        except Exception:
            logger.exception("Prometheus 查询失败")
            raise
        result_type = data.get("resultType", "")
        result_list = data.get("result", [])
        # 时间戳转换
        self._convert_timestamps(result_type, result_list)
        result_len = len(result_list) if result_list else 0
        logger.info(f"查询完成 type={result_type} size={result_len}")
        return {"resultType": result_type, "result": result_list}
