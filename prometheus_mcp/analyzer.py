from __future__ import annotations
from typing import Dict, List
from config import ConfigManager, QueryTemplate
from models import AnalyzeRequest, AnalyzeResponse, QueryParams
from prom_client import PrometheusRestClient
from loguru import logger


def render_labels(labels: Dict[str, str]) -> str:
    if not labels:
        return ""
    parts = [f'{k}="{v}"' for k, v in labels.items()]
    return "{" + ",".join(parts) + "}"


def render_query(template: str, labels: Dict[str, str]) -> str:
    return template.replace("{{labels}}", render_labels(labels))


def apply_placeholders(text: str, labels: Dict[str, str], interval: str) -> str:
    return text.replace("{{labels}}", render_labels(labels)).replace("{{interval}}", interval)


class AnalyzeService:
    def __init__(self, cfg: ConfigManager, client: PrometheusRestClient):
        self.cfg = cfg
        self.client = client

    def execute_query(self, qt: QueryTemplate, labels: Dict[str, str], *, start=None, end=None, step=None, interval: str = "5m") -> Dict[str, any]:
        templ = qt.template or ""
        if not templ:
            logger.debug(f"跳过空模板 metric={qt.metric}")
            return {"metric": qt.metric, "description": qt.description or "", "resultType": "", "result": []}
        q = apply_placeholders(templ, labels, interval)
        if start is not None and end is not None and step is not None:
            qp = QueryParams(query=q, start=start, end=end, step=step)
            logger.debug(f"执行范围分析查询 metric={qt.metric} step={step} start={start} end={end} interval={interval}")
        else:
            qp = QueryParams(query=q)
            logger.debug(f"执行瞬时分析查询 metric={qt.metric} interval={interval}")
        data = self.client.execute(qp)
        desc = qt.description or ""
        if desc:
            desc = apply_placeholders(desc, labels, interval)
        return {"metric": qt.metric, "description": desc, **data}

    def execute_queries(self, qts: List[QueryTemplate], labels: Dict[str, str], *, start=None, end=None, step=None, interval: str = "5m") -> List[Dict[str, any]]:
        logger.info(f"批量执行分析查询 count={len(qts)} range={(start is not None and end is not None and step is not None)} interval={interval}")
        return [self.execute_query(qt, labels, start=start, end=end, step=step, interval=interval) for qt in qts]

    def get_report(self, req: AnalyzeRequest) -> AnalyzeResponse:
        logger.info(f"生成分析报告 name={req.name} range={(req.start is not None and req.end is not None and req.step is not None)} interval={req.interval}")
        gi = next((x for x in self.cfg.global_config.appInstances if x.name == req.name), None)
        if gi is None:
            logger.error(f"分析类型未找到 name={req.name}")
            raise ValueError(f"AppInstance not found: {req.name}")
        is_range = req.start is not None and req.end is not None and req.step is not None
        results = self.execute_queries(gi.queryTemplates, req.labels, start=req.start, end=req.end, step=req.step, interval=req.interval or "5m")
        return AnalyzeResponse(name=gi.name, description=gi.description, rangeQuery=is_range, start=req.start, end=req.end, step=req.step, interval=req.interval, resultData=results)
