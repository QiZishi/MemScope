"""
偏好管理器 - 生命周期管理、冲突解决、置信度衰减

Direction C: Personal Work Habits / Preference Memory.

功能:
  1. 偏好 CRUD 操作
  2. 来源优先级冲突解决 (explicit > inferred > observed)
  3. 置信度衰减与自动清理
  4. 偏好导入/导出
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 来源优先级映射 (数值越大优先级越高)
_SOURCE_PRIORITY: Dict[str, int] = {
    'explicit': 100,
    'user_explicit': 100,
    'inferred': 50,
    'habit_inference': 50,
    'extracted': 40,
    'observed': 20,
}

# 默认衰减率
DEFAULT_DECAY_RATE: float = 0.95

# 最低有效置信度
MIN_CONFIDENCE: float = 0.1


class PreferenceManager:
    """管理用户偏好的完整生命周期。"""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: SqliteStore 实例，需支持 upsert_preference / get_preference 等方法。
        """
        self.store = store

    # ------------------------------------------------------------------
    # 设置偏好
    # ------------------------------------------------------------------

    def set_preference(
        self,
        owner: str,
        category: str,
        key: str,
        value: str,
        source: str = 'explicit',
        confidence: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        设置偏好，处理冲突。

        Args:
            owner: 用户/agent ID。
            category: 偏好类别 (style, tool, schedule, workflow 等)。
            key: 偏好键。
            value: 偏好值。
            source: 来源 (explicit / inferred / observed / extracted)。
            confidence: 置信度。None 时根据来源自动设置。

        Returns:
            设置后的偏好记录字典。
        """
        # 根据来源设置默认置信度
        if confidence is None:
            if source in ('explicit', 'user_explicit'):
                confidence = 0.9
            elif source in ('inferred', 'habit_inference', 'extracted'):
                confidence = 0.6
            else:
                confidence = 0.3

        # 确保置信度在合理范围内
        confidence = max(0.0, min(confidence, 1.0))

        # 检查是否存在冲突的偏好
        existing = self._safe_get_preference(owner, category, key)
        conflict_info: Optional[Dict[str, Any]] = None

        if existing and existing.get('value') != value:
            # 存在冲突 - 使用冲突解决策略
            resolution = self.resolve_conflict(existing, {
                'category': category,
                'key': key,
                'value': value,
                'confidence': confidence,
                'source': source,
            })

            # 如果新值胜出，继续更新；否则保持原值
            if resolution.get('id') == 'new':
                conflict_info = {
                    'resolved': True,
                    'winner': 'new',
                    'old_value': existing.get('value'),
                    'new_value': value,
                    'reason': resolution.get('reason', ''),
                }
            else:
                # 旧值胜出，不更新
                logger.info(
                    f"preference_manager: keeping existing preference "
                    f"{owner}/{category}/{key}={existing.get('value')} "
                    f"(conflict resolved: {resolution.get('reason', '')})"
                )
                result = dict(existing)
                result['conflict_resolved'] = {
                    'winner': 'existing',
                    'reason': resolution.get('reason', ''),
                }
                return result
        elif existing and existing.get('value') == value:
            # 相同值，提升置信度
            old_conf = existing.get('confidence', 0.5)
            confidence = min(old_conf + 0.05, 1.0)

        # 执行 upsert
        try:
            pref_id = self.store.upsert_preference(
                owner=owner,
                category=category,
                key=key,
                value=value,
                confidence=confidence,
                source=source,
            )

            result: Dict[str, Any] = {
                'id': pref_id,
                'owner': owner,
                'category': category,
                'key': key,
                'value': value,
                'confidence': confidence,
                'source': source,
            }

            if conflict_info:
                result['conflict_resolved'] = conflict_info

            logger.info(
                f"preference_manager: set preference "
                f"{owner}/{category}/{key}={value} "
                f"(source={source}, confidence={confidence:.2f})"
            )
            return result

        except Exception as e:
            logger.error(f"preference_manager: failed to set preference: {e}")
            return {
                'id': '',
                'owner': owner,
                'category': category,
                'key': key,
                'value': value,
                'confidence': confidence,
                'source': source,
                'error': str(e),
            }

    # ------------------------------------------------------------------
    # 获取偏好
    # ------------------------------------------------------------------

    def get_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """
        获取单个偏好。

        Args:
            owner: 用户/agent ID。
            category: 偏好类别。
            key: 偏好键。

        Returns:
            偏好记录字典，不存在则返回 None。
        """
        return self._safe_get_preference(owner, category, key)

    def get_preference_value(
        self,
        owner: str,
        category: str,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """获取偏好的值部分，不存在则返回默认值。"""
        pref = self._safe_get_preference(owner, category, key)
        if pref:
            return pref.get('value', default)
        return default

    # ------------------------------------------------------------------
    # 列出偏好
    # ------------------------------------------------------------------

    def list_preferences(
        self,
        owner: str,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        列出用户的所有偏好。

        Args:
            owner: 用户/agent ID。
            category: 可选的类别过滤。

        Returns:
            偏好记录列表。
        """
        try:
            return self.store.list_preferences(owner=owner, category=category)
        except Exception as e:
            logger.error(f"preference_manager: failed to list preferences: {e}")
            return []

    def list_by_confidence(
        self,
        owner: str,
        min_confidence: float = 0.0,
        category: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """按置信度过滤并排序偏好。"""
        all_prefs = self.list_preferences(owner, category)
        filtered = [p for p in all_prefs if p.get('confidence', 0) >= min_confidence]
        filtered.sort(key=lambda p: p.get('confidence', 0), reverse=True)
        return filtered

    # ------------------------------------------------------------------
    # 删除偏好
    # ------------------------------------------------------------------

    def delete_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> bool:
        """
        删除偏好。

        Args:
            owner: 用户/agent ID。
            category: 偏好类别。
            key: 偏好键。

        Returns:
            是否成功删除。
        """
        try:
            success = self.store.delete_preference(owner, category, key)
            if success:
                logger.info(
                    f"preference_manager: deleted preference {owner}/{category}/{key}"
                )
            return success
        except Exception as e:
            logger.error(f"preference_manager: failed to delete preference: {e}")
            return False

    # ------------------------------------------------------------------
    # 冲突解决
    # ------------------------------------------------------------------

    def resolve_conflict(
        self,
        existing: Dict[str, Any],
        new: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        偏好冲突解决。

        规则:
          1. 来源优先级: explicit > inferred > extracted > observed
          2. 同级来源: 新值 > 旧值 (recency wins)
          3. 高置信度 > 低置信度

        Args:
            existing: 已存在的偏好记录。
            new: 新的偏好记录。

        Returns:
            胜出方的记录，附加 'id' 字段 ('existing' 或 'new') 和 'reason'。
        """
        existing_source = existing.get('source', 'observed')
        new_source = new.get('source', 'observed')
        existing_priority = _SOURCE_PRIORITY.get(existing_source, 10)
        new_priority = _SOURCE_PRIORITY.get(new_source, 10)

        # 规则1: 来源优先级
        if new_priority > existing_priority:
            result = dict(new)
            result['id'] = 'new'
            result['reason'] = (
                f"higher source priority: {new_source}({new_priority}) > "
                f"{existing_source}({existing_priority})"
            )
            return result
        elif existing_priority > new_priority:
            result = dict(existing)
            result['id'] = 'existing'
            result['reason'] = (
                f"higher source priority: {existing_source}({existing_priority}) > "
                f"{new_source}({new_priority})"
            )
            return result

        # 规则2: 同级来源 - 比较置信度
        existing_conf = existing.get('confidence', 0.5)
        new_conf = new.get('confidence', 0.5)

        if new_conf > existing_conf:
            result = dict(new)
            result['id'] = 'new'
            result['reason'] = (
                f"higher confidence: {new_conf:.2f} > {existing_conf:.2f} "
                f"(same source level)"
            )
            return result
        elif existing_conf > new_conf:
            result = dict(existing)
            result['id'] = 'existing'
            result['reason'] = (
                f"higher confidence: {existing_conf:.2f} > {new_conf:.2f} "
                f"(same source level)"
            )
            return result

        # 规则3: 同置信度 - 新值胜出 (recency)
        result = dict(new)
        result['id'] = 'new'
        result['reason'] = "recency: new value wins at same priority and confidence"
        return result

    # ------------------------------------------------------------------
    # 置信度衰减
    # ------------------------------------------------------------------

    def decay_all(
        self,
        owner: str,
        decay_rate: float = DEFAULT_DECAY_RATE,
    ) -> int:
        """
        对所有偏好执行置信度衰减。

        每次衰减: new_confidence = old_confidence * decay_rate
        置信度低于 MIN_CONFIDENCE 的偏好将被标记为待清理。

        Args:
            owner: 用户/agent ID。
            decay_rate: 衰减因子 (0.0-1.0)。

        Returns:
            受影响的偏好数量。
        """
        try:
            affected = self.store.decay_preference_confidence(
                owner=owner,
                decay_factor=decay_rate,
            )

            if affected > 0:
                logger.info(
                    f"preference_manager: decayed {affected} preferences "
                    f"for owner={owner} (rate={decay_rate})"
                )

            # 清理低置信度偏好
            cleaned = self._cleanup_low_confidence(owner)
            if cleaned > 0:
                logger.info(
                    f"preference_manager: cleaned {cleaned} low-confidence preferences"
                )

            return affected

        except Exception as e:
            logger.error(f"preference_manager: decay failed: {e}")
            return 0

    # ------------------------------------------------------------------
    # 批量操作
    # ------------------------------------------------------------------

    def import_preferences(
        self,
        owner: str,
        preferences: List[Dict[str, str]],
    ) -> int:
        """
        批量导入偏好。

        Args:
            owner: 用户/agent ID。
            preferences: 偏好列表，每项需包含 category, key, value。

        Returns:
            成功导入的数量。
        """
        count = 0
        for pref in preferences:
            category = pref.get('category', '')
            key = pref.get('key', '')
            value = pref.get('value', '')

            if not all([category, key, value]):
                continue

            try:
                self.set_preference(
                    owner=owner,
                    category=category,
                    key=key,
                    value=value,
                    source=pref.get('source', 'explicit'),
                    confidence=pref.get('confidence'),
                )
                count += 1
            except Exception as e:
                logger.warning(
                    f"preference_manager: import failed for {category}/{key}: {e}"
                )

        logger.info(
            f"preference_manager: imported {count}/{len(preferences)} preferences "
            f"for owner={owner}"
        )
        return count

    def export_preferences(self, owner: str) -> List[Dict[str, Any]]:
        """
        导出用户的所有偏好。

        Args:
            owner: 用户/agent ID。

        Returns:
            偏好记录列表 (可序列化)。
        """
        prefs = self.list_preferences(owner)
        return [
            {
                'category': p.get('category', ''),
                'key': p.get('key', ''),
                'value': p.get('value', ''),
                'confidence': p.get('confidence', 0),
                'source': p.get('source', ''),
            }
            for p in prefs
        ]

    # ------------------------------------------------------------------
    # 摘要
    # ------------------------------------------------------------------

    def get_summary(self, owner: str) -> Dict[str, Any]:
        """
        获取用户偏好的摘要信息。

        Args:
            owner: 用户/agent ID。

        Returns:
            包含分类统计和 top 偏好的摘要字典。
        """
        all_prefs = self.list_preferences(owner)

        by_category: Dict[str, List[Dict[str, Any]]] = {}
        for pref in all_prefs:
            cat = pref.get('category', 'unknown')
            by_category.setdefault(cat, []).append(pref)

        summary: Dict[str, Any] = {
            'owner': owner,
            'total_preferences': len(all_prefs),
            'categories': {},
        }

        for cat, prefs in by_category.items():
            top = sorted(
                prefs,
                key=lambda p: p.get('confidence', 0),
                reverse=True,
            )[:5]
            summary['categories'][cat] = {
                'count': len(prefs),
                'top_preferences': [
                    {
                        'key': p.get('key', ''),
                        'value': p.get('value', ''),
                        'confidence': p.get('confidence', 0),
                        'source': p.get('source', ''),
                    }
                    for p in top
                ],
            }

        return summary

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _safe_get_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """安全地获取偏好，捕获所有异常。"""
        try:
            return self.store.get_preference(owner=owner, category=category, key=key)
        except Exception as e:
            logger.error(f"preference_manager: failed to get preference: {e}")
            return None

    def _cleanup_low_confidence(self, owner: str) -> int:
        """清理置信度过低的偏好。"""
        cleaned = 0
        try:
            all_prefs = self.list_preferences(owner)
            for pref in all_prefs:
                conf = pref.get('confidence', 1.0)
                if conf < MIN_CONFIDENCE:
                    success = self.store.delete_preference(
                        owner=owner,
                        category=pref.get('category', ''),
                        key=pref.get('key', ''),
                    )
                    if success:
                        cleaned += 1
                        logger.debug(
                            f"preference_manager: removed low-confidence preference "
                            f"{pref.get('category')}/{pref.get('key')} "
                            f"(confidence={conf:.3f})"
                        )
        except Exception as e:
            logger.error(f"preference_manager: cleanup failed: {e}")

        return cleaned
