from __future__ import annotations

from typing import Any, Dict, List, Annotated, Optional

from fastmcp import FastMCP

from analyzer import AnalyzeService
from config import ConfigManager
from models import AnalyzeRequest, QueryParams
from prom_client import PrometheusRestClient
from utils import compute_adaptive_step
from loguru import logger
import time

# 加载配置以获取端口
_cfg_for_port = ConfigManager.load()
_port = _cfg_for_port.global_config.serverPort or 7000
logger.info(f"初始化 FastMCP 服务端口: {_port}")
app = FastMCP("prometheus-mcp", port=_port)


@app.tool()
def list_supported_analyze_type() -> List[Dict[str, Any]]:
    """任何时候都请你先调用本工具，列出服务支持的所有分析类型。"""
    cfg = ConfigManager.load()
    logger.info("调用 list_supported_analyze_type")
    return [
        {
            "name": ai.name,
            "description": ai.description or "",
        }
        for ai in cfg.global_config.appInstances
    ]


# @app.tool()
def prom_query(query: Annotated[str, "PromQL 查询语句"],
               time: Annotated[int, "查询的时间戳(unix timestamp)，单位:秒"] = None,
               timeout: Annotated[str, "查询超时时间，格式如 15s、1m、2h 等，默认为配置文件中的 queryTimeout"] = None,
               limit: Annotated[int, "查询结果数限制，默认为配置文件中的 limit"] = None) -> Dict[str, Any]:
    logger.info(f"调用 prom_query time={time} limit={limit}")
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig
    client = PrometheusRestClient(
        cfg.base_url,
        request_timeout=pcfg.queryTimeout,
    )
    data = client.execute(QueryParams(query=query, time=time, timeout=timeout, limit=limit))
    return data


# @app.tool()
def prom_query_range(
    query: Annotated[str, "PromQL 查询语句"],
    start: Annotated[int, "范围查询起始时间戳 (unix)，单位:秒"],
    end: Annotated[int, "范围查询结束时间戳 (unix)，单位:秒"],
    interval: Annotated[Optional[str], "范围向量窗口大小(用于模板 {{interval}})，省略则使用配置 defaultInterval"] = None,
    timeout: Annotated[Optional[str], "查询超时时间，格式如 15s、1m、2h；省略则使用配置 queryTimeout"] = None,
    limit: Annotated[Optional[int], "结果数据行限制；省略则使用配置 limit"] = None,
) -> Dict[str, Any]:
    """执行 PromQL 范围查询（自适应步长）并返回查询结果。
    步长根据 (end-start) 与配置 maxPoints 自动计算。"""
    logger.info(f"调用 prom_query_range(start={start}, end={end}, interval={interval}) 自适应步长")
    if end <= start:
        return {"error": "end 必须大于 start"}
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig
    eff_interval = interval or pcfg.defaultInterval or "5m"
    step = compute_adaptive_step(start, end, max_points=pcfg.maxPoints, default_step=pcfg.defaultStep)
    logger.debug(f"自适应步长 step={step} interval={eff_interval}")
    client = PrometheusRestClient(
        cfg.base_url,
        request_timeout=pcfg.queryTimeout,
    )
    data = client.execute(QueryParams(query=query, start=start, end=end, step=step, timeout=timeout, limit=limit))
    data["step"] = step
    data["interval"] = eff_interval
    return data


@app.tool()
def analyze(
    name: Annotated[str, "分析类型名称（使用 list_supported_analyze_type 工具获取的 name 字段）"],
    labels: Annotated[Dict[str, str], "PromQL 标签过滤条件，如 {'cluster_name':'aicall-tj'}或{'instance':'10.0.0.1:9104'}等；可传空字典 {}，代表不过滤"],
    start: Annotated[int, "范围查询起始时间戳(秒)"],
    end: Annotated[int, "范围查询结束时间戳(秒)"],
    interval: Annotated[Optional[str], "范围向量窗口大小(用于替换模板 {{interval}})，省略则使用配置 defaultInterval"] = None,
) -> Dict[str, Any]:
    """执行预定义分析（强制范围查询，自适应步长）。"""
    logger.info(f"调用 analyze name={name} start={start} end={end} interval={interval} (自适应步长)")
    if end <= start:
        return {"error": "end 必须大于 start"}
    cfg = ConfigManager.load()
    pcfg = cfg.global_config.prometheusConfig
    eff_interval = interval or pcfg.defaultInterval or "5m"
    step = compute_adaptive_step(start, end, max_points=pcfg.maxPoints, default_step=pcfg.defaultStep)
    logger.debug(f"analyze 自适应步长 step={step} interval={eff_interval}")
    client = PrometheusRestClient(
        cfg.base_url,
        request_timeout=pcfg.queryTimeout,
    )
    srv = AnalyzeService(cfg, client)
    resp = srv.get_report(AnalyzeRequest(name=name, labels=labels or {}, start=start, end=end, step=step, interval=eff_interval))
    out = resp.model_dump()
    out["step"] = step
    out["interval"] = eff_interval
    return out


@app.tool()
def current_timestamp() -> Dict[str, int]:
    """获取当前 Unix 时间戳(秒)"""
    ts = int(time.time())
    logger.info(f"调用 current_timestamp now={ts}")
    return {"timestamp": ts}


# @app.tool()
def subtract(
    minuend: Annotated[int, "被减数，通常为结束时间戳(秒)或当前时间戳"],
    subtrahend: Annotated[int, "减数，需减去的秒数（如 1800 表示30分钟）"],
) -> Dict[str, int]:
    """执行整数减法: result = minuend - subtrahend。
    规则：凡是需要计算类似“最近X分钟/小时/秒”的起始时间，必须调用本工具而不是在提示中直接写出结果。"""
    result = minuend - subtrahend
    logger.info(f"调用 subtract {minuend}-{subtrahend}={result}")
    return {"result": result}


@app.tool()

def loki_query_range(
    query: Annotated[str, "Loki LogQL 查询字符串。例如 {instance=\"mysql:3306\"}、{job=\"mysql_logs\"}；只写标签筛选与表达式，不要在这里放时间范围。"],
    start: Annotated[str, "起始时间，RFC3339Nano 字符串，必须包含时区(Z 或 ±HH:MM)。示例：2025-08-26T12:00:00.000000000Z(UTC) 或 2025-08-26T20:00:00.000000000+08:00(北京时间)。若表达北京时间，请使用 +08:00，不要误写成 Z。支持不足9位小数(会右补零至纳秒)。"],
    end: Annotated[str, "结束时间，RFC3339Nano 字符串，必须包含时区(Z 或 ±HH:MM)，且严格大于 start。示例：2025-08-26T12:30:00.000000000Z 或 2025-08-26T20:30:00.000000000+08:00；建议与 start 使用同一时区表达。"],
) -> Dict[str, Any]:
    """Loki 日志范围查询。

    要点：
    - start/end 必须是 RFC3339Nano 并包含时区(Z 或 ±HH:MM)。若是北京时间请用 +08:00；不要把北京时间误写成 Z，否则会偏移 8 小时。
    - 示例等价时间：
      * 2025-08-26T12:34:56.123456789Z
      * 2025-08-26T20:34:56.123456789+08:00
      * 2025-08-26T04:34:56.123456789-08:00
    - 函数内部会将 start/end 解析为纳秒并调用 Loki；返回结果中 values 的时间戳会被转换为北京时间字符串(毫秒精度)便于阅读。
    - 支持不足 9 位小数，自动右补 0 到纳秒精度。
    - 常见错误：把北京时间写成以 Z 结尾的字符串(那是 UTC)，请改用 +08:00 或先转换到 UTC 后再用 Z。
    """
    from loki_client import LokiRestClient  # 绝对导入以兼容脚本运行
    from utils import parse_rfc3339_nano_to_ns
    logger.info(f"调用 loki_query_range start={start} end={end}")
    try:
        start_ns = parse_rfc3339_nano_to_ns(start)
        end_ns = parse_rfc3339_nano_to_ns(end)
    except Exception as e:
        return {"error": f"时间格式错误: {e}"}
    if end_ns <= start_ns:
        return {"error": "end 必须大于 start"}
    cfg = ConfigManager.load()
    lcfg = cfg.global_config.lokiConfig
    if not lcfg or not lcfg.baseUrl:
        logger.error("lokiConfig 未配置 baseUrl")
        return {"error": "lokiConfig.baseUrl 未配置"}
    client = LokiRestClient(lcfg.baseUrl, request_timeout=lcfg.queryTimeout)
    try:
        resp = client.query_range(query=query, start_ns=start_ns, end_ns=end_ns)
    except Exception as e:
        return {"error": f"Loki 查询失败: {e}"}
    return resp


def main() -> None:
    logger.info("启动 prometheus-mcp 服务器")
    app.run(transport="streamable-http")


if __name__ == "__main__":
    main()
