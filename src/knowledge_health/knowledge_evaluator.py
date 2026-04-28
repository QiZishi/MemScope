"""
知识评估器
基于 EbbinghausModel 封装评估逻辑，提供知识重要性、单点风险和综合健康评估。
"""

import math
from typing import Any, Dict, List, Optional

from .ebbinghaus import EbbinghausModel


class KnowledgeEvaluator:
    """知识评估器：封装重要性评分、单点风险和综合健康评估。"""

    def __init__(self, ebbinghaus_model: EbbinghausModel) -> None:
        """初始化评估器。

        Args:
            ebbinghaus_model: 已配置的 EbbinghausModel 实例，用于底层计算。
        """
        self.model: EbbinghausModel = ebbinghaus_model

    # ------------------------------------------------------------------
    # 委托方法：直接转发到 EbbinghausModel
    # ------------------------------------------------------------------

    def evaluate_importance(
        self,
        access_count: int,
        content_depth: float,
        time_sensitivity: float,
        team_coverage: float,
        error_cost: float,
    ) -> float:
        """评估知识重要性（五维加权）。

        委托给 EbbinghausModel.importance_score。

        Args:
            access_count:      访问/引用次数
            content_depth:     内容深度 [0, 1]
            time_sensitivity:  时间敏感度 [0, 1]
            team_coverage:     团队覆盖率 [0, 1]（越高说明越多人掌握）
            error_cost:        出错代价 [0, 1]

        Returns:
            重要性分数 [0, 1]
        """
        return self.model.importance_score(
            access_count=access_count,
            content_depth=content_depth,
            time_sensitivity=time_sensitivity,
            team_coverage=team_coverage,
            error_cost=error_cost,
        )

    def evaluate_single_point_risk(
        self, importance: float, holder_count: int
    ) -> float:
        """评估单点风险。

        委托给 EbbinghausModel.single_point_risk。

        Args:
            importance:    知识重要性 [0, 1]
            holder_count:  掌握该知识的人数

        Returns:
            单点风险值 [0, 1]（1.0 = 最高风险）
        """
        return self.model.single_point_risk(
            importance=importance, holder_count=holder_count
        )

    # ------------------------------------------------------------------
    # 综合健康评估
    # ------------------------------------------------------------------

    def evaluate_knowledge_health(
        self,
        store: Any,
        team_id: str,
        topic: str,
    ) -> Dict[str, Any]:
        """计算某个团队/主题的综合知识健康指标。

        假设 *store* 提供以下接口（duck typing）：
            store.get_knowledge_items(team_id, topic) -> List[dict]
        每条 item 至少包含以下字段：
            - id: str
            - category: str              (如 'api_doc', 'architecture', …)
            - last_access_days: float    (距今天数)
            - access_count: int
            - content_depth: float
            - time_sensitivity: float
            - team_coverage: float
            - error_cost: float
            - holder_count: int

        Args:
            store:    知识存储对象（duck-typed）
            team_id:  团队标识
            topic:    主题/领域

        Returns:
            包含以下键的字典：
            - topic: str
            - team_id: str
            - item_count: int                   知识条目总数
            - avg_retention: float              平均记忆保持率
            - avg_importance: float             平均重要性
            - avg_single_point_risk: float      平均单点风险
            - health_score: float               综合健康分 [0, 1]（越高越健康）
            - risk_items: List[dict]            高风险条目（health 分 < 0.4）
            - freshness_distribution: dict      各新鲜度状态的条目数量
        """
        items: List[Dict[str, Any]] = store.get_knowledge_items(team_id, topic)

        if not items:
            return {
                "topic": topic,
                "team_id": team_id,
                "item_count": 0,
                "avg_retention": 0.0,
                "avg_importance": 0.0,
                "avg_single_point_risk": 0.0,
                "health_score": 0.0,
                "risk_items": [],
                "freshness_distribution": {
                    "fresh": 0,
                    "aging": 0,
                    "stale": 0,
                    "forgotten": 0,
                },
            }

        total_retention = 0.0
        total_importance = 0.0
        total_risk = 0.0
        risk_items: List[Dict[str, Any]] = []
        freshness_dist: Dict[str, int] = {
            "fresh": 0,
            "aging": 0,
            "stale": 0,
            "forgotten": 0,
        }

        for item in items:
            category: str = item.get("category", "general")
            days: float = item.get("last_access_days", 0.0)
            access_count: int = item.get("access_count", 0)
            content_depth: float = item.get("content_depth", 0.5)
            time_sensitivity: float = item.get("time_sensitivity", 0.5)
            team_coverage: float = item.get("team_coverage", 0.5)
            error_cost: float = item.get("error_cost", 0.5)
            holder_count: int = item.get("holder_count", 1)

            # 记忆保持率
            retention = self.model.retention_score(days, category)
            total_retention += retention

            # 重要性
            importance = self.evaluate_importance(
                access_count=access_count,
                content_depth=content_depth,
                time_sensitivity=time_sensitivity,
                team_coverage=team_coverage,
                error_cost=error_cost,
            )
            total_importance += importance

            # 单点风险
            risk = self.evaluate_single_point_risk(importance, holder_count)
            total_risk += risk

            # 新鲜度分布
            freshness = self.model.freshness_status(days, category)
            freshness_dist[freshness] = freshness_dist.get(freshness, 0) + 1

            # 条目级健康分：保持率 * (1 - 单点风险)
            item_health = retention * (1.0 - risk)
            if item_health < 0.4:
                risk_items.append(
                    {
                        "id": item.get("id", "unknown"),
                        "category": category,
                        "retention": round(retention, 4),
                        "importance": round(importance, 4),
                        "single_point_risk": round(risk, 4),
                        "health": round(item_health, 4),
                        "days_since_access": days,
                        "holder_count": holder_count,
                    }
                )

        n = len(items)
        avg_retention = total_retention / n
        avg_importance = total_importance / n
        avg_risk = total_risk / n

        # 综合健康分：保留率 × 覆盖安全 × 重要性平衡
        health_score = avg_retention * (1.0 - avg_risk) * (0.5 + 0.5 * avg_importance)
        health_score = min(1.0, max(0.0, health_score))

        return {
            "topic": topic,
            "team_id": team_id,
            "item_count": n,
            "avg_retention": round(avg_retention, 4),
            "avg_importance": round(avg_importance, 4),
            "avg_single_point_risk": round(avg_risk, 4),
            "health_score": round(health_score, 4),
            "risk_items": sorted(risk_items, key=lambda x: x["health"]),
            "freshness_distribution": freshness_dist,
        }
