"""
知识新鲜度监控器
基于艾宾浩斯遗忘曲线的知识健康追踪
"""
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from .ebbinghaus import EbbinghausModel

logger = logging.getLogger(__name__)


class FreshnessMonitor:
    """知识新鲜度监控器，利用 EbbinghausModel 追踪和管理知识健康状态。"""

    def __init__(self, store: Any) -> None:
        self.store = store
        self.model = EbbinghausModel()

    # ------------------------------------------------------------------
    # 注册
    # ------------------------------------------------------------------

    def register_knowledge(
        self,
        chunk_id: str,
        team_id: str,
        category: str = 'general',
        importance: Optional[float] = None,
        holders: Optional[List[str]] = None,
    ) -> str:
        """注册知识条目到健康监控。

        Returns:
            knowledge_health 记录 id，失败返回空字符串
        """
        try:
            # 计算初始重要性（如果未提供）
            if importance is None:
                holder_count = len(holders) if holders else 1
                importance = self.model.importance_score(
                    access_count=1,
                    content_depth=0.5,
                    time_sensitivity=0.5,
                    team_coverage=max(0.0, 1.0 - 1.0 / max(holder_count, 1)),
                    error_cost=0.5,
                )

            # 构建 metadata
            metadata = json.dumps({
                'category': category,
                'chunk_id': chunk_id,
                'holders': holders or [],
                'holder_count': len(holders) if holders else 1,
                'importance': importance,
            })

            # 创建 knowledge_health 记录
            kh_id = self.store.upsert_knowledge_health(
                owner=team_id,
                topic=chunk_id,
                source='auto_register',
                freshness_score=1.0,
                accuracy_score=1.0,
                completeness_score=1.0,
                metadata=metadata,
            )

            if not kh_id:
                return ''

            # 创建 forgetting_schedule
            review_interval_days = self.model.next_review_interval(
                review_count=0, category=category
            ) / 24.0  # 转换为天
            self.store.insert_forgetting_schedule(
                owner=team_id,
                chunk_id=chunk_id,
                topic=chunk_id,
                interval_days=max(1.0, review_interval_days),
                ease_factor=2.5,
            )

            return kh_id
        except Exception as e:
            logger.error(f"register_knowledge failed: {e}")
            return ''

    # ------------------------------------------------------------------
    # 新鲜度检查
    # ------------------------------------------------------------------

    def check_freshness(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """检查所有知识的新鲜度状态。

        Returns:
            状态发生变化（freshness 下降）的条目列表
        """
        changed: List[Dict[str, Any]] = []
        try:
            now_ms = int(time.time() * 1000)
            owner = team_id or 'local'
            records = self.store.list_knowledge_health(owner)

            for rec in records:
                topic = rec.get('topic', '')
                metadata = self._parse_metadata(rec.get('metadata'))
                category = metadata.get('category', 'general')
                last_verified = rec.get('last_verified_at') or rec.get('createdAt', now_ms)
                days_since = (now_ms - last_verified) / 86400000.0

                new_freshness = self.model.retention_score(days_since, category)
                new_status = self.model.freshness_status(days_since, category)
                old_freshness = rec.get('freshness_score', 1.0)

                if new_freshness < old_freshness - 0.01:
                    self.store.update_freshness(owner, topic, new_freshness)
                    changed.append({
                        'id': rec.get('id'),
                        'topic': topic,
                        'category': category,
                        'old_freshness': old_freshness,
                        'new_freshness': round(new_freshness, 4),
                        'status': new_status,
                        'days_since_access': round(days_since, 1),
                    })
        except Exception as e:
            logger.error(f"check_freshness failed: {e}")

        return changed

    # ------------------------------------------------------------------
    # 记录访问
    # ------------------------------------------------------------------

    def record_access(self, knowledge_id: str, owner: str = 'local') -> Dict[str, Any]:
        """Record knowledge being accessed, reset freshness.

        Returns:
            操作结果摘要
        """
        try:
            now_ms = int(time.time() * 1000)

            # 查找对应记录
            records = self.store.list_knowledge_health(owner)
            target = None
            for rec in records:
                if rec.get('id') == knowledge_id or rec.get('topic') == knowledge_id:
                    target = rec
                    break

            if not target:
                return {'success': False, 'error': f'knowledge {knowledge_id} not found'}

            topic = target.get('topic', '')
            metadata = self._parse_metadata(target.get('metadata'))
            category = metadata.get('category', 'general')

            # 重置 freshness_score
            self.store.update_freshness(owner, topic, 1.0)

            # 更新 metadata 中的 access_count
            metadata['access_count'] = metadata.get('access_count', 0) + 1
            metadata['last_accessed_ms'] = now_ms
            self.store.upsert_knowledge_health(
                owner=owner,
                topic=topic,
                source=target.get('source'),
                freshness_score=1.0,
                accuracy_score=target.get('accuracy_score', 1.0),
                completeness_score=target.get('completeness_score', 1.0),
                metadata=json.dumps(metadata),
            )

            # 创建新的 forgetting_schedule
            review_count = metadata.get('access_count', 1)
            review_interval_hours = self.model.next_review_interval(review_count, category)
            review_interval_days = max(1.0, review_interval_hours / 24.0)
            self.store.insert_forgetting_schedule(
                owner=owner,
                chunk_id=topic,
                topic=topic,
                interval_days=review_interval_days,
                ease_factor=2.5,
            )

            return {
                'success': True,
                'topic': topic,
                'freshness_score': 1.0,
                'access_count': metadata['access_count'],
            }
        except Exception as e:
            logger.error(f"record_access failed: {e}")
            return {'success': False, 'error': str(e)}

    # ------------------------------------------------------------------
    # 复习提醒
    # ------------------------------------------------------------------

    def get_due_reviews(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取需要复习的知识条目。

        Returns:
            到期复习条目列表
        """
        try:
            owner = team_id or 'local'
            return self.store.get_due_reviews(owner)
        except Exception as e:
            logger.error(f"get_due_reviews failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 健康摘要
    # ------------------------------------------------------------------

    def get_health_summary(self, team_id: str) -> Dict[str, Any]:
        """获取团队知识健康摘要。

        Returns:
            包含状态统计和高风险条目的摘要
        """
        try:
            now_ms = int(time.time() * 1000)
            records = self.store.list_knowledge_health(team_id)

            status_counts: Dict[str, int] = {
                'fresh': 0, 'aging': 0, 'stale': 0, 'forgotten': 0,
            }
            high_risk: List[Dict[str, Any]] = []
            total_freshness = 0.0

            for rec in records:
                metadata = self._parse_metadata(rec.get('metadata'))
                category = metadata.get('category', 'general')
                importance = metadata.get('importance', 0.5)
                last_verified = rec.get('last_verified_at') or rec.get('createdAt', now_ms)
                days_since = (now_ms - last_verified) / 86400000.0

                fs = self.model.retention_score(days_since, category)
                status = self.model.freshness_status(days_since, category)
                status_counts[status] = status_counts.get(status, 0) + 1
                total_freshness += fs

                # 高风险: importance > 0.7 且 freshness < 0.5
                if importance > 0.7 and fs < 0.5:
                    high_risk.append({
                        'topic': rec.get('topic', ''),
                        'category': category,
                        'importance': importance,
                        'freshness': round(fs, 4),
                        'status': status,
                        'days_since_access': round(days_since, 1),
                    })

            total = len(records) or 1
            return {
                'team_id': team_id,
                'total_knowledge': len(records),
                'status_counts': status_counts,
                'average_freshness': round(total_freshness / total, 4),
                'high_risk_count': len(high_risk),
                'high_risk_items': high_risk,
            }
        except Exception as e:
            logger.error(f"get_health_summary failed: {e}")
            return {'team_id': team_id, 'error': str(e)}

    # ------------------------------------------------------------------
    # 批量更新
    # ------------------------------------------------------------------

    def update_all_freshness(self) -> int:
        """批量更新所有知识的新鲜度分数。

        Returns:
            更新的记录数
        """
        try:
            now_ms = int(time.time() * 1000)
            updated = 0

            # 遍历所有 owner（使用 check_freshness 逻辑，但 owner='local'）
            owner = 'local'
            records = self.store.list_knowledge_health(owner)
            for rec in records:
                topic = rec.get('topic', '')
                metadata = self._parse_metadata(rec.get('metadata'))
                category = metadata.get('category', 'general')
                last_verified = rec.get('last_verified_at') or rec.get('createdAt', now_ms)
                days_since = (now_ms - last_verified) / 86400000.0
                new_freshness = self.model.retention_score(days_since, category)

                if self.store.update_freshness(owner, topic, new_freshness):
                    updated += 1

            return updated
        except Exception as e:
            logger.error(f"update_all_freshness failed: {e}")
            return 0

    # ------------------------------------------------------------------
    # 内部工具
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_metadata(metadata: Optional[str]) -> Dict[str, Any]:
        """安全解析 metadata JSON 字符串。"""
        if not metadata:
            return {}
        try:
            return json.loads(metadata)
        except (json.JSONDecodeError, TypeError):
            return {}
