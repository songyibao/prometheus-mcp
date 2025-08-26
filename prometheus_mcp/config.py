from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Optional  # 移除未使用的 Any, Dict

from pydantic import BaseModel, Field, ValidationError
from loguru import logger


class QueryTemplate(BaseModel):
    metric: str
    description: Optional[str] = None
    template: str


class AppInstance(BaseModel):
    name: str
    description: Optional[str] = None
    queryTemplates: List[QueryTemplate] = Field(default_factory=list)


class PrometheusConfig(BaseModel):
    baseUrl: str
    queryTimeout: Optional[str] = None
    defaultStep: Optional[str] = None
    maxPoints: Optional[int] = None
    defaultInterval: Optional[str] = None


class LokiConfig(BaseModel):
    baseUrl: str
    queryTimeout: Optional[str] = None


class GlobalConfig(BaseModel):
    appInstances: List[AppInstance] = Field(default_factory=list)
    prometheusConfig: PrometheusConfig
    lokiConfig: Optional[LokiConfig] = None
    serverPort: Optional[int] = Field(default=7000, description="MCP 服务监听端口")


@dataclass
class ConfigManager:
    global_config: GlobalConfig

    @property
    def base_url(self) -> str:
        return self.global_config.prometheusConfig.baseUrl

    @staticmethod
    def load(path: Optional[str] = None) -> "ConfigManager":
        cfg_path = path or os.getenv("PROM_CONFIG_PATH") or os.path.abspath("config.json")
        logger.debug(f"加载配置文件: {cfg_path}")
        with open(cfg_path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        try:
            gc = GlobalConfig.model_validate(raw)
        except ValidationError as e:
            logger.error(f"配置文件校验失败: {e}")
            raise RuntimeError(f"Invalid config.json: {e}")
        logger.info(
            f"配置加载成功: appInstances={len(gc.appInstances)} promBase={gc.prometheusConfig.baseUrl} "
            f"lokiBase={(gc.lokiConfig.baseUrl if gc.lokiConfig else 'N/A')} port={gc.serverPort}"
        )
        return ConfigManager(global_config=gc)
