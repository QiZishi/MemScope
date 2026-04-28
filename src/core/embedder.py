"""
Real Embedder - 真实的嵌入生成器

调用外部 API（OpenAI/其他）生成真实的文本嵌入
"""

from typing import List, Optional
import logging
import os

logger = logging.getLogger(__name__)


class RealEmbedder:
    """真实的嵌入生成器"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "text-embedding-3-small",
        base_url: Optional[str] = None,
        embedding_dim: int = 1536,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url or "https://api.openai.com/v1"
        self.embedding_dim = embedding_dim
        
        # 缓存
        self._cache: Dict[str, List[float]] = {}
        
        if not self.api_key:
            logger.warning("No API key provided for RealEmbedder, using placeholder")
    
    def embed(self, text: str) -> List[float]:
        """
        生成单个文本的嵌入
        
        Args:
            text: 输入文本
            
        Returns:
            嵌入向量
        """
        # 检查缓存
        cache_key = hash(text) % 1000000
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        if not self.api_key:
            # 回退到占位符
            return self._placeholder_embed(text)
        
        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": text,
                    "model": self.model,
                },
                timeout=30,
            )
            response.raise_for_status()
            
            data = response.json()
            embedding = data["data"][0]["embedding"]
            
            # 缓存
            self._cache[cache_key] = embedding
            
            return embedding
            
        except Exception as e:
            logger.error(f"Failed to get embedding: {e}")
            return self._placeholder_embed(text)
    
    def embed_query(self, query: str) -> List[float]:
        """嵌入查询"""
        return self.embed(query)
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        批量生成嵌入
        
        Args:
            texts: 文本列表
            
        Returns:
            嵌入向量列表
        """
        if not self.api_key:
            return [self._placeholder_embed(t) for t in texts]
        
        try:
            import requests
            
            response = requests.post(
                f"{self.base_url}/embeddings",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": texts,
                    "model": self.model,
                },
                timeout=60,
            )
            response.raise_for_status()
            
            data = response.json()
            embeddings = [item["embedding"] for item in data["data"]]
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Failed to batch embed: {e}")
            return [self._placeholder_embed(t) for t in texts]
    
    def _placeholder_embed(self, text: str) -> List[float]:
        """占位符嵌入（基于哈希）"""
        import hashlib
        
        # 使用文本哈希生成确定性向量
        hash_bytes = hashlib.md5(text.encode()).digest()
        
        # 扩展到目标维度
        vec = []
        for i in range(self.embedding_dim):
            # 使用哈希字节生成伪随机但确定性的值
            val = (hash_bytes[i % 16] / 255.0) * 2 - 1  # [-1, 1]
            vec.append(val)
        
        # 归一化
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec


# 兼容旧接口
class Embedder(RealEmbedder):
    """兼容旧接口的嵌入器"""
    pass