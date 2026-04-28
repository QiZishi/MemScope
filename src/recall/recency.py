"""
Time Decay Scoring - 时间衰减评分

decay(t) = 0.5 ^ (age_days / half_life)
final = base_score * (alpha + (1-alpha) * decay)

目标：偏向最近的记忆，但保留高相关性的旧记忆
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import math


def apply_recency_decay(
    candidates: List[Dict[str, Any]],
    half_life_days: float = 14.0,
    alpha: float = 0.3,
    now: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    应用时间衰减评分
    
    Args:
        candidates: 候选列表 [{id, score, createdAt, ...}]
        half_life_days: 半衰期（天数），默认 14 天
        alpha: 基础分数保留比例（0.3 = 保留 30%）
        now: 当前时间戳（可选，默认使用当前时间）
        
    Returns:
        应用衰减后的候选列表
    """
    if not candidates:
        return candidates
    
    current_time = now or int(datetime.now().timestamp() * 1000)
    half_life_ms = half_life_days * 24 * 60 * 60 * 1000
    
    results = []
    for candidate in candidates:
        # 获取创建时间
        created_at = candidate.get("createdAt", current_time)
        if isinstance(created_at, str):
            # 尝试解析字符串时间
            try:
                created_at = int(datetime.fromisoformat(created_at).timestamp() * 1000)
            except:
                created_at = current_time
        
        # 计算年龄（毫秒）
        age_ms = max(0, current_time - created_at)
        
        # 计算衰减因子
        decay = math.pow(0.5, age_ms / half_life_ms)
        
        # 应用衰减公式
        base_score = candidate.get("score", 0.0)
        adjusted_score = base_score * (alpha + (1 - alpha) * decay)
        
        # 创建新的候选对象
        result = candidate.copy()
        result["score"] = adjusted_score
        result["decay_factor"] = decay
        results.append(result)
    
    return results


def apply_recency_decay_with_boost(
    candidates: List[Dict[str, Any]],
    half_life_days: float = 14.0,
    alpha: float = 0.3,
    recent_boost_days: float = 1.0,
    recent_boost_factor: float = 1.5,
    now: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    带近期加权的衰减评分
    
    Args:
        candidates: 候选列表
        half_life_days: 半衰期
        alpha: 基础保留比例
        recent_boost_days: 近期加权天数阈值
        recent_boost_factor: 近期加权系数
        now: 当前时间
        
    Returns:
        衰减后的候选列表
    """
    if not candidates:
        return candidates
    
    current_time = now or int(datetime.now().timestamp() * 1000)
    half_life_ms = half_life_days * 24 * 60 * 60 * 1000
    recent_threshold_ms = recent_boost_days * 24 * 60 * 60 * 1000
    
    results = []
    for candidate in candidates:
        created_at = candidate.get("createdAt", current_time)
        if isinstance(created_at, str):
            try:
                created_at = int(datetime.fromisoformat(created_at).timestamp() * 1000)
            except:
                created_at = current_time
        
        age_ms = max(0, current_time - created_at)
        
        # 基础衰减
        decay = math.pow(0.5, age_ms / half_life_ms)
        base_score = candidate.get("score", 0.0)
        adjusted_score = base_score * (alpha + (1 - alpha) * decay)
        
        # 近期加权
        if age_ms < recent_threshold_ms:
            adjusted_score *= recent_boost_factor
        
        result = candidate.copy()
        result["score"] = adjusted_score
        result["decay_factor"] = decay
        results.append(result)
    
    return results


def get_decay_factor(
    created_at: int,
    half_life_days: float = 14.0,
    now: Optional[int] = None,
) -> float:
    """
    计算单个候选的衰减因子
    
    Args:
        created_at: 创建时间戳（毫秒）
        half_life_days: 半衰期
        now: 当前时间
        
    Returns:
        衰减因子 [0, 1]
    """
    current_time = now or int(datetime.now().timestamp() * 1000)
    half_life_ms = half_life_days * 24 * 60 * 60 * 1000
    age_ms = max(0, current_time - created_at)
    return math.pow(0.5, age_ms / half_life_ms)