"""Feishu (Lark) Open API integration for MemScope."""
from .client import FeishuClient
from .pipeline import FeishuMemoryPipeline

__all__ = ["FeishuClient", "FeishuMemoryPipeline"]
