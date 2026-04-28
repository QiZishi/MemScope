"""
Reciprocal Rank Fusion (RRF) - 多源搜索结果融合

RRF(d) = Σ 1 / (k + rank_i(d))
where k is a constant (default 60) and rank_i is the rank in list i.

优点：处理不同搜索源之间的评分尺度不匹配问题
"""

from typing import List, Dict, Any


def rrf_fuse(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    normalize_length: bool = True,
) -> Dict[str, float]:
    """
    使用 RRF 算法融合多个排名列表
    
    Args:
        ranked_lists: 多个排名列表，每个列表包含 {id, score} 字典
        k: RRF 常数，默认 60
        normalize_length: 是否对列表长度归一化，防止长列表主导融合结果
        
    Returns:
        融合后的评分字典 {id: rrf_score}
    """
    scores: Dict[str, float] = {}
    
    for ranked_list in ranked_lists:
        # 长度归一化因子：每个列表贡献的总分归一化到相同水平
        # 防止候选多的搜索源（如 pattern search）过度主导融合
        list_len = len(ranked_list) if ranked_list else 1
        len_norm = 1.0
        if normalize_length and list_len > 0:
            # 使用 log 归一化，避免短列表被过度放大
            import math
            len_norm = 1.0 / math.log2(max(list_len, 2))
        
        for rank, item in enumerate(ranked_list):
            item_id = item.get("id", item.get("chunkId", ""))
            if not item_id:
                continue
            
            prev_score = scores.get(item_id, 0.0)
            # RRF 公式：1 / (k + rank + 1)，带长度归一化
            rrf_contribution = len_norm / (k + rank + 1)
            scores[item_id] = prev_score + rrf_contribution
    
    return scores


def rrf_fuse_with_weights(
    ranked_lists: List[List[Dict[str, Any]]],
    weights: List[float] = None,
    k: int = 60,
) -> Dict[str, float]:
    """
    带权重的 RRF 融合
    
    Args:
        ranked_lists: 多个排名列表
        weights: 各列表的权重（默认均等）
        k: RRF 常数
        
    Returns:
        融合后的评分字典
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")
    
    scores: Dict[str, float] = {}
    
    for ranked_list, weight in zip(ranked_lists, weights):
        for rank, item in enumerate(ranked_list):
            item_id = item.get("id", item.get("chunkId", ""))
            if not item_id:
                continue
            
            prev_score = scores.get(item_id, 0.0)
            rrf_contribution = weight * 1.0 / (k + rank + 1)
            scores[item_id] = prev_score + rrf_contribution
    
    return scores


def normalize_rrf_scores(scores: Dict[str, float]) -> Dict[str, float]:
    """
    将 RRF 评分归一化到 [0, 1] 范围
    
    Args:
        scores: RRF 评分字典
        
    Returns:
        归一化后的评分字典
    """
    if not scores:
        return scores
    
    max_score = max(scores.values())
    if max_score == 0:
        return scores
    
    return {id: score / max_score for id, score in scores.items()}