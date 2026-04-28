"""
LLM辅助偏好提取器 - 从对话中自动提取用户偏好

不依赖LLM时使用规则匹配降级。
Direction C: Personal Work Habits / Preference Memory.

策略:
  1. 中文模式匹配 - 识别偏好表达句式
  2. 工具调用推断 - 从使用模式推断隐含偏好
  3. 命令行工具检测 - 识别常用CLI工具偏好
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# 中文偏好表达模式
# 每条: (正则, category, key_template, default_confidence)
_CHINESE_PATTERNS: List[Tuple[str, str, str, float]] = [
    # 我更喜欢X / 我喜欢用X
    (r'我(?:更)?喜欢(?:用)?(.+?)(?:[，。,.]|$)', 'style', 'preference', 0.8),
    # 以后用X代替Y / 以后使用X替代Y
    (r'以后(?:用|使用)(.+?)(?:代替|替代|替换)(.+?)(?:[，。,.]|$)', 'tool', 'replacement', 0.9),
    # 每周X做Y / 每天X处理Y
    (r'(?:每周|每天|每月)(.{1,10}?)(?:做|处理|整理|写)(.+?)(?:[，。,.]|$)', 'schedule', 'periodic', 0.7),
    # 不要用X / 不要使用X
    (r'不要(?:用|使用)(.+?)(?:[，。,.]|$)', 'tool', 'avoid', 0.8),
    # X比Y好 / X比Y强 / X比Y快
    (r'(.+?)(?:比|比起来)(.+?)(?:好|强|快|方便)', 'tool', 'comparison', 0.7),
    # 优先用X / 首选X / 默认用X
    (r'(?:优先|首选|默认)(?:用|使用)?(.+?)(?:[，。,.]|$)', 'tool', 'default', 0.85),
    # 习惯X / 通常X / 一般X
    (r'(?:习惯|通常|一般)(.+?)(?:[，。,.]|$)', 'style', 'habit', 0.6),
    # 用X就好 / 用X就行
    (r'用(.+?)(?:就好|就行|就可以了)', 'tool', 'default', 0.75),
    # X比较好 / X更好
    (r'(.+?)(?:比较好|更好|最佳)', 'tool', 'preference', 0.7),
    # 希望X / 想要X
    (r'(?:希望|想要|需要)(?:用)?(.+?)(?:[，。,.]|$)', 'style', 'desire', 0.65),
]

# 英文偏好表达模式
_ENGLISH_PATTERNS: List[Tuple[str, str, str, float]] = [
    # I prefer X / I'd prefer X
    (r"(?:I(?:'d)?|we) prefer(?:\s+(?:to\s+)?)?(?:use\s+)?(.+?)(?:[.,;]|$)", 'style', 'preference', 0.8),
    # use X instead of Y / replace X with Y
    (r'use\s+(.+?)\s+(?:instead|rather)\s+(?:of|than)\s+(.+?)(?:[.,;]|$)', 'tool', 'replacement', 0.9),
    # don't use X / avoid X
    (r"(?:don't|do\s+not)\s+(?:use|want)\s+(.+?)(?:[.,;]|$)", 'tool', 'avoid', 0.8),
    # X is better than Y
    (r'(.+?)\s+(?:is|are)\s+better\s+(?:than|compared\s+to)\s+(.+?)(?:[.,;]|$)', 'tool', 'comparison', 0.7),
    # always use X / default to X
    (r'(?:always|default(?:\s+to)?)\s+(?:use\s+)?(.+?)(?:[.,;]|$)', 'tool', 'default', 0.85),
    # I'm used to X / I usually X
    (r"(?:I(?:'m)?|we(?:'re)?)\s+(?:used\s+to|usually|normally)\s+(.+?)(?:[.,;]|$)", 'style', 'habit', 0.6),
    # every X do Y (schedule)
    (r'every\s+(\w+)\s+(.+?)(?:[.,;]|$)', 'schedule', 'periodic', 0.7),
]

# CLI工具模式检测
_CLI_PATTERNS: List[Tuple[str, str, float]] = [
    (r'\bgit\s+(?:commit|push|pull|merge|rebase|checkout|branch|log|diff|add|stash)\b', 'git', 0.3),
    (r'\bdocker\s+(?:build|run|compose|exec|ps|logs|pull|push)\b', 'docker', 0.3),
    (r'\bkubectl\s+(?:get|apply|describe|delete|logs|exec|port-forward)\b', 'kubernetes', 0.3),
    (r'\bnpm\s+(?:install|run|start|build|test|publish)\b', 'npm', 0.3),
    (r'\byarn\s+(?:add|install|run|start|build|test)\b', 'yarn', 0.3),
    (r'\bpip\s+(?:install|list|freeze|show)\b', 'pip', 0.3),
    (r'\bpython3?\s+', 'python', 0.3),
    (r'\bcargo\s+(?:build|run|test|publish)\b', 'cargo', 0.3),
    (r'\bmake\s+', 'make', 0.3),
    (r'\bcurl\s+', 'curl', 0.3),
    (r'\bwget\s+', 'wget', 0.3),
    (r'\bsed\s+', 'sed', 0.3),
    (r'\bawk\s+', 'awk', 0.3),
    (r'\bvim\b|\bnano\b|\bcode\b', 'editor', 0.3),
    (r'\bssh\s+', 'ssh', 0.3),
    (r'\bscp\s+', 'scp', 0.3),
]


class PreferenceExtractor:
    """从对话和工具调用中自动提取用户偏好的规则引擎。"""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: SqliteStore 实例。
        """
        self.store = store

    def extract_from_conversation(
        self,
        user_msg: str,
        assistant_msg: str,
        owner: str,
    ) -> List[Dict[str, Any]]:
        """
        从对话中提取偏好三元组。

        Args:
            user_msg: 用户消息文本。
            assistant_msg: 助手回复文本。
            owner: 用户/agent ID。

        Returns:
            提取的偏好列表，每项包含:
            - category: 偏好类别
            - key: 偏好键
            - value: 偏好值
            - confidence: 置信度
            - source: 来源标识
            - raw_match: 原始匹配文本
        """
        if not user_msg or not user_msg.strip():
            return []

        preferences: List[Dict[str, Any]] = []
        text = user_msg.strip()

        # 1. 中文模式匹配
        preferences.extend(self._match_patterns(text, _CHINESE_PATTERNS, 'zh'))

        # 2. 英文模式匹配
        preferences.extend(self._match_patterns(text, _ENGLISH_PATTERNS, 'en'))

        # 3. CLI工具检测（从用户消息中）
        cli_prefs = self._detect_cli_tools(text, owner)
        preferences.extend(cli_prefs)

        # 4. 从助手回复中提取（如果包含工具调用）
        if assistant_msg:
            assistant_cli = self._detect_cli_tools(assistant_msg, owner)
            preferences.extend(assistant_cli)

        # 去重
        preferences = self._deduplicate_preferences(preferences)

        logger.debug(
            f"preference_extractor: extracted {len(preferences)} preferences "
            f"from conversation for owner={owner}"
        )
        return preferences

    def extract_from_tool_call(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        owner: str,
    ) -> List[Dict[str, Any]]:
        """
        从工具调用中推断偏好。

        通过工具名称和参数模式推断用户的工作习惯和偏好。

        Args:
            tool_name: 工具名称。
            tool_args: 工具参数字典。
            owner: 用户/agent ID。

        Returns:
            推断出的偏好列表。
        """
        if not tool_name:
            return []

        preferences: List[Dict[str, Any]] = []

        # 1. 工具使用频率偏好
        # 将工具使用记录为隐含的工具偏好
        preferences.append({
            'category': 'tool',
            'key': 'frequently_used',
            'value': tool_name,
            'confidence': 0.3,  # 单次使用，低置信度
            'source': 'observed',
            'raw_match': f'tool_call:{tool_name}',
        })

        # 2. 检测参数偏好模式
        param_prefs = self._analyze_tool_args(tool_name, tool_args)
        preferences.extend(param_prefs)

        # 3. 特定工具的深度分析
        tool_prefs = self._analyze_specific_tool(tool_name, tool_args)
        preferences.extend(tool_prefs)

        logger.debug(
            f"preference_extractor: extracted {len(preferences)} preferences "
            f"from tool call {tool_name} for owner={owner}"
        )
        return preferences

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _match_patterns(
        self,
        text: str,
        patterns: List[Tuple[str, str, str, float]],
        lang: str,
    ) -> List[Dict[str, Any]]:
        """对文本应用一组正则模式匹配。"""
        results: List[Dict[str, Any]] = []

        for pattern, category, key_template, default_confidence in patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if not groups:
                        continue

                    # 清理匹配结果
                    value = groups[0].strip()
                    if not value or len(value) < 2 or len(value) > 200:
                        continue

                    # 对于 replacement/comparison 类型，需要两个捕获组
                    if key_template in ('replacement', 'comparison') and len(groups) >= 2:
                        new_val = groups[0].strip()
                        old_val = groups[1].strip()
                        if new_val and old_val:
                            value = f"{new_val} > {old_val}"
                        else:
                            continue

                    # 生成 key
                    if key_template in ('preference', 'habit', 'desire'):
                        key = f"{key_template}_{lang}"
                    elif key_template == 'periodic':
                        # 从匹配中提取时间信息
                        key = f"periodic_{self._normalize_schedule(match.group(0))}"
                    else:
                        key = key_template

                    results.append({
                        'category': category,
                        'key': key,
                        'value': value,
                        'confidence': default_confidence,
                        'source': 'extracted',
                        'raw_match': match.group(0).strip(),
                    })
            except re.error as e:
                logger.warning(f"preference_extractor: regex error for pattern '{pattern}': {e}")
            except Exception as e:
                logger.warning(f"preference_extractor: match error: {e}")

        return results

    def _detect_cli_tools(
        self,
        text: str,
        owner: str,
    ) -> List[Dict[str, Any]]:
        """检测文本中出现的CLI工具使用。"""
        results: List[Dict[str, Any]] = []
        detected_tools: Dict[str, int] = {}

        for pattern, tool_name, weight in _CLI_PATTERNS:
            try:
                count = len(re.findall(pattern, text, re.IGNORECASE))
                if count > 0:
                    detected_tools[tool_name] = detected_tools.get(tool_name, 0) + count
            except re.error:
                continue

        for tool_name, count in detected_tools.items():
            # 多次出现增加置信度
            confidence = min(0.3 + count * 0.1, 0.8)
            results.append({
                'category': 'tool',
                'key': f'cli_{tool_name}',
                'value': tool_name,
                'confidence': confidence,
                'source': 'observed',
                'raw_match': f'cli_detected:{tool_name}({count}x)',
            })

        return results

    def _analyze_tool_args(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """分析工具参数，提取参数级偏好。"""
        results: List[Dict[str, Any]] = []

        if not tool_args:
            return results

        # 检测编辑器偏好
        editor_keys = {'editor', 'EDITOR', 'editor_name'}
        for k in editor_keys:
            if k in tool_args:
                results.append({
                    'category': 'tool',
                    'key': 'editor',
                    'value': str(tool_args[k]),
                    'confidence': 0.5,
                    'source': 'observed',
                    'raw_match': f'editor_arg:{tool_args[k]}',
                })
                break

        # 检测 shell 偏好
        shell_keys = {'shell', 'SHELL', 'interpreter'}
        for k in shell_keys:
            if k in tool_args:
                results.append({
                    'category': 'tool',
                    'key': 'shell',
                    'value': str(tool_args[k]),
                    'confidence': 0.5,
                    'source': 'observed',
                    'raw_match': f'shell_arg:{tool_args[k]}',
                })
                break

        # 检测 verbose/quiet 模式偏好
        if tool_args.get('verbose') or tool_args.get('-v') or tool_args.get('--verbose'):
            results.append({
                'category': 'style',
                'key': 'verbosity',
                'value': 'verbose',
                'confidence': 0.4,
                'source': 'observed',
                'raw_match': 'verbose_flag',
            })

        # 检测 output format 偏好
        fmt_keys = {'format', 'output', 'output_format', '-o', '--output'}
        for k in fmt_keys:
            if k in tool_args:
                fmt_val = str(tool_args[k])
                if fmt_val in ('json', 'yaml', 'csv', 'table', 'text', 'xml'):
                    results.append({
                        'category': 'style',
                        'key': 'output_format',
                        'value': fmt_val,
                        'confidence': 0.5,
                        'source': 'observed',
                        'raw_match': f'format_arg:{fmt_val}',
                    })
                    break

        return results

    def _analyze_specific_tool(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """针对特定工具进行深度参数分析。"""
        results: List[Dict[str, Any]] = []

        if not tool_args:
            return results

        tool_lower = tool_name.lower()

        # Git 特定分析
        if 'git' in tool_lower:
            cmd = tool_args.get('command', tool_args.get('cmd', ''))
            if isinstance(cmd, str):
                # 检测 merge vs rebase 偏好
                if 'rebase' in cmd:
                    results.append({
                        'category': 'workflow',
                        'key': 'git_merge_strategy',
                        'value': 'rebase',
                        'confidence': 0.5,
                        'source': 'observed',
                        'raw_match': f'git_rebase',
                    })
                elif 'merge' in cmd:
                    results.append({
                        'category': 'workflow',
                        'key': 'git_merge_strategy',
                        'value': 'merge',
                        'confidence': 0.4,
                        'source': 'observed',
                        'raw_match': f'git_merge',
                    })

        # 包管理器分析
        if tool_lower in ('npm', 'yarn', 'pnpm'):
            results.append({
                'category': 'tool',
                'key': 'js_package_manager',
                'value': tool_lower,
                'confidence': 0.5,
                'source': 'observed',
                'raw_match': f'pkg_mgr:{tool_lower}',
            })

        # Python 包管理器
        if tool_lower in ('pip', 'pip3', 'conda', 'poetry', 'uv'):
            results.append({
                'category': 'tool',
                'key': 'py_package_manager',
                'value': tool_lower,
                'confidence': 0.5,
                'source': 'observed',
                'raw_match': f'py_pkg_mgr:{tool_lower}',
            })

        # 编程语言偏好
        if tool_lower in ('python', 'python3', 'node', 'deno', 'bun',
                          'rustc', 'cargo', 'go', 'javac', 'gcc', 'g++',
                          'clang', 'clang++'):
            results.append({
                'category': 'tool',
                'key': 'programming_language',
                'value': tool_lower,
                'confidence': 0.4,
                'source': 'observed',
                'raw_match': f'lang:{tool_lower}',
            })

        return results

    def _normalize_schedule(self, text: str) -> str:
        """规范化调度描述。"""
        text_lower = text.lower()
        if '每天' in text_lower or 'daily' in text_lower:
            return 'daily'
        elif '每周' in text_lower or 'weekly' in text_lower:
            return 'weekly'
        elif '每月' in text_lower or 'monthly' in text_lower:
            return 'monthly'
        return 'periodic'

    def _deduplicate_preferences(
        self,
        preferences: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """对提取的偏好去重，保留最高置信度的。"""
        seen: Dict[str, Dict[str, Any]] = {}

        for pref in preferences:
            dedup_key = f"{pref['category']}:{pref['key']}:{pref['value']}"
            if dedup_key not in seen or pref['confidence'] > seen[dedup_key]['confidence']:
                seen[dedup_key] = pref

        return list(seen.values())
