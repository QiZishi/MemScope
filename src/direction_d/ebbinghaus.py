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

    def next_review_interval(self, review_count: int, category: str = 'general') -> float:
        """计算下次复习间隔（小时）
        基于 SM-2 算法简化版：
        - 第1次: 1天
        - 第2次: 3天
        - 第3次: 7天
        - 第n次: 基础间隔 * 2^(n-1)
        """
        base_interval_hours = 24  # 1天
        interval = base_interval_hours * (2 ** min(review_count, 6))
        # 根据知识类型调整
        lam = self.lambda_map.get(category, 0.01)
        type_factor = 0.01 / lam  # 衰减越慢，复习间隔越长
        return interval * type_factor

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
