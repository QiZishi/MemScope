"""
习惯推断引擎 - 从行为模式中学习用户习惯

Direction C: Personal Work Habits / Preference Memory.

策略:
  1. 时间模式分析 - 从 tool_logs 的时间戳中提取活跃时段
  2. 工具使用频率分析 - 统计工具调用频率与偏好
  3. 主题聚类分析 - 从对话内容中提取高频关键词
  4. 工作流序列挖掘 - 识别重复出现的工具调用序列
"""

import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 中英文停用词
_STOP_WORDS = {
    # 英文
    "the", "and", "for", "are", "but", "not", "you", "all", "can",
    "had", "her", "was", "one", "our", "out", "has", "have", "been",
    "from", "this", "that", "with", "they", "will", "each", "make",
    "like", "into", "than", "then", "them", "were", "what", "when",
    "your", "how", "its", "also", "just", "over", "such", "some",
    "very", "would", "could", "should", "about", "other", "which",
    "their", "there", "being", "have", "does", "did", "done",
    # 中文常见虚词
    "的", "了", "是", "在", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "他", "她",
    "么", "那", "被", "从", "把", "对", "它", "吧", "呢", "吗",
    "请", "帮", "我", "们", "给", "让", "用", "做", "来", "可以",
}


class HabitInference:
    """从历史交互数据中推断行为模式和习惯。"""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: SqliteStore 实例。
        """
        self.store = store

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def get_habit_summary(self, owner: str) -> Dict[str, Any]:
        """
        获取用户习惯的综合总结。

        Args:
            owner: 用户/agent ID。

        Returns:
            综合习惯摘要，包含:
            - time_patterns: 时间模式
            - tool_preferences: 工具偏好
            - topic_clusters: 主题聚类
            - workflows: 工作流序列
        """
        return {
            'owner': owner,
            'time_patterns': self.analyze_time_patterns(owner),
            'tool_preferences': self.analyze_tool_frequency(owner),
            'topic_clusters': self.analyze_topic_clusters(owner),
            'workflows': self.analyze_workflow_sequences(owner),
        }

    # ------------------------------------------------------------------
    # 时间模式分析
    # ------------------------------------------------------------------

    def analyze_time_patterns(self, owner: str) -> List[Dict[str, Any]]:
        """
        分析时间模式 - 从 tool_logs 的时间戳中提取活跃时段。

        Args:
            owner: 用户/agent ID。

        Returns:
            时间模式列表，包含:
            - pattern_type: 'time_pattern'
            - description: 人类可读描述
            - data: 详细数据 (peak_hours, day_distribution 等)
            - confidence: 置信度
        """
        patterns: List[Dict[str, Any]] = []

        try:
            tool_logs = self.store.get_tool_logs(limit=500, owner=owner)
        except Exception as e:
            logger.warning(f"habit_inference: failed to get tool logs: {e}")
            tool_logs = []

        # 如果工具日志不够，尝试从 chunks 的时间戳中获取数据
        chunk_timestamps: List[int] = []
        try:
            chunks = self.store.get_all_chunks(limit=500)
            for c in chunks:
                if c.get('owner') == owner or not c.get('owner'):
                    ts = c.get('createdAt', 0)
                    if ts > 0:
                        chunk_timestamps.append(ts)
        except Exception as e:
            logger.debug(f"habit_inference: failed to get chunks for time analysis: {e}")

        # 合并时间戳
        all_timestamps: List[int] = []

        for log in tool_logs:
            ts = log.get('ts', 0)
            if ts > 0:
                if ts > 1e12:
                    ts = ts / 1000  # ms -> s
                all_timestamps.append(int(ts))

        for ts in chunk_timestamps:
            if ts > 1e12:
                ts = ts / 1000
            all_timestamps.append(int(ts))

        if len(all_timestamps) < 5:
            return patterns

        # 按小时统计
        hour_counts: Counter = Counter()
        day_counts: Counter = Counter()
        weekday_counts: Counter = Counter()

        for ts in all_timestamps:
            try:
                dt = datetime.fromtimestamp(ts)
                hour_counts[dt.hour] += 1
                day_counts[dt.strftime('%Y-%m-%d')] += 1
                weekday_counts[dt.strftime('%A')] += 1
            except (OSError, ValueError, OverflowError):
                continue

        total = sum(hour_counts.values())

        # 高频时段检测
        if total > 0:
            avg_per_hour = total / 24
            peak_hours = sorted(
                [(h, c) for h, c in hour_counts.items() if c > avg_per_hour * 1.2],
                key=lambda x: x[1],
                reverse=True,
            )

            if peak_hours:
                peak_range = self._format_hour_range([h for h, _ in peak_hours[:5]])
                confidence = min(0.4 + (total / 200) * 0.5, 0.95)

                pattern = self._store_pattern(
                    owner=owner,
                    pattern_type='time_pattern',
                    description=f'最活跃时段: {peak_range}',
                    data={
                        'peak_hours': {str(h): c for h, c in peak_hours[:10]},
                        'hour_distribution': {str(hr): cnt for hr, cnt in sorted(hour_counts.items())},
                        'total_samples': total,
                    },
                    confidence=confidence,
                )
                if pattern:
                    patterns.append(pattern)

        # 星期几分布检测
        if weekday_counts:
            most_common_day = weekday_counts.most_common(1)[0]
            least_common_day = weekday_counts.most_common()[-1] if len(weekday_counts) > 1 else most_common_day

            if (most_common_day[1] > least_common_day[1] * 1.5 and
                    most_common_day[1] > 5):
                confidence = min(0.35 + (total / 100) * 0.4, 0.85)

                pattern = self._store_pattern(
                    owner=owner,
                    pattern_type='time_pattern',
                    description=(
                        f'最活跃日: {most_common_day[0]} ({most_common_day[1]}次), '
                        f'最少: {least_common_day[0]} ({least_common_day[1]}次)'
                    ),
                    data={
                        'day_distribution': dict(weekday_counts),
                        'busiest_day': most_common_day[0],
                        'quietest_day': least_common_day[0],
                    },
                    confidence=confidence,
                )
                if pattern:
                    patterns.append(pattern)

        # 工作日 vs 周末
        weekday_names = {'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'}
        weekend_names = {'Saturday', 'Sunday'}
        weekday_total = sum(weekday_counts.get(d, 0) for d in weekday_names)
        weekend_total = sum(weekday_counts.get(d, 0) for d in weekend_names)

        if weekday_total > 0 and weekend_total > 0:
            ratio = weekday_total / max(weekend_total, 1)
            if ratio > 3:
                confidence = min(0.4 + (total / 150) * 0.3, 0.8)
                pattern = self._store_pattern(
                    owner=owner,
                    pattern_type='time_pattern',
                    description=f'主要在工作日活跃 (工作日/周末 = {ratio:.1f}x)',
                    data={
                        'weekday_count': weekday_total,
                        'weekend_count': weekend_total,
                        'ratio': ratio,
                    },
                    confidence=confidence,
                )
                if pattern:
                    patterns.append(pattern)

        return patterns

    # ------------------------------------------------------------------
    # 工具使用频率分析
    # ------------------------------------------------------------------

    def analyze_tool_frequency(self, owner: str) -> List[Dict[str, Any]]:
        """
        分析工具使用频率。

        Args:
            owner: 用户/agent ID。

        Returns:
            工具频率分析结果列表。
        """
        patterns: List[Dict[str, Any]] = []

        try:
            tool_logs = self.store.get_tool_logs(limit=500, owner=owner)
        except Exception as e:
            logger.warning(f"habit_inference: failed to get tool logs: {e}")
            return patterns

        if len(tool_logs) < 3:
            return patterns

        # 统计工具调用次数
        tool_counts: Counter = Counter()
        for log in tool_logs:
            tool_name = log.get('tool', '')
            if tool_name:
                tool_counts[tool_name] += 1

        if not tool_counts:
            return patterns

        total = sum(tool_counts.values())
        ranked = tool_counts.most_common(15)

        # 计算偏好比率
        tool_ranking: Dict[str, Any] = {}
        for name, count in ranked:
            tool_ranking[name] = {
                'count': count,
                'ratio': count / total,
            }

        # 主要工具模式
        top_tools = [f"{name} ({count}次)" for name, count in ranked[:5]]
        description = f'常用工具: {", ".join(top_tools)}'
        confidence = min(0.4 + (total / 100) * 0.5, 0.95)

        pattern = self._store_pattern(
            owner=owner,
            pattern_type='tool_frequency',
            description=description,
            data={
                'tool_ranking': tool_ranking,
                'total_tool_calls': total,
                'unique_tools': len(tool_counts),
                'top_tool': ranked[0][0] if ranked else '',
            },
            confidence=confidence,
        )
        if pattern:
            patterns.append(pattern)

        # 检测工具组合偏好 (经常一起使用的工具)
        combo_patterns = self._detect_tool_combinations(tool_logs)
        patterns.extend(combo_patterns)

        return patterns

    # ------------------------------------------------------------------
    # 主题聚类分析
    # ------------------------------------------------------------------

    def analyze_topic_clusters(self, owner: str) -> List[Dict[str, Any]]:
        """
        分析主题聚类 - 从对话内容中提取高频关键词。

        Args:
            owner: 用户/agent ID。

        Returns:
            主题聚类分析结果列表。
        """
        patterns: List[Dict[str, Any]] = []

        try:
            chunks = self.store.get_all_chunks(limit=300)
        except Exception as e:
            logger.warning(f"habit_inference: failed to get chunks: {e}")
            return patterns

        # 过滤属于该 owner 的 chunks
        owner_chunks = [
            c for c in chunks
            if c.get('owner') == owner or not c.get('owner')
        ]

        if len(owner_chunks) < 5:
            return patterns

        # 提取关键词并聚类
        keyword_groups: Dict[str, List[str]] = defaultdict(list)

        for chunk in owner_chunks:
            content = chunk.get('content', '')
            if not content:
                continue
            keywords = self._extract_keywords(content, top_n=5)
            chunk_id = chunk.get('id', '')
            for kw in keywords:
                keyword_groups[kw].append(chunk_id)

        # 过滤出现频率足够高的关键词
        clusters = {
            kw: chunk_ids
            for kw, chunk_ids in keyword_groups.items()
            if len(chunk_ids) >= 3
        }

        if not clusters:
            return patterns

        sorted_clusters = sorted(
            clusters.items(),
            key=lambda x: len(x[1]),
            reverse=True,
        )

        # 为前5个聚类生成模式
        for keyword, chunk_ids in sorted_clusters[:5]:
            description = f'高频主题: "{keyword}" ({len(chunk_ids)} 条相关记忆)'
            confidence = min(0.35 + len(chunk_ids) / 20, 0.9)

            pattern = self._store_pattern(
                owner=owner,
                pattern_type='topic_cluster',
                description=description,
                data={
                    'keyword': keyword,
                    'chunk_ids': chunk_ids[:30],
                    'cluster_size': len(chunk_ids),
                },
                confidence=confidence,
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    # ------------------------------------------------------------------
    # 工作流序列分析
    # ------------------------------------------------------------------

    def analyze_workflow_sequences(self, owner: str) -> List[Dict[str, Any]]:
        """
        分析工作流序列 - 从 tool_logs 中提取重复出现的工具调用序列。

        Args:
            owner: 用户/agent ID。

        Returns:
            工作流模式列表。
        """
        patterns: List[Dict[str, Any]] = []

        try:
            tool_logs = self.store.get_tool_logs(limit=500, owner=owner)
        except Exception as e:
            logger.warning(f"habit_inference: failed to get tool logs: {e}")
            return patterns

        if len(tool_logs) < 10:
            return patterns

        # 按时间排序（升序）
        sorted_logs = sorted(tool_logs, key=lambda x: x.get('ts', 0))

        # 提取工具名序列
        tool_sequence = [log.get('tool', '') for log in sorted_logs]
        tool_sequence = [t for t in tool_sequence if t]  # 过滤空值

        if len(tool_sequence) < 5:
            return patterns

        # 滑动窗口挖掘频繁序列 (长度 2-5)
        sequences: Counter = Counter()
        for window_size in range(2, 6):
            for i in range(len(tool_sequence) - window_size + 1):
                seq = tuple(tool_sequence[i:i + window_size])
                sequences[seq] += 1

        # 找出重复出现的序列 (>= 2 次)
        repeated = [
            (seq, count)
            for seq, count in sequences.items()
            if count >= 2
        ]
        repeated.sort(key=lambda x: (x[1], len(x[0])), reverse=True)

        # 去重：如果一个子序列的 count 和父序列相同，优先保留父序列
        seen_seqs: set = set()
        for seq, count in repeated[:10]:
            # 检查是否是某个已选序列的子串
            is_sub = False
            for seen in seen_seqs:
                if self._is_subsequence(seq, seen):
                    is_sub = True
                    break
            if is_sub:
                continue

            seen_seqs.add(seq)
            seq_str = ' → '.join(seq)
            description = f'工作流 ({count}次): {seq_str}'
            confidence = min(0.4 + count / 15, 0.9)

            pattern = self._store_pattern(
                owner=owner,
                pattern_type='workflow',
                description=description,
                data={
                    'sequence': list(seq),
                    'occurrence_count': count,
                    'sequence_length': len(seq),
                },
                confidence=confidence,
            )
            if pattern:
                patterns.append(pattern)

        return patterns

    # ------------------------------------------------------------------
    # 智能建议
    # ------------------------------------------------------------------

    def should_suggest(
        self,
        owner: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        基于当前上下文判断是否应该提供建议。

        Args:
            owner: 用户/agent ID。
            context: 当前上下文，包含:
                - time: 当前时间 (ISO 格式或时间戳)
                - recent_tools: 最近使用的工具列表
                - project: 当前项目名

        Returns:
            建议字典，无建议则返回 None。
        """
        suggestions: List[Dict[str, Any]] = []

        try:
            patterns = self.store.get_behavior_patterns(owner=owner)
        except Exception as e:
            logger.warning(f"habit_inference: failed to get behavior patterns: {e}")
            return None

        if not patterns:
            return None

        # 检查时间匹配
        current_time = context.get('time')
        if current_time:
            time_suggestion = self._match_time_pattern(patterns, current_time)
            if time_suggestion:
                suggestions.append(time_suggestion)

        # 检查工具序列匹配
        recent_tools = context.get('recent_tools', [])
        if len(recent_tools) >= 1:
            tool_suggestion = self._match_tool_sequence(patterns, recent_tools)
            if tool_suggestion:
                suggestions.append(tool_suggestion)

        # 返回最高置信度的建议
        if suggestions:
            suggestions.sort(key=lambda s: s.get('confidence', 0), reverse=True)
            return suggestions[0]

        return None

    # ------------------------------------------------------------------
    # 内部方法 - 模式存储
    # ------------------------------------------------------------------

    def _store_pattern(
        self,
        owner: str,
        pattern_type: str,
        description: str,
        data: Dict[str, Any],
        confidence: float,
    ) -> Optional[Dict[str, Any]]:
        """存储行为模式并返回模式字典。"""
        try:
            data_json = json.dumps(data, ensure_ascii=False)
            pattern_id = self.store.insert_behavior_pattern(
                owner=owner,
                pattern_type=pattern_type,
                description=description,
                data=data_json,
                frequency=data.get('occurrence_count', data.get('total_samples', 1)),
                confidence=confidence,
            )

            return {
                'id': pattern_id,
                'pattern_type': pattern_type,
                'description': description,
                'data': data,
                'confidence': confidence,
            }
        except Exception as e:
            logger.error(f"habit_inference: failed to store pattern: {e}")
            return None

    # ------------------------------------------------------------------
    # 内部方法 - 分析辅助
    # ------------------------------------------------------------------

    def _detect_tool_combinations(
        self,
        tool_logs: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """检测频繁一起使用的工具组合。"""
        patterns: List[Dict[str, Any]] = []

        # 按时间窗口（5分钟内）分组工具调用
        if len(tool_logs) < 2:
            return patterns

        sorted_logs = sorted(tool_logs, key=lambda x: x.get('ts', 0))
        window_ms = 5 * 60 * 1000  # 5 分钟

        windows: List[List[str]] = []
        current_window: List[str] = []
        window_start = 0

        for log in sorted_logs:
            ts = log.get('ts', 0)
            tool = log.get('tool', '')
            if not tool:
                continue

            if not current_window:
                window_start = ts
                current_window.append(tool)
            elif ts - window_start <= window_ms:
                current_window.append(tool)
            else:
                if len(current_window) >= 2:
                    windows.append(current_window)
                current_window = [tool]
                window_start = ts

        if len(current_window) >= 2:
            windows.append(current_window)

        # 统计工具对的共现频率
        pair_counts: Counter = Counter()
        for window in windows:
            unique_tools = sorted(set(window))
            for i in range(len(unique_tools)):
                for j in range(i + 1, len(unique_tools)):
                    pair_counts[(unique_tools[i], unique_tools[j])] += 1

        # 找出高频对
        for (t1, t2), count in pair_counts.most_common(5):
            if count >= 2:
                description = f'常用工具组合: {t1} + {t2} ({count}次)'
                confidence = min(0.3 + count / 10, 0.8)

                pattern = self._store_pattern(
                    owner='',
                    pattern_type='tool_combination',
                    description=description,
                    data={
                        'tools': [t1, t2],
                        'co_occurrence': count,
                    },
                    confidence=confidence,
                )
                if pattern:
                    patterns.append(pattern)

        return patterns

    def _match_time_pattern(
        self,
        patterns: List[Dict[str, Any]],
        current_time: Any,
    ) -> Optional[Dict[str, Any]]:
        """检查当前时间是否匹配历史时间模式。"""
        now: Optional[datetime] = None

        if isinstance(current_time, (int, float)):
            try:
                ts = current_time
                if ts > 1e12:
                    ts = ts / 1000
                now = datetime.fromtimestamp(ts)
            except (OSError, ValueError):
                return None
        elif isinstance(current_time, str):
            for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%H:%M'):
                try:
                    now = datetime.strptime(current_time, fmt)
                    break
                except ValueError:
                    continue
            if now is None:
                return None

        if now is None:
            return None

        current_hour = now.hour

        for p in patterns:
            if p.get('pattern_type') != 'time_pattern':
                continue

            data_str = p.get('data', '{}')
            try:
                data = json.loads(data_str) if isinstance(data_str, str) else data_str
            except (json.JSONDecodeError, TypeError):
                continue

            peak_hours = data.get('peak_hours', {})
            if str(current_hour) in peak_hours:
                return {
                    'type': 'time_match',
                    'suggestion': f'当前时段 ({current_hour}:00) 是你的高频工作时段',
                    'confidence': p.get('confidence', 0.5) * 0.8,
                    'pattern_id': p.get('id', ''),
                }

        return None

    def _match_tool_sequence(
        self,
        patterns: List[Dict[str, Any]],
        recent_tools: List[str],
    ) -> Optional[Dict[str, Any]]:
        """检查最近工具使用是否匹配已知工作流。"""
        if not recent_tools:
            return None

        for p in patterns:
            if p.get('pattern_type') != 'workflow':
                continue

            data_str = p.get('data', '{}')
            try:
                data = json.loads(data_str) if isinstance(data_str, str) else data_str
            except (json.JSONDecodeError, TypeError):
                continue

            sequence = data.get('sequence', [])
            if not sequence or len(sequence) < 2:
                continue

            # 检查最近使用的工具是否是某个已知序列的前缀
            if self._is_prefix(recent_tools, sequence):
                remaining = sequence[len(recent_tools):]
                if remaining:
                    return {
                        'type': 'workflow_continuation',
                        'suggestion': f'根据习惯，你接下来可能需要: {" → ".join(remaining)}',
                        'remaining_tools': remaining,
                        'confidence': p.get('confidence', 0.5) * 0.6,
                        'pattern_id': p.get('id', ''),
                    }

        return None

    @staticmethod
    def _is_prefix(shorter: List[str], longer: List[str]) -> bool:
        """检查 shorter 是否是 longer 的前缀。"""
        if len(shorter) >= len(longer):
            return False
        return shorter == longer[:len(shorter)]

    @staticmethod
    def _is_subsequence(shorter: Tuple[str, ...], longer: Tuple[str, ...]) -> bool:
        """检查 shorter 是否是 longer 的连续子序列。"""
        if len(shorter) >= len(longer):
            return False
        shorter_str = '|'.join(shorter)
        longer_str = '|'.join(longer)
        return shorter_str in longer_str

    # ------------------------------------------------------------------
    # 内部方法 - 文本分析
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """使用简单 TF 方法提取关键词。"""
        if not text:
            return []

        # 提取英文单词 (3+ 字符)
        en_words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        # 提取中文词组 (2-4 字)
        zh_words = re.findall(r'[\u4e00-\u9fff]{2,4}', text)

        all_words = en_words + zh_words
        word_counts = Counter(
            w for w in all_words if w not in _STOP_WORDS and len(w) >= 2
        )

        return [w for w, _ in word_counts.most_common(top_n)]

    @staticmethod
    def _format_hour_range(hours: List[int]) -> str:
        """将小时列表格式化为人类可读的范围字符串。"""
        if not hours:
            return '未知'

        sorted_hours = sorted(set(hours))

        if len(sorted_hours) <= 2:
            return ', '.join(f'{h:02d}:00' for h in sorted_hours)

        # 合并为连续范围
        ranges: List[Tuple[int, int]] = []
        start = sorted_hours[0]
        end = sorted_hours[0]

        for h in sorted_hours[1:]:
            if h == end + 1:
                end = h
            else:
                ranges.append((start, end))
                start = h
                end = h
        ranges.append((start, end))

        parts: List[str] = []
        for s, e in ranges:
            if s == e:
                parts.append(f'{s:02d}:00')
            else:
                parts.append(f'{s:02d}:00-{e + 1:02d}:00')

        return ', '.join(parts)
