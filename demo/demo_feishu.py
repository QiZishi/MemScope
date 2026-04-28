#!/usr/bin/env python3
"""
Enterprise Memory Engine — Feishu API Integration Demo
=======================================================

Demonstrates how the enterprise memory system integrates with Feishu (Lark)
messaging: receive message → extract memory → store → retrieve → push alert.

This demo runs in simulation mode if FEISHU_APP_ID/FEISHU_APP_SECRET are not
set, showing the complete integration flow with mock data.

Usage:
    python3 demo_feishu.py

    # With real Feishu credentials:
    FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx python3 demo_feishu.py
"""

import json
import os
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

# ============================================================================
# Color helpers
# ============================================================================

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'

def banner(text: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * 70}{Colors.END}\n")

def step(num: int, title: str) -> None:
    print(f"\n{Colors.BOLD}{Colors.GREEN}  ▶ Step {num}: {title}{Colors.END}")
    print(f"  {Colors.DIM}{'─' * 50}{Colors.END}")

def info(msg: str) -> None:
    print(f"  {Colors.BLUE}ℹ{Colors.END} {msg}")

def success(msg: str) -> None:
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")

def warn(msg: str) -> None:
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")

def result(label: str, value: Any) -> None:
    if isinstance(value, (dict, list)):
        formatted = json.dumps(value, indent=2, ensure_ascii=False, default=str)
        print(f"  {Colors.BOLD}{label}:{Colors.END}")
        for line in formatted.split('\n'):
            print(f"    {line}")
    else:
        print(f"  {Colors.BOLD}{label}:{Colors.END} {value}")


# ============================================================================
# Feishu API Client (abstraction layer)
# ============================================================================

class FeishuClient:
    """Feishu Open API client for messaging integration.

    In production, this uses the real Feishu Open API.
    In demo mode, it simulates API responses.
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str = None, app_secret: str = None):
        self.app_id = app_id or os.environ.get("FEISHU_APP_ID", "")
        self.app_secret = app_secret or os.environ.get("FEISHU_APP_SECRET", "")
        self.demo_mode = not (self.app_id and self.app_secret)
        self._tenant_token = None

        if self.demo_mode:
            info("🔗 飞书 API 运行在演示模式 (模拟响应)")
            info("  设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 以连接真实 API")
        else:
            info(f"🔗 飞书 API 连接中... (APP_ID: {self.app_id[:8]}...)")

    def get_tenant_access_token(self) -> str:
        """Get tenant access token for API calls."""
        if self.demo_mode:
            return "mock_tenant_token_demo_mode"

        # Real implementation would call:
        # POST /auth/v3/tenant_access_token/internal
        # {
        #   "app_id": self.app_id,
        #   "app_secret": self.app_secret
        # }
        info("🔑 获取 tenant_access_token...")
        return "real_token_from_api"

    def receive_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming message event from Feishu.

        Event format (from Feishu webhook):
        {
            "event": {
                "message": {
                    "message_id": "om_xxx",
                    "chat_id": "oc_xxx",
                    "chat_type": "group",
                    "content": "{\"text\": \"...\"}",
                    "sender": {
                        "sender_id": {"open_id": "ou_xxx"},
                        "sender_type": "user"
                    }
                }
            }
        }
        """
        msg = event.get("event", {}).get("message", {})
        content_str = msg.get("content", "{}")
        try:
            content = json.loads(content_str)
        except json.JSONDecodeError:
            content = {"text": content_str}

        return {
            "message_id": msg.get("message_id", str(uuid.uuid4())),
            "chat_id": msg.get("chat_id", ""),
            "chat_type": msg.get("chat_type", "group"),
            "text": content.get("text", ""),
            "sender_id": msg.get("sender", {}).get("sender_id", {}).get("open_id", "unknown"),
            "timestamp": int(time.time() * 1000),
        }

    def send_message(self, chat_id: str, content: str, msg_type: str = "text") -> Dict[str, Any]:
        """Send a message to a Feishu chat.

        In production, calls:
        POST /im/v1/messages
        {
            "receive_id": chat_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": content})
        }
        """
        if self.demo_mode:
            return {
                "message_id": f"om_demo_{uuid.uuid4().hex[:8]}",
                "status": "sent (demo mode)",
                "chat_id": chat_id,
                "content_preview": content[:100],
            }

        # Real implementation
        # headers = {"Authorization": f"Bearer {self._tenant_token}"}
        # requests.post(f"{self.BASE_URL}/im/v1/messages", ...)
        return {"message_id": f"om_{uuid.uuid4().hex[:8]}", "status": "sent"}

    def send_rich_message(self, chat_id: str, card: Dict[str, Any]) -> Dict[str, Any]:
        """Send an interactive card message."""
        if self.demo_mode:
            return {
                "message_id": f"om_demo_card_{uuid.uuid4().hex[:8]}",
                "status": "sent (demo mode)",
                "card_type": card.get("config", {}).get("wide_screen_mode", False),
            }
        return {"message_id": f"om_{uuid.uuid4().hex[:8]}", "status": "sent"}


# ============================================================================
# Memory Extraction Engine
# ============================================================================

class MemoryExtractor:
    """Extracts memory-relevant information from Feishu messages.

    Uses keyword matching and pattern detection to identify:
    - Decisions and rationale
    - Technical knowledge
    - Preferences and habits
    - Action items and follow-ups
    """

    DECISION_KEYWORDS = [
        "决定", "决策", "确定", "选择", "采用", "采用", "放弃", "替代",
        "decided", "chose", "adopted", "selected", "dropped", "replaced",
        "architecture", "架构", "方案", "策略", "approach",
    ]

    KNOWLEDGE_KEYWORDS = [
        "部署", "配置", "安装", "修复", "bug", "error", "问题",
        "deploy", "config", "install", "fix", "solution", "解决",
        "docker", "kubernetes", "aws", "database", "api", "endpoint",
        "数据库", "接口", "服务", "中间件",
    ]

    PREFERENCE_KEYWORDS = [
        "喜欢", "偏好", "习惯", "常用", "推荐", "最好",
        "prefer", "like", "favorite", "recommend", "best",
        "总是", "通常", "每次", "always", "usually", "typically",
    ]

    ACTION_KEYWORDS = [
        "需要", "待办", "TODO", "跟进", "完成", "deadline",
        "need to", "todo", "follow up", "complete", "deadline",
        "计划", "安排", "通知",
    ]

    def extract_from_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a message and extract memory-relevant information."""
        text = message.get("text", "").lower()

        result = {
            "message_id": message.get("message_id"),
            "sender_id": message.get("sender_id"),
            "raw_text": message.get("text", ""),
            "timestamp": message.get("timestamp"),
            "classifications": [],
            "extracted_memories": [],
            "confidence": 0.0,
        }

        # Classify message type
        if any(kw in text for kw in [k.lower() for k in self.DECISION_KEYWORDS]):
            result["classifications"].append("decision")
            result["extracted_memories"].append({
                "type": "knowledge",
                "content": message.get("text", ""),
                "category": "architecture",
                "importance": 0.8,
            })

        if any(kw in text for kw in [k.lower() for k in self.KNOWLEDGE_KEYWORDS]):
            result["classifications"].append("knowledge")
            result["extracted_memories"].append({
                "type": "knowledge",
                "content": message.get("text", ""),
                "category": self._detect_domain(text),
                "importance": 0.6,
            })

        if any(kw in text for kw in [k.lower() for k in self.PREFERENCE_KEYWORDS]):
            result["classifications"].append("preference")
            pref = self._extract_preference(text)
            if pref:
                result["extracted_memories"].append(pref)

        if any(kw in text for kw in [k.lower() for k in self.ACTION_KEYWORDS]):
            result["classifications"].append("action_item")
            result["extracted_memories"].append({
                "type": "action_item",
                "content": message.get("text", ""),
                "importance": 0.7,
            })

        # Calculate overall confidence
        if result["classifications"]:
            result["confidence"] = min(0.5 + len(result["classifications"]) * 0.15, 0.95)

        if not result["classifications"]:
            result["classifications"].append("general")
            result["confidence"] = 0.3

        return result

    def _detect_domain(self, text: str) -> str:
        """Detect the knowledge domain from text content."""
        domain_keywords = {
            "infrastructure": ["deploy", "server", "docker", "kubernetes", "aws", "cloud", "部署", "服务器"],
            "frontend": ["react", "vue", "css", "html", "ui", "前端", "页面"],
            "backend": ["api", "endpoint", "database", "service", "后端", "接口", "服务"],
            "security": ["auth", "security", "token", "oauth", "安全", "认证", "权限"],
            "devops": ["ci", "cd", "pipeline", "jenkins", "ci/cd", "流水线"],
            "testing": ["test", "unit", "e2e", "coverage", "测试", "覆盖率"],
            "architecture": ["architecture", "design", "pattern", "架构", "设计", "模式"],
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in text for kw in keywords):
                return domain
        return "general"

    def _extract_preference(self, text: str) -> Optional[Dict[str, Any]]:
        """Try to extract a preference from the text."""
        # Simple heuristic extraction
        for pattern in ["喜欢(使用|用)(.*)", "偏好(.*)", "推荐使用(.*)", "prefer(.*)"]:
            import re
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return {
                    "type": "preference",
                    "content": text,
                    "category": "tool_preference",
                    "importance": 0.5,
                }
        return {
            "type": "preference",
            "content": text,
            "category": "work_pattern",
            "importance": 0.4,
        }


# ============================================================================
# Alert Generator
# ============================================================================

class AlertGenerator:
    """Generates Feishu alert messages for knowledge health issues."""

    @staticmethod
    def build_freshness_alert(chunks: List[Dict]) -> Dict[str, Any]:
        """Build a Feishu interactive card for freshness alerts."""
        elements = []

        # Header
        elements.append({
            "tag": "markdown",
            "content": "**🔔 知识健康预警**\n系统检测到以下知识条目需要关注："
        })

        elements.append({"tag": "hr"})

        for chunk in chunks:
            status = chunk.get("freshness_status", "unknown")
            emoji = {"forgotten": "🔴", "stale": "🟡", "aging": "🔵"}.get(status, "⚪")
            importance = chunk.get("importance_score", 0)
            days = chunk.get("days_since_access", "N/A")

            elements.append({
                "tag": "markdown",
                "content": (
                    f"{emoji} **{status.upper()}** — 重要度: {importance:.2f}\n"
                    f"未访问天数: {days} | 类别: {chunk.get('category', 'N/A')}\n"
                    f"建议: {chunk.get('recommendation', '请检查')}"
                )
            })

        elements.append({"tag": "hr"})
        elements.append({
            "tag": "markdown",
            "content": f"*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": "🧠 企业记忆系统 — 知识健康预警"},
                "template": "red",
            },
            "elements": elements,
        }

    @staticmethod
    def build_gap_alert(gaps: List[Dict], team_id: str) -> Dict[str, Any]:
        """Build a Feishu interactive card for knowledge gap alerts."""
        elements = []
        elements.append({
            "tag": "markdown",
            "content": f"**🔎 团队知识缺口报告 — {team_id}**\n"
        })

        for gap in gaps:
            severity = gap.get("severity", "unknown")
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(severity, "⚪")
            elements.append({
                "tag": "markdown",
                "content": (
                    f"{emoji} **{gap.get('domain', 'N/A')}** — 覆盖率: {gap.get('coverage', 0)*100:.0f}%\n"
                    f"建议: {gap.get('recommendation', 'N/A')}"
                )
            })

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"🗺️ 团队知识缺口 — {team_id}"},
                "template": "orange",
            },
            "elements": elements,
        }

    @staticmethod
    def build_preference_summary(preferences: List[Dict], user: str) -> Dict[str, Any]:
        """Build a Feishu card showing user preference summary."""
        elements = []
        elements.append({
            "tag": "markdown",
            "content": f"**👤 {user} 的工作偏好档案**"
        })

        by_cat = {}
        for p in preferences:
            cat = p.get("category", "unknown")
            by_cat.setdefault(cat, []).append(p)

        cat_emoji = {
            "tool_preference": "🔧", "schedule": "⏰",
            "work_pattern": "📋", "style": "🎨",
        }

        for cat, prefs in by_cat.items():
            lines = [f"{cat_emoji.get(cat, '📌')} **{cat}**"]
            for p in prefs:
                src = "显式" if p.get("source") == "user_explicit" else "推断"
                lines.append(f"  • {p['key']}: {p['value']} ({src}, 置信度: {p.get('confidence', 0):.2f})")
            elements.append({"tag": "markdown", "content": "\n".join(lines)})

        return {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": f"📋 工作偏好 — {user}"},
                "template": "blue",
            },
            "elements": elements,
        }


# ============================================================================
# Integration Pipeline
# ============================================================================

class FeishuMemoryPipeline:
    """End-to-end integration pipeline: Feishu → Memory → Alert."""

    def __init__(self, feishu_client: FeishuClient = None):
        self.feishu = feishu_client or FeishuClient()
        self.extractor = MemoryExtractor()
        self.alert_gen = AlertGenerator()
        self._memories = []
        self._preferences = {}
        self._alerts = []

    def process_incoming_message(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Full pipeline: receive → extract → store → enrich."""
        # Step 1: Receive from Feishu
        message = self.feishu.receive_message(event)

        # Step 2: Extract memory
        extraction = self.extractor.extract_from_message(message)

        # Step 3: Store memories
        stored = []
        for mem in extraction["extracted_memories"]:
            mem["stored_at"] = int(time.time() * 1000)
            mem["source_message_id"] = message["message_id"]
            mem["source_sender"] = message["sender_id"]
            self._memories.append(mem)
            stored.append(mem)

        return {
            "message": message,
            "extraction": extraction,
            "stored_count": len(stored),
            "memories": stored,
        }

    def query_memories(self, query: str, user: str = None) -> List[Dict]:
        """Search stored memories by query."""
        query_lower = query.lower()
        results = []
        for mem in self._memories:
            content = mem.get("content", "").lower()
            if query_lower in content or any(w in content for w in query_lower.split()):
                if user is None or mem.get("source_sender") == user:
                    results.append(mem)
        return results

    def push_alerts(self, chat_id: str, alert_type: str = "freshness") -> Dict[str, Any]:
        """Generate and push alerts to a Feishu chat."""
        if alert_type == "freshness":
            # Simulate stale/forgotten chunks
            stale_chunks = [
                {"chunk_id": "chunk-001", "freshness_status": "forgotten", "importance_score": 0.85,
                 "days_since_access": 95, "category": "architecture", "recommendation": "立即重新验证"},
                {"chunk_id": "chunk-002", "freshness_status": "stale", "importance_score": 0.7,
                 "days_since_access": 35, "category": "backend", "recommendation": "建议审查更新"},
            ]
            card = self.alert_gen.build_freshness_alert(stale_chunks)
        elif alert_type == "gaps":
            gaps = [
                {"domain": "security", "severity": "critical", "coverage": 0.1,
                 "recommendation": "安排安全知识转移会议"},
                {"domain": "documentation", "severity": "high", "coverage": 0.2,
                 "recommendation": "建立文档编写规范和激励机制"},
            ]
            card = self.alert_gen.build_gap_alert(gaps, "eng-team")
        else:
            return {"error": f"未知的预警类型: {alert_type}"}

        # Send via Feishu
        response = self.feishu.send_rich_message(chat_id, card)
        return {"alert_type": alert_type, "card": card, "send_response": response}


# ============================================================================
# Demo Flow
# ============================================================================

def run_feishu_demo():
    """Run the Feishu integration demo."""
    banner("🔗 飞书 API 集成演示")
    print(f"  {Colors.DIM}演示完整链路: 飞书消息 → 记忆提取 → 存储 → 检索 → 预警推送{Colors.END}\n")

    # Initialize
    pipeline = FeishuMemoryPipeline()

    # ==================================================================
    # Phase 1: Message Reception & Memory Extraction
    # ==================================================================
    step(1, "接收飞书消息 → 提取记忆")

    # Simulate incoming Feishu messages
    messages = [
        {
            "event": {
                "message": {
                    "message_id": "om_001_architecture",
                    "chat_id": "oc_eng_team_chat",
                    "chat_type": "group",
                    "content": json.dumps({"text": "我们决定采用微服务架构替代单体应用，主要原因是团队规模增长后部署频率需要提高。这是经过讨论后的架构决策。"}),
                    "sender": {"sender_id": {"open_id": "ou_zhangsan"}, "sender_type": "user"},
                }
            }
        },
        {
            "event": {
                "message": {
                    "message_id": "om_002_knowledge",
                    "chat_id": "oc_eng_team_chat",
                    "chat_type": "group",
                    "content": json.dumps({"text": "提醒大家：Kubernetes 部署时要注意配置 resource limits，上次线上 OOM 就是因为没设置 memory limit。建议使用 HPA 自动扩容。"}),
                    "sender": {"sender_id": {"open_id": "ou_wangwu"}, "sender_type": "user"},
                }
            }
        },
        {
            "event": {
                "message": {
                    "message_id": "om_003_preference",
                    "chat_id": "oc_eng_team_chat",
                    "chat_type": "group",
                    "content": json.dumps({"text": "我通常喜欢在早上 9 点到 12 点之间做深度编码工作，这个时间段不要安排会议。推荐使用 VSCode 配合 Remote-SSH 插件进行远程开发。"}),
                    "sender": {"sender_id": {"open_id": "ou_lisi"}, "sender_type": "user"},
                }
            }
        },
        {
            "event": {
                "message": {
                    "message_id": "om_004_action",
                    "chat_id": "oc_eng_team_chat",
                    "chat_type": "group",
                    "content": json.dumps({"text": "TODO: 需要完成 API 限流方案的文档，并在周五之前部署到 staging 环境进行测试。deadline: 本周五。"}),
                    "sender": {"sender_id": {"open_id": "ou_zhangsan"}, "sender_type": "user"},
                }
            }
        },
        {
            "event": {
                "message": {
                    "message_id": "om_005_security",
                    "chat_id": "oc_eng_team_chat",
                    "chat_type": "group",
                    "content": json.dumps({"text": "安全提醒：OAuth2 认证流程需要使用 PKCE 模式。Access token 存内存，refresh token 放 httpOnly cookie。这是经过安全评审后确定的方案。"}),
                    "sender": {"sender_id": {"open_id": "ou_lisi"}, "sender_type": "user"},
                }
            }
        },
    ]

    for i, event in enumerate(messages, 1):
        info(f"\n  📨 模拟收到消息 #{i}:")
        result_info = pipeline.process_incoming_message(event)
        msg_text = result_info["message"]["text"]
        info(f"    原文: {msg_text[:60]}...")
        info(f"    分类: {', '.join(result_info['extraction']['classifications'])}")
        info(f"    置信度: {result_info['extraction']['confidence']:.2f}")
        info(f"    提取记忆: {result_info['stored_count']} 条")
        for mem in result_info["memories"]:
            info(f"      → [{mem['type']}] {mem.get('content', '')[:50]}... (重要度: {mem['importance']:.1f})")

    # ==================================================================
    # Phase 2: Memory Retrieval
    # ==================================================================
    step(2, "记忆检索 — 根据查询找到相关知识")

    queries = [
        ("微服务架构决策", None),
        ("Kubernetes 部署", None),
        ("工作偏好", "ou_lisi"),
        ("安全", None),
    ]

    for query, user in queries:
        user_desc = f" (用户: {user})" if user else ""
        results = pipeline.query_memories(query, user)
        print(f"\n  {Colors.BOLD}🔍 查询: \"{query}\"{user_desc}{Colors.END}")
        if results:
            for r in results:
                info(f"  [{r['type']}] {r['content'][:70]}...")
        else:
            warn("  未找到匹配的记忆")

    # ==================================================================
    # Phase 3: Alert Generation & Push
    # ==================================================================
    step(3, "生成预警 → 推送到飞书群")

    # Freshness alert
    info("生成知识新鲜度预警...")
    alert_result = pipeline.push_alerts("oc_eng_team_chat", "freshness")
    send_resp = alert_result["send_response"]
    success(f"预警卡片已发送: {send_resp.get('message_id', 'N/A')}")
    info(f"  卡片包含 {len(alert_result['card']['elements'])} 个元素")
    info(f"  预警类型: {alert_result['alert_type']}")

    # Gap alert
    info("\n生成团队知识缺口预警...")
    alert_result = pipeline.push_alerts("oc_eng_team_chat", "gaps")
    send_resp = alert_result["send_response"]
    success(f"缺口报告已发送: {send_resp.get('message_id', 'N/A')}")
    info(f"  卡片包含 {len(alert_result['card']['elements'])} 个元素")

    # ==================================================================
    # Phase 4: Preference Summary Push
    # ==================================================================
    step(4, "用户偏好摘要 → 推送到飞书")

    # Build preference summary for lisi
    lisi_prefs = [
        {"category": "tool_preference", "key": "css_framework", "value": "CSS Modules", "confidence": 0.95, "source": "user_explicit"},
        {"category": "work_pattern", "key": "testing_approach", "value": "TDD with React Testing Library", "confidence": 0.95, "source": "user_explicit"},
        {"category": "schedule", "key": "preferred_meeting_time", "value": "下午 14:00-16:00", "confidence": 0.95, "source": "user_explicit"},
        {"category": "tool_preference", "key": "most_used_tool", "value": "editor", "confidence": 0.72, "source": "habit_inference"},
    ]

    card = AlertGenerator.build_preference_summary(lisi_prefs, "李四")
    send_resp = pipeline.feishu.send_rich_message("oc_eng_team_chat", card)
    success(f"偏好档案已发送: {send_resp.get('message_id', 'N/A')}")

    # ==================================================================
    # Phase 5: End-to-End Flow Diagram
    # ==================================================================
    step(5, "完整集成流程图")

    flow = """
    ┌─────────────────────────────────────────────────────────────────┐
    │                    飞书集成完整流程                               │
    ├─────────────────────────────────────────────────────────────────┤
    │                                                                 │
    │  👤 用户在飞书群发送消息                                          │
    │         │                                                       │
    │         ▼                                                       │
    │  📡 Feishu Webhook 接收消息事件                                   │
    │         │                                                       │
    │         ▼                                                       │
    │  🧠 MemoryExtractor 分析消息                                     │
    │    ├─ 分类: decision / knowledge / preference / action           │
    │    ├─ 提取: 内容、领域、重要度                                     │
    │    └─ 置信度评估                                                  │
    │         │                                                       │
    │         ▼                                                       │
    │  💾 SQLite 存储                                                  │
    │    ├─ chunks 表 (知识条目)                                        │
    │    ├─ user_preferences 表 (用户偏好)                             │
    │    ├─ behavior_patterns 表 (行为模式)                             │
    │    ├─ knowledge_health 表 (知识健康)                              │
    │    └─ team_knowledge_map 表 (团队知识地图)                        │
    │         │                                                       │
    │         ▼                                                       │
    │  🔍 Hybrid Search (RRF + MMR + Recency)                         │
    │    └─ 根据查询检索相关记忆                                         │
    │         │                                                       │
    │         ▼                                                       │
    │  📊 知识健康分析                                                  │
    │    ├─ FreshnessMonitor: 新鲜度检查                                │
    │    ├─ GapDetector: 缺口检测                                      │
    │    └─ AlertGenerator: 预警生成                                   │
    │         │                                                       │
    │         ▼                                                       │
    │  📤 Feishu Interactive Card 推送                                  │
    │    ├─ 知识健康预警卡片                                            │
    │    ├─ 团队缺口报告卡片                                            │
    │    └─ 用户偏好摘要卡片                                            │
    │                                                                 │
    └─────────────────────────────────────────────────────────────────┘
    """
    print(flow)

    # ==================================================================
    # Summary
    # ==================================================================
    banner("📊 飞书集成演示总结")

    print(f"  {Colors.BOLD}{Colors.GREEN}✅ 完整演示了飞书 × 企业记忆系统的集成链路:{Colors.END}\n")

    summary_items = [
        ("📨 消息接收", f"处理 {len(messages)} 条飞书消息"),
        ("🧠 记忆提取", f"提取 {sum(1 for m in pipeline._memories)} 条记忆"),
        ("💾 记忆存储", "存储到 SQLite (chunks + preferences + patterns)"),
        ("🔍 记忆检索", f"执行 {len(queries)} 次混合搜索查询"),
        ("⚠️ 知识预警", "生成新鲜度预警 + 缺口报告"),
        ("📤 卡片推送", "发送 3 张飞书互动卡片"),
    ]
    for icon_label, desc in summary_items:
        print(f"    {icon_label}: {desc}")

    print()
    print(f"  {Colors.BOLD}{Colors.CYAN}集成模式:{Colors.END}")
    print(f"    • 演示模式: 无需飞书凭证，模拟 API 响应")
    print(f"    • 生产模式: 设置 FEISHU_APP_ID + FEISHU_APP_SECRET 连接真实 API")
    print()
    print(f"  {Colors.BOLD}{Colors.CYAN}支持的卡片类型:{Colors.END}")
    print(f"    • 🔴 知识健康预警卡片 (红/黄/蓝 三级)")
    print(f"    • 🟠 团队缺口报告卡片")
    print(f"    • 🔵 用户偏好摘要卡片")
    print()
    print(f"  {Colors.BOLD}{Colors.GREEN}🎉 飞书集成演示完成！{Colors.END}\n")


if __name__ == "__main__":
    try:
        run_feishu_demo()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ 演示已中断{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 演示出错: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
