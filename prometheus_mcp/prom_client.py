from __future__ import annotations

import httpx
from typing import Any, Dict, Optional

from models import QueryParams
from utils import parse_duration_to_seconds
from loguru import logger


class PrometheusRestClient:
    def __init__(self, base_url: str, username: Optional[str] = None, password: Optional[str] = None,
                 request_timeout: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.auth = (username, password) if username and password else None
        timeout_seconds = parse_duration_to_seconds(request_timeout, 30.0)
        logger.debug(f"初始化 PrometheusRestClient base_url={self.base_url} timeout={timeout_seconds}s auth={'yes' if self.auth else 'no'}")
        self.client = httpx.Client(auth=self.auth, timeout=timeout_seconds)

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

    def execute(self, qp: QueryParams) -> Dict[str, Any]:
        """根据 QueryParams 判定执行瞬时或范围查询，返回 {'resultType','result'}"""
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
        logger.debug(f"执行{'范围' if is_range else '瞬时'}查询 endpoint={endpoint} params={params}")
        r = self.client.get(f"{self.base_url}{endpoint}", params=params)
        try:
            r.raise_for_status()
            data = self._extract_data(r.json())
        except Exception:
            logger.exception("Prometheus 查询失败")
            raise
        result = data.get("result")
        # 因为我们每次查询都只是执行一条查询语句，所以只要成功了，result的长度实际都是1
        if not result or len(result) != 1:
            logger.warning(f"Prometheus 查询结果异常: {data}")
            return {"resultType": data.get("resultType", ""), "result": []}
        # 获取该查询的真实查询结果数据
        real_data = result[0].get("values")
        real_data_len = len(real_data) if real_data else 0
        logger.info(f"查询完成 type={data.get('resultType','')} size={real_data_len}")
        return {"resultType": data.get("resultType", ""), "result": data.get("result", [])}
