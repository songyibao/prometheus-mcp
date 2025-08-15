from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
    username: Optional[str] = None
    password: Optional[str] = None
    queryTimeout: Optional[str] = None
    defaultStep: Optional[str] = None
    minStep: Optional[str] = None  # 新增：允许的最小步长，若外部传入更小步长则使用该值


class GlobalConfig(BaseModel):
    appInstances: List[AppInstance] = Field(default_factory=list)
    prometheusConfig: PrometheusConfig


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
        logger.info(f"配置加载成功: appInstances={len(gc.appInstances)} baseUrl={gc.prometheusConfig.baseUrl}")
        return ConfigManager(global_config=gc)
