"""
Shared 模块 - 共享工具

包含：
- LLMCaller LLM 调用器（多级降级）
- cosine_similarity 余弦相似度计算
"""

from .llm_call import LLMCaller
from .utils import cosine_similarity, cosine_similarity_batch

__all__ = ["LLMCaller", "cosine_similarity", "cosine_similarity_batch"]