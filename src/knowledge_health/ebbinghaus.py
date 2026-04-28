"""
艾宾浩斯遗忘曲线模型
支持按知识类型调参的遗忘建模
"""
import math
import time
from typing import Dict, Optional


class EbbinghausModel:
    """艾宾浩斯遗忘曲线: R = e^(-t/S)"""

    # 不同知识类型的衰减参数
    DEFAULT_LAMBDA: Dict[str, float] = {
        'api_doc': 0.02,        # API文档衰减快 (半衰期 ~35天)
        'architecture': 0.005,   # 架构决策衰减慢 (半衰期 ~139天)
        'process': 0.01,         # 流程规范中等 (半衰期 ~69天)
        'client': 0.015,         # 客户信息中等偏快
        'competitor': 0.02,      # 竞品信息衰减快
        'codebase': 0.008,       # 代码库知识衰减较慢
        'security': 0.003,       # 安全知识几乎不衰减
        'general': 0.01,         # 通用默认
    }

    # 不同知识类型的有效期(天)
    VALIDITY_DAYS: Dict[str, int] = {
        'api_doc': 30,
        'architecture': 180,
        'process': 90,
        'client': 60,
        'competitor': 30,
        'codebase': 120,
        'security': 365,
        'general': 60,
    }

    def __init__(self, custom_lambda: Optional[Dict[str, float]] = None) -> None:
        self.lambda_map: Dict[str, float] = {**self.DEFAULT_LAMBDA}
        if custom_lambda:
            self.lambda_map.update(custom_lambda)

    def retention_score(self, days_since_access: float, category: str = 'general') -> float:
        """计算记忆保持率 R = e^(-t/S)"""
        lam = self.lambda_map.get(category, 0.01)
        return math.exp(-lam * days_since_access)

    def retention_score_with_reinforcement(
        self,
        days_since_access: float,
        category: str = 'general',
        access_count: int = 1,
        quality: int = 3,
    ) -> float:
        """
        带强化学习的记忆保持率。
        
        Enhancement: 多次访问和高质量回忆会减缓遗忘速度。
        每次高质量回忆将等效衰减系数降低，模拟记忆巩固效应。
        
        Args:
            days_since_access: 距上次访问的天数
            category: 知识类别
            access_count: 访问次数
            quality: 最近回忆质量 0-5
            
        Returns:
            记忆保持率 [0, 1]
        """
        lam = self.lambda_map.get(category, 0.01)
        
        # 强化因子: 多次高质量回忆减缓遗忘
        # access_count 贡献: log scale, 每次回忆效果递减
        access_factor = 1.0 / (1.0 + 0.15 * math.log1p(access_count))
        
        # quality 贡献: 高质量回忆(4-5)显著减缓遗忘
        quality_factor = 1.0 - (quality / 5.0) * 0.3  # q=5 -> 0.7x, q=0 -> 1.0x
        
        effective_lam = lam * access_factor * quality_factor
        return math.exp(-effective_lam * days_since_access)

    def freshness_status(self, days_since_access: float, category: str = 'general') -> str:
        """判断新鲜度状态: fresh / aging / stale / forgotten"""
        validity = self.VALIDITY_DAYS.get(category, 60)
        if days_since_access <= validity:
            return 'fresh'
        elif days_since_access <= validity * 2:
            return 'aging'
        elif days_since_access <= validity * 4:
            return 'stale'
        else:
            return 'forgotten'

    def next_review_interval(self, review_count: int, category: str = 'general', quality: int = 3) -> float:
        """计算下次复习间隔（小时）
        基于增强版 SM-2 算法：
        - quality: 回忆质量 0-5（0=完全忘记, 5=完美回忆）
        - 第1次: 1天
        - 第2次: 3天
        - 第3次: 7天
        - 后续基于 easiness factor 动态调整
        
        Enhancement: 引入 easiness factor (EF) 动态调整，
        高质量回忆增加间隔，低质量回忆缩短间隔。
        """
        # SM-2 easiness factor 计算
        quality = max(0, min(5, quality))
        # EF 公式: EF' = EF + (0.1 - (5-q) * (0.08 + (5-q) * 0.02))
        # 从 EF=2.5 开始
        ef = 2.5
        for _ in range(max(0, review_count)):
            ef_delta = 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)
            ef = max(1.3, ef + ef_delta)  # EF 最低 1.3
        
        base_interval_hours = 24  # 1天
        if review_count <= 0:
            interval = base_interval_hours
        elif review_count == 1:
            interval = base_interval_hours * 3  # 3天
        elif review_count == 2:
            interval = base_interval_hours * 7  # 7天
        else:
            # SM-2: interval = interval_prev * EF
            interval = base_interval_hours * 7 * (ef ** (review_count - 2))
        
        # 根据知识类型调整
        lam = self.lambda_map.get(category, 0.01)
        type_factor = 0.01 / lam  # 衰减越慢，复习间隔越长
        interval *= type_factor
        
        # 质量过低时缩短间隔
        if quality < 3:
            interval *= (quality + 1) / 4.0  # q=0 -> 0.25x, q=2 -> 0.75x
        
        return interval

    def importance_score(
        self,
        access_count: int,
        content_depth: float,
        time_sensitivity: float,
        team_coverage: float,
        error_cost: float,
    ) -> float:
        """5维加权知识重要性评估"""
        w1, w2, w3, w4, w5 = 0.2, 0.2, 0.15, 0.25, 0.2
        # Normalize access_count to [0,1] using log scale
        norm_access = min(1.0, math.log1p(access_count) / 5.0)
        score = (
            w1 * norm_access
            + w2 * content_depth
            + w3 * time_sensitivity
            + w4 * (1.0 - team_coverage)
            + w5 * error_cost
        )
        return min(1.0, max(0.0, score))

    def single_point_risk(self, importance: float, holder_count: int) -> float:
        """单点风险评估: risk = importance / holder_count"""
        if holder_count <= 0:
            return 1.0
        return min(1.0, importance / holder_count)
