"""
Direction B: Decision Extractor
从飞书对话/文档中自动提取决策信息
"""
import json
import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class DecisionExtractor:
    """从对话和文档中提取结构化决策信息"""

    # 决策信号词（中文）
    DECISION_SIGNALS_ZH = [
        r'我们(?:决定|确认|选定|敲定|采用|定)',
        r'(?:最终|最后)(?:决定|确认|选定|定)',
        r'(?:经过|根据).*(?:讨论|评估|对比).*决定',
        r'(?:同意|赞成|支持)(?:使用|采用|选择)',
        r'(?:否决|否定|放弃|排除)(?:了)?',
        r'方案[甲乙丙ABC](?:更|最)?(?:好|优|合适)',
        r'(?:截止|deadline|交付)(?:日期|时间)(?:是|定在|改为)',
        r'(?:负责人|owner|对接人)(?:是|改为|变更为)',
        r'(?:优先级|priority)(?:改为|调整为|定为)',
        r'(?:结论|总结|决议)',
        r'(?:就|那就)(?:定|用|选)',
    ]

    # 决策信号词（英文）
    DECISION_SIGNALS_EN = [
        r'(?:we|team)\s+(?:decided|confirmed|agreed|chose)',
        r'(?:final|ultimately)\s+(?:decision|choice)',
        r'(?:approved|rejected|postponed)',
        r'deadline\s+(?:is|changed to|extended to)',
        r'(?:owner|assignee)\s+(?:is|changed to)',
        r'(?:priority)\s+(?:set to|changed to)',
    ]

    # 否决/反对信号
    REJECTION_SIGNALS = [
        r'不(?:同意|赞成|支持|采用)',
        r'(?:否决|否定|拒绝|放弃)',
        r'(?:反对|不同意)',
        r'(?:rejected|opposed|disagreed)',
        r'不做',
        r'算了',
    ]

    # 理由信号
    RATIONALE_SIGNALS = [
        r'(?:因为|由于|考虑到|基于)',
        r'(?:原因|理由)(?:是|在于)',
        r'(?:优点|优势|好处)(?:是|在于)',
        r'(?:缺点|不足|风险)(?:是|在于)',
        r'(?:because|since|due to|reason)',
        r'(?:pros|cons|advantage|drawback)',
    ]

    def __init__(self, store):
        self.store = store

    def extract_from_message(
        self,
        message: str,
        sender: str = '',
        project_id: str = '',
        channel_id: str = '',
        timestamp_ms: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """从单条消息中提取决策信息"""
        decisions = []
        ts = timestamp_ms or int(time.time() * 1000)

        # 检测是否包含决策信号
        has_decision_signal = False
        for pattern in self.DECISION_SIGNALS_ZH + self.DECISION_SIGNALS_EN:
            if re.search(pattern, message, re.IGNORECASE):
                has_decision_signal = True
                break

        if not has_decision_signal:
            return decisions

        # 提取决策内容
        decision_text = self._extract_decision_text(message)
        if not decision_text:
            return decisions

        # 提取理由
        rationale = self._extract_rationale(message)

        # 检测被否决的方案
        alternatives = self._extract_alternatives(message)

        # 构建决策记录
        decision = {
            'id': str(uuid.uuid4()),
            'project_id': project_id,
            'title': self._generate_title(decision_text),
            'decision': decision_text,
            'rationale': rationale,
            'alternatives': json.dumps(alternatives, ensure_ascii=False) if alternatives else None,
            'participants': json.dumps([sender], ensure_ascii=False) if sender else None,
            'source_message': message[:500],
            'source_channel': channel_id,
            'decided_at_ms': ts,
            'status': 'active',
        }

        decisions.append(decision)
        return decisions

    def extract_from_conversation(
        self,
        messages: List[Dict[str, Any]],
        project_id: str = '',
        channel_id: str = '',
    ) -> List[Dict[str, Any]]:
        """从多轮对话中提取决策"""
        all_decisions = []
        participants = set()

        for msg in messages:
            sender = msg.get('sender', msg.get('role', ''))
            content = msg.get('content', msg.get('text', ''))
            ts = msg.get('timestamp_ms', msg.get('timestamp', None))

            if sender:
                participants.add(sender)

            decisions = self.extract_from_message(
                content, sender, project_id, channel_id, ts
            )
            all_decisions.extend(decisions)

        # 为每个决策补充完整参与者列表
        for dec in all_decisions:
            dec['participants'] = json.dumps(list(participants), ensure_ascii=False)

        return all_decisions

    def save_decisions(self, decisions: List[Dict[str, Any]], owner: str = 'default') -> List[str]:
        """保存提取的决策到数据库"""
        ids = []
        for dec in decisions:
            try:
                did = self.store.insert_decision(
                    owner=owner,
                    title=dec.get('title', ''),
                    project=dec.get('project_id', ''),
                    context=dec.get('decision', ''),
                    chosen=dec.get('rationale', ''),
                    alternatives=dec.get('alternatives', ''),
                    tags=json.dumps({
                        'participants': dec.get('participants', '[]'),
                        'source_channel': dec.get('source_channel', ''),
                        'decided_at_ms': dec.get('decided_at_ms', 0),
                        'status': dec.get('status', 'active'),
                    }, ensure_ascii=False),
                )
                if did:
                    ids.append(did)
            except Exception as e:
                logger.error(f"Failed to save decision: {e}")
        return ids

    def _extract_decision_text(self, message: str) -> str:
        """提取决策核心内容"""
        # 尝试匹配 "决定XXX" 模式
        patterns = [
            r'(?:决定|确认|选定|敲定|采用|同意)\s*(.+?)(?:[。\.]|$)',
            r'(?:decided|confirmed|agreed)\s+(?:to\s+)?(.+?)(?:\.|$)',
            r'(?:方案|选择|决定)\s*(?:是|为)\s*(.+?)(?:[。\.]|$)',
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        # 如果没有明确模式，取决策信号后的句子
        for signal in self.DECISION_SIGNALS_ZH:
            match = re.search(signal, message)
            if match:
                rest = message[match.end():].strip()
                # 取到句号或结尾
                end = re.search(r'[。\.！!]', rest)
                if end:
                    return rest[:end.start()].strip()
                return rest[:200].strip()

        return ''

    def _extract_rationale(self, message: str) -> str:
        """提取决策理由"""
        for pattern in self.RATIONALE_SIGNALS:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                rest = message[match.end():].strip()
                end = re.search(r'[。\.，,；;]', rest)
                if end:
                    return rest[:end.start()].strip()
                return rest[:200].strip()
        return ''

    def _extract_alternatives(self, message: str) -> List[str]:
        """提取被否决的方案"""
        alternatives = []

        # 匹配 "不选A" / "放弃B" 模式
        for pattern in self.REJECTION_SIGNALS:
            match = re.search(pattern + r'\s*(.+?)(?:[，,。\.]|$)', message)
            if match:
                alt = match.group(1).strip() if match.lastindex else ''
                if alt:
                    alternatives.append(alt)

        # 匹配 "A而不是B" / "A而非C" 模式
        rather_patterns = [
            r'(.+?)(?:而不是|而非|不是|优于)\s*(.+?)(?:[，,。\.]|$)',
            r'(.+?)\s+(?:instead of|rather than)\s+(.+?)(?:\.|$)',
        ]
        for pattern in rather_patterns:
            match = re.search(pattern, message)
            if match:
                alternatives.append(match.group(2).strip())

        return alternatives

    def _generate_title(self, decision_text: str) -> str:
        """从决策内容生成简短标题"""
        if not decision_text:
            return '未命名决策'
        # 取前30个字符作为标题
        title = decision_text[:30]
        if len(decision_text) > 30:
            title += '...'
        return title

    def search_decisions(
        self,
        query: str,
        owner: str = 'default',
        project_id: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """搜索决策"""
        return self.store.search_decisions(owner, query=query, project=project_id, limit=limit)

    def get_project_decisions(
        self,
        project_id: str,
        owner: str = 'default',
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """获取项目的所有决策"""
        return self.store.get_decisions_by_project(owner, project_id, limit)
