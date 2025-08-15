from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class QueryParams(BaseModel):
    """统一的 PromQL 查询参数模型。
    - 若提供 start/end/step => 进行范围查询
    - 否则 => 瞬时查询
    """
    query: str
    # 范围查询参数（全部提供才视为范围查询）
    start: Optional[int] = None
    end: Optional[int] = None
    step: Optional[str] = None
    # 瞬时查询专用，可选
    time: Optional[int] = None
    # 通用可选控制参数
    timeout: Optional[str] = None
    limit: Optional[int] = None


class AnalyzeRequest(BaseModel):
    name: str
    labels: Dict[str, str] = Field(default_factory=dict)
    # 分析时可选范围参数（供上层判断是否使用范围查询，不直接用于 prom_client）
    start: Optional[int] = None
    end: Optional[int] = None
    step: Optional[str] = None


class AnalyzeResponse(BaseModel):
    name: str
    description: Optional[str] = None
    rangeQuery: bool = False
    start: Optional[int] = None
    end: Optional[int] = None
    step: Optional[str] = None
    # 每项 = { description: str, resultType: str, result: list }
    resultData: List[Dict[str, Any]] = Field(default_factory=list)
