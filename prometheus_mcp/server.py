from __future__ import annotations

from typing import Any, Dict, List, Annotated, Optional

from fastmcp import FastMCP

from analyzer import AnalyzeService
from config import ConfigManager
from models import AnalyzeRequest, QueryParams
from prom_client import PrometheusRestClient
from utils import parse_duration_to_seconds
from loguru import logger
import time

app = FastMCP("prometheus-mcp")


@app.tool()
def list_supported_analyze_type() -> List[Dict[str, Any]]:
    """列出服务支持的所有分析类型，如 mysql指标分析、redis指标分析 等"""
    cfg = ConfigManager.load()
    logger.info("调用 list_supported_analyze_type")
    return [
        {
            "name": ai.name,
            "description": ai.description or "",
            "metrics": [qt.metric for qt in ai.queryTemplates],
        }
        for ai in cfg.global_config.appInstances
    ]


@app.tool()
def prom_query(query: Annotated[str, "PromQL 查询语句"],
               time: Annotated[int, "查询的时间戳(unix timestamp)，单位:秒"] = None,
               timeout: Annotated[str, "查询超时时间，格式如 15s、1m、2h 等，默认为配置文件中的 queryTimeout"] = None,
               limit: Annotated[int, "查询结果数限制，默认为配置文件中的 limit"] = None) -> Dict[str, Any]:
    logger.info(f"调用 prom_query time={time} limit={limit}")
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig
    client = PrometheusRestClient(
        cfg.base_url,
        pcfg.username,
        pcfg.password,
        request_timeout=pcfg.queryTimeout,
    )
    data = client.execute(QueryParams(query=query, time=time, timeout=timeout, limit=limit))
    return data


@app.tool()
def prom_query_range(
    query: Annotated[str, "PromQL 查询语句"],
    start: Annotated[int, "范围查询起始时间戳 (unix)，单位:秒"],
    end: Annotated[int, "范围查询结束时间戳 (unix)，单位:秒"],
    step: Annotated[Optional[str], "查询步长(数据分辨率)，如 15s、30s、1m；省略则使用配置 defaultStep"] = None,
    timeout: Annotated[Optional[str], "查询超时时间，格式如 15s、1m、2h；省略则使用配置 queryTimeout"] = None,
    limit: Annotated[Optional[int], "结果数据行限制；省略则使用配置 limit"] = None,
) -> Dict[str, Any]:
    logger.info(f"调用 prom_query_range start={start} end={end} step={step}")
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig
    client = PrometheusRestClient(
        cfg.base_url,
        pcfg.username,
        pcfg.password,
        request_timeout=pcfg.queryTimeout,
    )
    effective_step = step or (pcfg.defaultStep or "15s")
    if pcfg.minStep and parse_duration_to_seconds(effective_step) < parse_duration_to_seconds(pcfg.minStep):
        logger.debug(f"步长 {effective_step} 小于 minStep {pcfg.minStep}，已替换")
        effective_step = pcfg.minStep
    data = client.execute(QueryParams(query=query, start=start, end=end, step=effective_step, timeout=timeout, limit=limit))
    return data


@app.tool()
def analyze(
    name: Annotated[str, "分析类型名称（使用 list_supported_analyze_type 工具获取的 name 字段）"],
    labels: Annotated[Dict[str, str], "PromQL 标签过滤条件，如 {'instance':'10.0.0.1:9104'}；可传空字典 {} 表示不额外过滤"],
    start: Annotated[Optional[int], "可选：范围查询起始时间戳(秒)。与 end/step 组合决定是否执行范围查询"] = None,
    end: Annotated[Optional[int], "可选：范围查询结束时间戳(秒)。若仅提供 end 则默认 start=end-1800(最近30分钟)"] = None,
    step: Annotated[Optional[str], "可选：步长，如 15s/30s/1m；缺省使用配置 defaultStep；若小于配置 minStep 则自动提升"] = None,
) -> Dict[str, Any]:
    logger.info(f"调用 analyze name={name} start={start} end={end} step={step}")
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig

    any_range = start is not None or end is not None or step is not None
    err: Optional[str] = None
    eff_start, eff_end, eff_step = start, end, step

    if any_range:
        if eff_end is not None and eff_start is None:
            eff_start = eff_end - 1800
            logger.debug(f"推导 start={eff_start} (end-1800)")
        if eff_start is not None and eff_end is None:
            err = "仅提供 start 不能确定范围，请同时提供 end，或只提供 end 让系统推导 start"
        if eff_step is None:
            eff_step = pcfg.defaultStep or "1m"
        if pcfg.minStep and eff_step and parse_duration_to_seconds(eff_step) < parse_duration_to_seconds(pcfg.minStep):
            logger.debug(f"步长 {eff_step} 小于 minStep {pcfg.minStep}，已提升")
            eff_step = pcfg.minStep
    if err:
        logger.warning(f"analyze 参数错误: {err}")
        return {"error": err}

    client = PrometheusRestClient(
        cfg.base_url,
        pcfg.username,
        pcfg.password,
        request_timeout=pcfg.queryTimeout,
    )
    srv = AnalyzeService(cfg, client)

    if not (eff_start is not None and eff_end is not None and eff_step is not None):
        eff_start = eff_end = eff_step = None
    resp = srv.get_report(AnalyzeRequest(name=name, labels=labels or {}, start=eff_start, end=eff_end, step=eff_step))
    return resp.model_dump()


@app.tool()
def current_timestamp() -> Dict[str, int]:
    """获取当前 Unix 时间戳(秒)"""
    ts = int(time.time())
    logger.info(f"调用 current_timestamp now={ts}")
    return {"timestamp": ts}


def main() -> None:
    logger.info("启动 prometheus-mcp 服务器")
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
