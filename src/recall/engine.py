"""
Recall Engine - 完整的混合搜索引擎

整合：
- FTS 全文搜索
- 向量搜索
- Pattern 搜索（短词/CJK）
- RRF 融合
- MMR 重排
- 时间衰减
"""

from typing import List, Dict, Any, Optional
from .rrf import rrf_fuse, normalize_rrf_scores
from .mmr import mmr_rerank, cosine_similarity
from .recency import apply_recency_decay
import logging

logger = logging.getLogger(__name__)


class RecallEngine:
    """完整的混合召回引擎"""
    
    def __init__(
        self,
        store: Any,  # SqliteStore
        embedder: Any,  # Embedder
        config: Optional[Dict[str, Any]] = None,
    ):
        self.store = store
        self.embedder = embedder
        self.config = config or {}
        
        # 默认配置
        self.rrf_k = self.config.get("rrf_k", 60)
        self.mmr_lambda = self.config.get("mmr_lambda", 0.7)
        self.recency_half_life = self.config.get("recency_half_life_days", 14)
        self.max_results_default = self.config.get("max_results_default", 10)
        self.max_results_max = self.config.get("max_results_max", 20)
        self.min_score_default = self.config.get("min_score_default", 0.45)
    
    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        min_score: Optional[float] = None,
        role: Optional[str] = None,
        scope: str = "private",
        agent_id: str = "default",
    ) -> Dict[str, Any]:
        """
        执行混合搜索
        
        Args:
            query: 搜索查询
            max_results: 最大结果数
            min_score: 最小分数阈值
            role: 角色过滤
            scope: 搜索范围 (private/shared/all)
            agent_id: Agent ID
            
        Returns:
            搜索结果 {hits: [...], meta: {...}}
        """
        max_results = max_results or self.max_results_default
        max_results = min(max_results, self.max_results_max)
        min_score = min_score or self.min_score_default
        
        candidate_pool = max_results * 5  # 候选池大小
        
        # Step 1: 多源搜索
        all_ranked_lists = []
        
        # 1a: FTS 搜索
        fts_candidates = []
        if query:
            try:
                fts_candidates = self._fts_search(query, candidate_pool, scope, agent_id)
                fts_ranked = [{"id": c.get("id"), "score": c.get("score", 0)} 
                             for c in fts_candidates]
                if fts_ranked:
                    all_ranked_lists.append(fts_ranked)
                    logger.debug(f"FTS found {len(fts_ranked)} candidates")
            except Exception as e:
                logger.warning(f"FTS search failed: {e}")
        
        # 1b: 向量搜索
        vec_candidates = []
        if query and self.embedder:
            try:
                query_vec = self.embedder.embed_query(query)
                vec_candidates = self._vector_search(query_vec, candidate_pool, scope, agent_id)
                vec_ranked = [{"id": c.get("id"), "score": c.get("score", 0)} 
                             for c in vec_candidates]
                if vec_ranked:
                    all_ranked_lists.append(vec_ranked)
                    logger.debug(f"Vector search found {len(vec_ranked)} candidates")
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")
        
        # 1c: Pattern 搜索（短词/CJK）
        pattern_candidates = []
        if query:
            try:
                pattern_candidates = self._pattern_search(query, candidate_pool, scope, agent_id)
                pattern_ranked = [{"id": c.get("id"), "score": c.get("score", 0)} 
                                 for c in pattern_candidates]
                if pattern_ranked:
                    all_ranked_lists.append(pattern_ranked)
                    logger.debug(f"Pattern search found {len(pattern_ranked)} candidates")
            except Exception as e:
                logger.warning(f"Pattern search failed: {e}")
        
        # 如果没有候选，直接返回
        if not all_ranked_lists or not any(all_ranked_lists):
            return {
                "hits": [],
                "meta": {
                    "usedMinScore": min_score,
                    "usedMaxResults": max_results,
                    "totalCandidates": 0,
                    "note": "No candidates found for the given query.",
                },
            }
        
        # Step 2: RRF 融合
        rrf_scores = rrf_fuse(all_ranked_lists, k=self.rrf_k)
        
        # Step 3: 转换为列表并排序
        rrf_list = [
            {"id": id, "score": score}
            for id, score in rrf_scores.items()
        ]
        rrf_list.sort(key=lambda x: x["score"], reverse=True)
        
        # Step 4: MMR 重排
        embeddings = {}
        if self.embedder:
            try:
                query_vec = self.embedder.embed_query(query) if query else None
                for item in rrf_list[:candidate_pool]:
                    chunk_id = item["id"]
                    vec = self.store.get_embedding(chunk_id)
                    if vec:
                        embeddings[chunk_id] = vec
                
                mmr_results = mmr_rerank(
                    rrf_list[:candidate_pool],
                    embeddings,
                    query_vec,
                    lambda_param=self.mmr_lambda,
                    top_k=max_results * 2,
                )
            except Exception as e:
                logger.warning(f"MMR rerank failed: {e}, using RRF only")
                mmr_results = rrf_list[:max_results * 2]
        else:
            mmr_results = rrf_list[:max_results * 2]
        
        # Step 5: 时间衰减
        with_ts = []
        for item in mmr_results:
            chunk = self.store.get_chunk(item["id"])
            if chunk:
                item["createdAt"] = chunk.get("createdAt", 0)
                with_ts.append(item)
        
        decayed = apply_recency_decay(with_ts, half_life_days=self.recency_half_life)
        
        # Step 6: 过滤和归一化
        sorted_results = sorted(decayed, key=lambda x: x["score"], reverse=True)
        
        if not sorted_results:
            return {
                "hits": [],
                "meta": {
                    "usedMinScore": min_score,
                    "usedMaxResults": max_results,
                    "totalCandidates": len(rrf_scores),
                },
            }
        
        top_score = sorted_results[0]["score"]
        absolute_floor = top_score * min_score * 0.3
        
        # 角色过滤
        filtered = []
        for item in sorted_results:
            if len(filtered) >= max_results:
                break
            
            chunk = self.store.get_chunk(item["id"])
            if not chunk:
                continue
            
            # 角色过滤
            if role and chunk.get("role") != role:
                continue
            
            # 分数过滤
            if item["score"] < absolute_floor:
                continue
            
            filtered.append((item, chunk))
        
        # 归一化分数
        display_max = filtered[0][0]["score"] if filtered else 1
        
        # Step 7: 构建 hits
        hits = []
        for item, chunk in filtered:
            normalized_score = item["score"] / display_max if display_max > 0 else 0
            
            hit = {
                "chunkId": chunk.get("id"),
                "score": round(normalized_score, 3),
                "summary": chunk.get("summary", ""),
                "original_excerpt": self._make_excerpt(chunk.get("content", "")),
                "role": chunk.get("role", ""),
                "visibility": chunk.get("visibility", "private"),
                "owner": chunk.get("owner", ""),
                "source": {
                    "ts": chunk.get("createdAt"),
                    "role": chunk.get("role", "assistant"),
                },
            }
            hits.append(hit)
        
        return {
            "hits": hits,
            "meta": {
                "usedMinScore": min_score,
                "usedMaxResults": max_results,
                "totalCandidates": len(rrf_scores),
            },
        }
    
    def _fts_search(
        self,
        query: str,
        limit: int,
        scope: str,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """FTS 全文搜索"""
        return self.store.fts_search(query, limit, scope, agent_id)
    
    def _vector_search(
        self,
        query_vec: List[float],
        limit: int,
        scope: str,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """向量搜索"""
        return self.store.vector_search(query_vec, limit, scope, agent_id)
    
    def _pattern_search(
        self,
        query: str,
        limit: int,
        scope: str,
        agent_id: str,
    ) -> List[Dict[str, Any]]:
        """Pattern 搜索（短词/CJK）"""
        # 提取短词和 CJK bigrams
        import re
        cleaned = re.sub(r'[."""(){}[\]*:^~!@#$%&\\/<>,;\'`?？。，！、：""''（）【】《》]', ' ', query)
        space_split = [t for t in cleaned.split() if len(t) == 2]
        
        # CJK bigrams
        cjk_runs = re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf\uF900-\uFAFF]{2,}', cleaned)
        cjk_bigrams = []
        for run in cjk_runs:
            for i in range(len(run) - 1):
                cjk_bigrams.append(run[i:i+2])
        
        short_terms = list(set(space_split + cjk_bigrams))
        
        if not short_terms:
            return []
        
        return self.store.pattern_search(short_terms, limit, scope, agent_id)
    
    def _make_excerpt(self, content: str, max_len: int = 500) -> str:
        """生成摘要片段"""
        if len(content) <= max_len:
            return content
        return content[:max_len] + "..."