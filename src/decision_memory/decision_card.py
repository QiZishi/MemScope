"""
Direction B: Decision Card Manager
历史决策卡片推送 - 当相关话题被提及时主动推送
"""
import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DecisionCardManager:
    """决策卡片管理器 - 主动推送历史决策"""

    def __init__(self, store):
        self.store = store

    def check_and_push(
        self,
        current_message: str,
        owner: str = 'default',
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """检查当前消息是否涉及已有决策话题，返回需要推送的决策卡片"""
        cards = []

        # 提取当前消息的关键词
        keywords = self._extract_keywords(current_message)
        if not keywords:
            return cards

        # 搜索相关决策
        related_decisions = []
        for keyword in keywords[:5]:  # 最多查5个关键词
            results = self.store.search_decisions(owner, query=keyword, project=project_id, limit=3)
            for r in results:
                if r.get('id') not in {d.get('id') for d in related_decisions}:
                    related_decisions.append(r)

        # 生成决策卡片
        for decision in related_decisions[:3]:  # 最多推送3个
            card = self._format_decision_card(decision)
            if card:
                cards.append(card)

        return cards

    def format_cards_markdown(self, cards: List[Dict[str, Any]]) -> str:
        """将决策卡片格式化为 Markdown"""
        if not cards:
            return ''

        lines = ['## 📋 相关历史决策\n']
        for i, card in enumerate(cards, 1):
            lines.append(f"### {i}. {card.get('title', '未命名决策')}")
            lines.append(f"**决策**: {card.get('decision', 'N/A')}")

            if card.get('rationale'):
                lines.append(f"**理由**: {card['rationale']}")

            if card.get('alternatives'):
                try:
                    alts = json.loads(card['alternatives']) if isinstance(card['alternatives'], str) else card['alternatives']
                    if alts:
                        lines.append(f"**被否决方案**: {', '.join(alts)}")
                except (json.JSONDecodeError, TypeError):
                    pass

            if card.get('participants'):
                try:
                    parts = json.loads(card['participants']) if isinstance(card['participants'], str) else card['participants']
                    if parts:
                        lines.append(f"**参与者**: {', '.join(parts)}")
                except (json.JSONDecodeError, TypeError):
                    pass

            tags = card.get('tags', '{}')
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = {}

            if tags.get('decided_at_ms'):
                from datetime import datetime
                ts = tags['decided_at_ms'] / 1000
                dt = datetime.fromtimestamp(ts)
                lines.append(f"**时间**: {dt.strftime('%Y-%m-%d %H:%M')}")

            lines.append(f"**状态**: {tags.get('status', 'active')}")
            lines.append('')

        return '\n'.join(lines)

    def record_decision(
        self,
        title: str,
        decision: str,
        rationale: str = '',
        project_id: str = '',
        alternatives: List[str] = None,
        participants: List[str] = None,
        owner: str = 'default',
    ) -> str:
        """手动记录决策"""
        try:
            did = self.store.insert_decision(
                owner=owner,
                title=title,
                project=project_id,
                context=decision,
                chosen=rationale,
                alternatives=json.dumps(alternatives or [], ensure_ascii=False),
                tags=json.dumps({
                    'participants': json.dumps(participants or [], ensure_ascii=False),
                    'status': 'active',
                    'decided_at_ms': int(time.time() * 1000),
                }, ensure_ascii=False),
            )
            return did
        except Exception as e:
            logger.error(f"Failed to record decision: {e}")
            return ''

    def overturn_decision(self, decision_id: str, reason: str = '') -> bool:
        """推翻一个决策"""
        try:
            decision = self.store.get_decision(decision_id)
            if not decision:
                return False

            tags = decision.get('tags', '{}')
            if isinstance(tags, str):
                try:
                    tags = json.loads(tags)
                except json.JSONDecodeError:
                    tags = {}

            tags['status'] = 'overturned'
            tags['overturned_reason'] = reason
            tags['overturned_at_ms'] = int(time.time() * 1000)

            self.store.update_decision(decision_id, {'tags': json.dumps(tags, ensure_ascii=False)})
            return True
        except Exception as e:
            logger.error(f"Failed to overturn decision: {e}")
            return False

    def get_decision_history(
        self,
        project_id: str = '',
        owner: str = 'default',
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取决策历史"""
        if project_id:
            return self.store.get_decisions_by_project(owner, project_id, limit)
        # 返回所有决策
        try:
            return self.store.search_decisions(owner, limit=limit)
        except Exception:
            return []

    def _extract_keywords(self, text: str) -> List[str]:
        """从文本中提取关键词"""
        keywords = []

        # 中文关键词提取（简单方法：取2-4字的高频词组）
        # 技术关键词
        tech_patterns = [
            r'(?:React|Vue|Angular|Python|Java|Go|Rust|Docker|K8s|Kubernetes)',
            r'(?:方案[甲乙丙ABC]|架构|部署|发布|上线|回滚)',
            r'(?:API|SDK|数据库|缓存|消息队列|微服务)',
            r'(?:前端|后端|全栈|运维|测试|产品)',
            r'(?:Redis|MySQL|MongoDB|Elasticsearch|Kafka|RabbitMQ)',
        ]

        for pattern in tech_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            keywords.extend(matches)

        # 提取引号内的关键词
        quoted = re.findall(r'["\u201c]([^"\u201d]{2,20})["\u201d]', text)
        keywords.extend(quoted)

        # 提取中文名词短语（简单：连续2-6个汉字）
        cn_nouns = re.findall(r'[\u4e00-\u9fff]{2,6}', text)
        # 过滤常见停用词
        stopwords = {'我们', '他们', '你们', '这个', '那个', '什么', '怎么', '为什么',
                     '因为', '所以', '但是', '而且', '或者', '如果', '虽然', '可以',
                     '已经', '还是', '不是', '所有', '一些', '一个', '这些', '那些'}
        cn_nouns = [w for w in cn_nouns if w not in stopwords]
        keywords.extend(cn_nouns[:10])

        # 去重
        seen = set()
        unique = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen:
                seen.add(kw_lower)
                unique.append(kw)

        return unique

    def _format_decision_card(self, decision: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """格式化单个决策为卡片"""
        if not decision:
            return None

        return {
            'id': decision.get('id', ''),
            'title': decision.get('title', '未命名决策'),
            'decision': decision.get('context', decision.get('chosen', '')),
            'rationale': decision.get('chosen', ''),
            'alternatives': decision.get('alternatives', '[]'),
            'participants': decision.get('tags', '{}'),
            'project': decision.get('project', ''),
            'tags': decision.get('tags', '{}'),
        }
