"""
Maximal Marginal Relevance (MMR) - 多样性重排

MMR = λ · sim(q, d) - (1-λ) · max(sim(d, d_selected))

目标：平衡相关性（sim(q,d)）和多样性（避免结果过于相似）
"""

from typing import List, Dict, Any, Optional
import numpy as np


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """
    计算两个向量的余弦相似度
    
    Args:
        vec_a: 向量 A
        vec_b: 向量 B
        
    Returns:
        余弦相似度 [-1, 1]
    """
    if not vec_a or not vec_b:
        return 0.0
    
    # 转换为 numpy 数组
    a = np.array(vec_a)
    b = np.array(vec_b)
    
    # 计算余弦相似度
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(dot_product / (norm_a * norm_b))


def mmr_rerank(
    candidates: List[Dict[str, Any]],
    embeddings: Dict[str, List[float]],
    query_embedding: Optional[List[float]] = None,
    lambda_param: float = 0.7,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """
    MMR 多样性重排
    
    Args:
        candidates: 候选列表 [{id, score, ...}]
        embeddings: 嵌入向量字典 {id: embedding}
        query_embedding: 查询向量（可选，用于相关性计算）
        lambda_param: 相关性权重（0.7 = 相关性更重要）
        top_k: 返回的结果数量
        
    Returns:
        重排后的候选列表
    """
    if len(candidates) <= 1:
        return candidates
    
    selected: List[Dict[str, Any]] = []
    remaining = list(candidates)
    
    while len(selected) < top_k and remaining:
        best_idx = 0
        best_mmr = -float('inf')
        
        for i, candidate in enumerate(remaining):
            cand_id = candidate.get("id", candidate.get("chunkId", ""))
            cand_vec = embeddings.get(cand_id)
            cand_score = candidate.get("score", 0.0)
            
            # 计算与查询的相关性（如果没有 query_embedding，使用原始分数）
            relevance_score = cand_score
            if query_embedding and cand_vec:
                relevance_score = cosine_similarity(query_embedding, cand_vec)
            
            # 计算与已选结果的最大相似度
            max_sim_to_selected = 0.0
            if cand_vec and selected:
                for s in selected:
                    s_id = s.get("id", s.get("chunkId", ""))
                    s_vec = embeddings.get(s_id)
                    if s_vec:
                        sim = cosine_similarity(cand_vec, s_vec)
                        max_sim_to_selected = max(max_sim_to_selected, sim)
            
            # MMR 公式
            mmr_score = lambda_param * relevance_score - (1 - lambda_param) * max_sim_to_selected
            
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = i
        
        # 选择最佳候选并移除
        chosen = remaining.pop(best_idx)
        # 保留原始分数，不修改
        selected.append(chosen)
    
    return selected


def mmr_rerank_with_diversity_threshold(
    candidates: List[Dict[str, Any]],
    embeddings: Dict[str, List[float]],
    min_diversity: float = 0.3,
    lambda_param: float = 0.7,
    top_k: int = 20,
) -> List[Dict[str, Any]]:
    """
    带多样性阈值的 MMR 重排
    
    Args:
        candidates: 候选列表
        embeddings: 嵌入向量字典
        min_diversity: 最小多样性阈值（结果之间的最小相似度上限）
        lambda_param: 相关性权重
        top_k: 返回结果数量
        
    Returns:
        重排后的候选列表
    """
    if len(candidates) <= 1:
        return candidates
    
    selected: List[Dict[str, Any]] = []
    remaining = list(candidates)
    
    # 第一个选择相关性最高的
    remaining.sort(key=lambda x: x.get("score", 0), reverse=True)
    selected.append(remaining.pop(0))
    
    while len(selected) < top_k and remaining:
        best_idx = 0
        best_mmr = -float('inf')
        
        for i, candidate in enumerate(remaining):
            cand_id = candidate.get("id", candidate.get("chunkId", ""))
            cand_vec = embeddings.get(cand_id)
            cand_score = candidate.get("score", 0.0)
            
            # 计算与已选结果的相似度
            max_sim_to_selected = 0.0
            if cand_vec:
                for s in selected:
                    s_id = s.get("id", s.get("chunkId", ""))
                    s_vec = embeddings.get(s_id)
                    if s_vec:
                        sim = cosine_similarity(cand_vec, s_vec)
                        max_sim_to_selected = max(max_sim_to_selected, sim)
            
            # 如果与已选结果太相似，跳过
            if max_sim_to_selected > (1 - min_diversity):
                continue
            
            # MMR 计算
            mmr_score = lambda_param * cand_score - (1 - lambda_param) * max_sim_to_selected
            
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_idx = i
        
        if best_mmr == -float('inf'):
            # 所有候选都被跳过，选择分数最高的
            remaining.sort(key=lambda x: x.get("score", 0), reverse=True)
            if remaining:
                selected.append(remaining.pop(0))
            else:
                break
        else:
            chosen = remaining.pop(best_idx)
            selected.append(chosen)
    
    return selected