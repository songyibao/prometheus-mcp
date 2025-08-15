from loguru import logger
import os, sys

# 初始化日志（允许通过环境变量 PROM_LOG_LEVEL 调整级别）
_level = os.getenv("PROM_LOG_LEVEL", "INFO")
logger.remove()
logger.add(sys.stderr, level=_level, enqueue=True,
           format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<8} | {name}:{line} | {message}")

__all__ = [
    "config",
    "prom_client",
    "analyzer",
    "server",
]
