# Prometheus MCP Server (Python)

Prometheus/VictoriaMetrics 指标巡检 / 分析 MCP 服务。读取 `config.json` 中的应用实例与 PromQL 模板，
暴露一组工具（tools）给大模型或客户端，给大模型提供获取真实数据并分析的能力。

> 基于[FastMCP](https://gofastmcp.com/getting-started/welcome)

---

## 运行

- Python >= 3.11 或 [uv:python 包管理工具](https://docs.astral.sh/uv/getting-started/installation/)
- 已部署 Prometheus / VictoriaMetrics 并暴露 HTTP API

### 修改服务配置

编辑根目录下的 `config.json`，配置 Prometheus/VictoriaMetrics 的 API 地址和本服务的端口

```jsonc
{
  "serverPort": 7000, // MCP 服务端口
  "prometheusConfig": {
    "baseUrl": "http://localhost:8428", // Prometheus 或 VictoriaMetrics 的 API 地址
    ... // 其他配置项
  }
}
```

> 运行环境管理下面二选一即可

### 使用 `pip`

准备好 Python 虚拟环境，需要 Python 3.11 或更高版本

安装依赖

```bash
pip install -r requirements.txt
```

可选镜像源

```bash
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
```

运行 MCP 服务

```bash
python prometheus_mcp/server.py
```

### 使用 uv

安装 `uv`：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

配置项目镜像源(可选)  
修改根目录 `pyproject.toml`

```toml
[[tool.uv.index]]
url = "http://mirrors.aliyun.com/pypi/simple/"
```

同步依赖

```bash
uv sync
```

运行 MCP 服务

```bash
uv run prometheus_mcp/server.py
```

### 启动后简单探测

```bash
curl -s http://127.0.0.1:7000/mcp | head
```

### 暴露为 HTTP OpenAPI(用于对接不支持 MCP Client 的上层服务)

```bash
mcpo --port 8002 --server-type streamable-http -- http://127.0.0.1:7000/mcp
```

其中,`--port` 指定 OpenAPI 端口，`-- http://`后面是本 MCP 服务地址

## 环境变量

| 变量名             | 描述                                              |
| ------------------ | ------------------------------------------------- |
| `PROM_CONFIG_PATH` | 配置文件路径，默认为当前工作目录下的`config.json` |

---

## 配置文件关键字段

```jsonc
{
  "serverPort": 7000, // MCP 服务端口
  "prometheusConfig": {
    "baseUrl": "http://localhost:8428", // Prometheus 或 VictoriaMetrics 的 API 地址
    "queryTimeout": "30s", // query 查询超时时间
    "defaultStep": "1m", // 默认查询步长(未配置maxPoints时生效)
    "maxPoints": 30, // 最大返回点数，用于控制返回的数据量
    "defaultInterval": "5m" // 默认时间窗口大小,会被填充到查询模板中的 {{interval}}
  },
  "appInstances": [
    {
      "name": "mysql_analyze",
      "description": "通过prometheus mysql exporter的查询语句获取mysql性能指标",
      "queryTemplates": [
        {
          "metric": "uptime_seconds",
          "description": "MySQL 实例累计运行时长(秒)",
          "template": "mysql_global_status_uptime{{labels}}"
        },
        ... // 更多指标查询语句模板,根据需要定义
      ]
    },
    ... // 更多分析类型如 redis_analyze和node_analyze,根据需要定义
  ]
}
```
