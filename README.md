# Prometheus MCP Server (Python)

A minimal MCP server using `fastmcp` that mirrors the Java Spring Boot app:

- Reads config.json (Prometheus config + appInstances + query templates)
- Builds PromQL by rendering `{{labels}}`
- Executes instant and range queries to Prometheus HTTP API
- Provides MCP tools for listing services and generating analysis reports

## Layout

- `prometheus_mcp/` Python package
  - `config.py` Pydantic models and loader for `config.json`
  - `prom_client.py` Prometheus HTTP client via httpx
  - `analyzer.py` Render templates and aggregate results
  - `server.py` fastmcp MCP server exposing tools
- `config.json` configuration copied from the Java app

## Quick start

1. Ensure Python 3.9+
2. Install deps (example):
   pip install -e .
3. Run server:
   prometheus-mcp

Set PROM_CONFIG_PATH env var to point to a specific config path (default: ./config.json).
