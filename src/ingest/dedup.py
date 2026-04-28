"""
Dedup - 智能去重

检测重复内容：
1. 向量相似度 > 0.95 → 重复
2. LLM 判断 DUPLICATE/UPDATE/NEW
"""

from typing import List, Dict, Any, Optional, Tuple
import logging
import numpy as np

logger = logging.getLogger(__name__)


class DedupEngine:
    """智能去重引擎"""
    
    def __init__(
        self,
        store: Any,
        embedder: Any,
        llm_caller: Any,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.store = store
        self.embedder = embedder
        self.llm_caller = llm_caller
        self.config = config or {}
        
        # 配置
        self.similarity_threshold = self.config.get("similarity_threshold", 0.95)
        self.top_k_similar = self.config.get("top_k_similar", 5)
    
    def check_duplicate(
        self,
        new_chunk: Dict[str, Any],
        owner: str = "default",
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """
        检查新块是否重复
        
        Args:
            new_chunk: 新块
            owner: 所有者
            
        Returns:
            (status, similar_chunk)
            status: DUPLICATE | UPDATE | NEW
        """
        content = new_chunk.get("content", "")
        
        if not content:
            return ("NEW", None)
        
        # 1. 向量相似度检测
        similar_chunks = self._find_similar_by_vector(content, owner)
        
        if not similar_chunks:
            return ("NEW", None)
        
        # 2. 检查最相似的
        most_similar = similar_chunks[0]
        similarity = most_similar.get("similarity", 0)
        
        if similarity > self.similarity_threshold:
            # 高度相似，可能是重复或更新
            logger.debug(f"High similarity {similarity:.2f} with chunk {most_similar.get('id')}")
            
            # 3. LLM 判断
            if self.llm_caller:
                status = self._llm_judge(content, most_similar)
                return (status, most_similar)
            else:
                # 没有 LLM，默认为重复
                return ("DUPLICATE", most_similar)
        
        return ("NEW", None)
    
    def _find_similar_by_vector(
        self,
        content: str,
        owner: str,
    ) -> List[Dict[str, Any]]:
        """通过向量相似度查找相似块"""
        if not self.embedder:
            return []
        
        try:
            # 生成新内容的嵌入
            new_embedding = self.embedder.embed(content)
            
            # 获取所有块的嵌入
            all_embeddings = self.store.get_all_embeddings(owner)
            
            if not all_embeddings:
                return []
            
            # 计算相似度
            similar = []
            
            for item in all_embeddings:
                chunk_id = item.get("id")
                embedding = item.get("embedding")
                
                if embedding:
                    similarity = self._cosine_similarity(new_embedding, embedding)
                    
                    if similarity > 0.5:  # 初步过滤
                        similar.append({
                            "id": chunk_id,
                            "similarity": similarity,
                            "content": item.get("content", ""),
                        })
            
            # 排序并返回 top_k
            similar.sort(key=lambda x: x["similarity"], reverse=True)
            return similar[:self.top_k_similar]
            
        except Exception as e:
            logger.warning(f"Vector similarity check failed: {e}")
            return []
    
    def _cosine_similarity(
        self,
        vec_a: List[float],
        vec_b: List[float],
    ) -> float:
        """计算余弦相似度"""
        a = np.array(vec_a)
        b = np.array(vec_b)
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return float(dot_product / (norm_a * norm_b))
    
    async def _llm_judge(
        self,
        new_content: str,
        similar_chunk: Dict[str, Any],
    ) -> str:
        """LLM 判断是否重复或更新"""
        prompt = f'''Compare two pieces of content and determine their relationship.

New content:
{new_content[:500]}

Existing content:
{similar_chunk.get("content", "")[:500]}

Answer with ONE word:
- DUPLICATE (same information, no need to store again)
- UPDATE (new information supplements or corrects the existing content)
- NEW (different topic or content)

Output ONLY the word, no explanation.
'''
        
        try:
            response = await self.llm_caller.call(prompt)
            
            # 解析响应
            response = response.strip().upper()
            
            if response in ["DUPLICATE", "UPDATE", "NEW"]:
                return response
            
        except Exception as e:
            logger.warning(f"LLM dedup judgment failed: {e}")
        
        # 默认为 NEW
        return "NEW"
    
    async def process_chunk(
        self,
        new_chunk: Dict[str, Any],
        owner: str = "default",
    ) -> Dict[str, Any]:
        """
        处理新块，根据去重结果决定存储方式
        
        Args:
            new_chunk: 新块
            owner: 所有者
            
        Returns:
            处理后的块
        """
        status, similar_chunk = self.check_duplicate(new_chunk, owner)
        
        if status == "DUPLICATE":
            logger.info(f"Chunk duplicated with {similar_chunk.get('id')}, skip")
            return None
        
        if status == "UPDATE":
            # 合并内容
            logger.info(f"Chunk updates {similar_chunk.get('id')}")
            
            # 合并摘要
            old_summary = similar_chunk.get("summary", "")
            new_summary = new_chunk.get("summary", "")
            
            merged_summary = await self._merge_summaries(old_summary, new_summary)
            new_chunk["summary"] = merged_summary
            
            # 记录合并历史
            merge_history = similar_chunk.get("merge_history", [])
            merge_history.append({
                "chunk_id": new_chunk.get("id"),
                "timestamp": new_chunk.get("createdAt"),
            })
            new_chunk["merge_history"] = merge_history
            new_chunk["merge_count"] = len(merge_history)
            
            # 更新原块
            self.store.update_chunk(similar_chunk.get("id"), {
                "summary": merged_summary,
                "merge_history": merge_history,
                "merge_count": len(merge_history),
            })
            
            return new_chunk
        
        # NEW - 正常存储
        return new_chunk
    
    async def _merge_summaries(
        self,
        old_summary: str,
        new_summary: str,
    ) -> str:
        """合并摘要"""
        if not old_summary:
            return new_summary
        if not new_summary:
            return old_summary
        
        if self.llm_caller:
            prompt = f'''Merge two summaries into one concise summary.

Old summary: {old_summary}
New summary: {new_summary}

Output the merged summary (max 200 words).
'''
            
            try:
                merged = await self.llm_caller.call(prompt)
                return merged.strip()
            except:
                pass
        
        # 简单拼接
        return f"{old_summary}\n{new_summary}"