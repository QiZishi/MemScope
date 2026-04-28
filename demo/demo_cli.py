#!/usr/bin/env python3
"""
Enterprise Memory Engine — CLI Demo Script
==========================================

Demonstrates all 9 enterprise memory tools:
  1. preference_set     — Set user preferences (Direction C)
  2. preference_get     — Retrieve a specific preference (Direction C)
  3. preference_list    — List all preferences (Direction C)
  4. habit_patterns     — Infer behavior patterns (Direction C)
  5. knowledge_health   — Check knowledge freshness (Direction D)
  6. knowledge_gaps     — Detect team knowledge gaps (Direction D)
  7. knowledge_alerts   — Generate knowledge alerts (Direction D)
  8. team_knowledge_map — Build team knowledge map (Direction D)
  9. knowledge_freshness — Monitor freshness lifecycle (Direction D)

Usage:
    python3 demo_cli.py

No external dependencies required — uses only Python standard library.
"""

import json
import os
import sqlite3
import sys
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

# ============================================================================
# Color helpers for terminal output
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
    """Print a section banner."""
    width = 70
    print()
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * width}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}  {text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'═' * width}{Colors.END}")
    print()

def step(num: int, title: str) -> None:
    """Print a step header."""
    print(f"\n{Colors.BOLD}{Colors.GREEN}  ▶ Step {num}: {title}{Colors.END}")
    print(f"  {Colors.DIM}{'─' * 50}{Colors.END}")

def info(msg: str) -> None:
    """Print an info message."""
    print(f"  {Colors.BLUE}ℹ{Colors.END} {msg}")

def success(msg: str) -> None:
    """Print a success message."""
    print(f"  {Colors.GREEN}✓{Colors.END} {msg}")

def warn(msg: str) -> None:
    """Print a warning message."""
    print(f"  {Colors.YELLOW}⚠{Colors.END} {msg}")

def error(msg: str) -> None:
    """Print an error message."""
    print(f"  {Colors.RED}✗{Colors.END} {msg}")

def result(label: str, value: Any) -> None:
    """Print a labeled result."""
    if isinstance(value, (dict, list)):
        formatted = json.dumps(value, indent=2, ensure_ascii=False, default=str)
        # Indent continuation lines
        lines = formatted.split('\n')
        print(f"  {Colors.BOLD}{label}:{Colors.END}")
        for line in lines:
            print(f"    {line}")
    else:
        print(f"  {Colors.BOLD}{label}:{Colors.END} {value}")

def data_table(headers: List[str], rows: List[List[str]]) -> None:
    """Print a simple data table."""
    if not rows:
        print(f"  {Colors.DIM}(空){Colors.END}")
        return
    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(cell)))
    # Print header
    header_line = " │ ".join(f"{Colors.BOLD}{h:<{col_widths[i]}}{Colors.END}" for i, h in enumerate(headers))
    sep_line = "─┼─".join("─" * w for w in col_widths)
    print(f"  {header_line}")
    print(f"  {Colors.DIM}{sep_line}{Colors.END}")
    # Print rows
    for row in rows:
        line = " │ ".join(f"{str(row[i]):<{col_widths[i]}}" if i < len(col_widths) else str(row[i]) for i in range(len(row)))
        print(f"  {line}")


# ============================================================================
# Schema v2 — Enterprise memory tables (inline for demo self-containment)
# ============================================================================

SCHEMA_V2_SQL = """
-- Schema version tracking
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at INTEGER NOT NULL,
    description TEXT
);

-- User preferences (Direction C)
CREATE TABLE IF NOT EXISTS user_preferences (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    category TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    evidence_count INTEGER DEFAULT 1,
    source TEXT,
    createdAt INTEGER NOT NULL,
    updatedAt INTEGER NOT NULL,
    UNIQUE(owner, category, key)
);
CREATE INDEX IF NOT EXISTS idx_pref_owner ON user_preferences(owner);
CREATE INDEX IF NOT EXISTS idx_pref_category ON user_preferences(category);

-- Behavior patterns (Direction C)
CREATE TABLE IF NOT EXISTS behavior_patterns (
    id TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    pattern_type TEXT NOT NULL,
    description TEXT NOT NULL,
    data TEXT,
    confidence REAL DEFAULT 0.5,
    sample_count INTEGER DEFAULT 0,
    createdAt INTEGER NOT NULL,
    updatedAt INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bp_owner ON behavior_patterns(owner);

-- Knowledge health (Direction D)
CREATE TABLE IF NOT EXISTS knowledge_health (
    id TEXT PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    team_id TEXT,
    importance_score REAL DEFAULT 0.5,
    last_accessed_at INTEGER,
    access_count INTEGER DEFAULT 0,
    freshness_status TEXT DEFAULT 'fresh',
    last_verified_at INTEGER,
    category TEXT
);
CREATE INDEX IF NOT EXISTS idx_kh_chunk ON knowledge_health(chunk_id);
CREATE INDEX IF NOT EXISTS idx_kh_team ON knowledge_health(team_id);
CREATE INDEX IF NOT EXISTS idx_kh_status ON knowledge_health(freshness_status);

-- Team knowledge map (Direction D)
CREATE TABLE IF NOT EXISTS team_knowledge_map (
    id TEXT PRIMARY KEY,
    team_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    description TEXT,
    member_coverage TEXT,
    overall_coverage REAL DEFAULT 0.0,
    gap_areas TEXT,
    last_analysis_at INTEGER,
    createdAt INTEGER NOT NULL,
    updatedAt INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tkm_team ON team_knowledge_map(team_id);
"""


# ============================================================================
# Demo Database — Lightweight store for demo purposes
# ============================================================================

class DemoStore:
    """Simple SQLite store wrapping the schema_v2 tables."""

    def __init__(self, db_path: str = ":memory:"):
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._apply_schema()

    def _apply_schema(self):
        self.conn.executescript(SCHEMA_V2_SQL)
        self.conn.commit()

    def close(self):
        self.conn.close()

    # --- User Preferences ---
    def upsert_user_preference(self, owner, category, key, value, confidence=0.5, source=None):
        pref_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        self.conn.execute("""
            INSERT INTO user_preferences (id, owner, category, key, value, confidence, evidence_count, source, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(owner, category, key) DO UPDATE SET
                value = excluded.value,
                confidence = CASE WHEN excluded.confidence > user_preferences.confidence THEN excluded.confidence ELSE user_preferences.confidence END,
                evidence_count = user_preferences.evidence_count + 1,
                source = COALESCE(excluded.source, user_preferences.source),
                updatedAt = excluded.updatedAt
        """, (pref_id, owner, category, key, value, confidence, source, now, now))
        self.conn.commit()
        return pref_id

    def get_user_preference(self, owner, category, key):
        cur = self.conn.execute("SELECT * FROM user_preferences WHERE owner=? AND category=? AND key=?", (owner, category, key))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_user_preferences(self, owner, category=None, min_confidence=0.0, limit=100):
        conditions = ["owner=?", "confidence>=?"]
        params = [owner, min_confidence]
        if category:
            conditions.append("category=?")
            params.append(category)
        where = " AND ".join(conditions)
        cur = self.conn.execute(f"SELECT * FROM user_preferences WHERE {where} ORDER BY confidence DESC LIMIT ?", params + [limit])
        return [dict(r) for r in cur.fetchall()]

    def delete_user_preference(self, owner, category, key):
        cur = self.conn.execute("DELETE FROM user_preferences WHERE owner=? AND category=? AND key=?", (owner, category, key))
        self.conn.commit()
        return cur.rowcount > 0

    def decay_preference_confidence(self, decay_factor=0.95, min_confidence=0.1):
        now = int(time.time() * 1000)
        cur = self.conn.execute(
            "UPDATE user_preferences SET confidence=MAX(confidence*?,?), updatedAt=? WHERE confidence>?",
            (decay_factor, min_confidence, now, min_confidence)
        )
        self.conn.commit()
        return cur.rowcount

    # --- Behavior Patterns ---
    def insert_behavior_pattern(self, owner, pattern_type, description, data=None, confidence=0.5, sample_count=0):
        pattern_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        self.conn.execute(
            "INSERT INTO behavior_patterns (id, owner, pattern_type, description, data, confidence, sample_count, createdAt, updatedAt) VALUES (?,?,?,?,?,?,?,?,?)",
            (pattern_id, owner, pattern_type, description, json.dumps(data) if data else None, confidence, sample_count, now, now)
        )
        self.conn.commit()
        return pattern_id

    def get_behavior_patterns(self, owner, pattern_type=None, limit=20):
        if pattern_type:
            cur = self.conn.execute("SELECT * FROM behavior_patterns WHERE owner=? AND pattern_type=? ORDER BY confidence DESC LIMIT ?", (owner, pattern_type, limit))
        else:
            cur = self.conn.execute("SELECT * FROM behavior_patterns WHERE owner=? ORDER BY confidence DESC LIMIT ?", (owner, limit))
        results = []
        for r in cur.fetchall():
            d = dict(r)
            if d.get("data"):
                try:
                    d["data"] = json.loads(d["data"])
                except (json.JSONDecodeError, TypeError):
                    pass
            results.append(d)
        return results

    # --- Knowledge Health ---
    def upsert_knowledge_health(self, chunk_id, team_id=None, importance_score=0.5, freshness_status="fresh", category=None):
        health_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        self.conn.execute("""
            INSERT INTO knowledge_health (id, chunk_id, team_id, importance_score, last_accessed_at, access_count, freshness_status, last_verified_at, category)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
            ON CONFLICT(chunk_id) DO UPDATE SET importance_score=excluded.importance_score, freshness_status=excluded.freshness_status
        """, (health_id, chunk_id, team_id, importance_score, now, freshness_status, now, category))
        self.conn.commit()
        return health_id

    def record_knowledge_access(self, chunk_id):
        now = int(time.time() * 1000)
        self.conn.execute("""
            UPDATE knowledge_health SET last_accessed_at=?, access_count=access_count+1,
            freshness_status=CASE WHEN freshness_status IN ('stale','forgotten') THEN 'aging' ELSE freshness_status END
            WHERE chunk_id=?
        """, (now, chunk_id))
        self.conn.commit()

    def get_knowledge_health(self, chunk_id):
        cur = self.conn.execute("SELECT * FROM knowledge_health WHERE chunk_id=?", (chunk_id,))
        row = cur.fetchone()
        return dict(row) if row else None

    def list_knowledge_health(self, team_id=None, status_filter=None, limit=20):
        conditions, params = [], []
        if team_id:
            conditions.append("team_id=?")
            params.append(team_id)
        if status_filter:
            conditions.append("freshness_status=?")
            params.append(status_filter)
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = self.conn.execute(f"SELECT * FROM knowledge_health {where} ORDER BY importance_score DESC LIMIT ?", params + [limit])
        return [dict(r) for r in cur.fetchall()]

    def get_knowledge_alerts(self, team_id=None, alert_type="all", limit=20):
        conditions, params = [], []
        if team_id:
            conditions.append("kh.team_id=?")
            params.append(team_id)
        if alert_type == "stale":
            conditions.append("kh.freshness_status='stale'")
        elif alert_type == "forgotten":
            conditions.append("kh.freshness_status='forgotten'")
        elif alert_type == "degraded":
            conditions.append("kh.freshness_status IN ('stale','forgotten')")
        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        cur = self.conn.execute(f"""
            SELECT kh.*, c.summary, c.content, c.owner, c.visibility
            FROM knowledge_health kh LEFT JOIN chunks c ON kh.chunk_id = c.id
            {where} ORDER BY kh.importance_score DESC, kh.last_accessed_at ASC LIMIT ?
        """, params + [limit])
        results = []
        for row in cur.fetchall():
            d = dict(row)
            status = d.get("freshness_status", "fresh")
            if status == "stale":
                d["alert_message"] = f"⚠️ 知识过期 (重要度: {d.get('importance_score',0):.2f})，建议验证或更新"
            elif status == "forgotten":
                d["alert_message"] = f"🔴 知识被遗忘 (重要度: {d.get('importance_score',0):.2f})，长期未访问"
            elif status == "aging":
                d["alert_message"] = f"🔵 知识老化中 (重要度: {d.get('importance_score',0):.2f})，可能需要审查"
            results.append(d)
        return results

    # --- Team Knowledge Map ---
    def upsert_team_knowledge_map(self, team_id, domain, description=None, member_coverage=None, overall_coverage=0.0, gap_areas=None):
        map_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        cur = self.conn.execute("SELECT id FROM team_knowledge_map WHERE team_id=? AND domain=?", (team_id, domain))
        existing = cur.fetchone()
        if existing:
            map_id = existing[0]
            self.conn.execute(
                "UPDATE team_knowledge_map SET description=?, member_coverage=?, overall_coverage=?, gap_areas=?, last_analysis_at=?, updatedAt=? WHERE id=?",
                (description, json.dumps(member_coverage) if member_coverage else None, overall_coverage,
                 json.dumps(gap_areas) if gap_areas else None, now, now, map_id)
            )
        else:
            self.conn.execute(
                "INSERT INTO team_knowledge_map (id, team_id, domain, description, member_coverage, overall_coverage, gap_areas, last_analysis_at, createdAt, updatedAt) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (map_id, team_id, domain, description, json.dumps(member_coverage) if member_coverage else None,
                 overall_coverage, json.dumps(gap_areas) if gap_areas else None, now, now, now)
            )
        self.conn.commit()
        return map_id

    def get_team_knowledge_map(self, team_id):
        cur = self.conn.execute("SELECT * FROM team_knowledge_map WHERE team_id=? ORDER BY overall_coverage ASC", (team_id,))
        rows = cur.fetchall()
        if not rows:
            return None
        domains = []
        for row in rows:
            d = dict(row)
            for field in ("member_coverage", "gap_areas"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            domains.append(d)
        total_domains = len(domains)
        avg_coverage = sum(d.get("overall_coverage", 0) for d in domains) / total_domains if total_domains else 0
        return {
            "team_id": team_id,
            "total_domains": total_domains,
            "average_coverage": round(avg_coverage, 3),
            "low_coverage_domains": sum(1 for d in domains if d.get("overall_coverage", 0) < 0.5),
            "domains": domains,
        }

    def list_knowledge_gaps(self, team_id, domain=None, min_severity="low"):
        severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        min_sev = severity_order.get(min_severity, 0)
        conditions, params = ["team_id=?"], [team_id]
        if domain:
            conditions.append("domain=?")
            params.append(domain)
        where = " AND ".join(conditions)
        cur = self.conn.execute(f"SELECT * FROM team_knowledge_map WHERE {where} ORDER BY overall_coverage ASC", params)
        results = []
        for row in cur.fetchall():
            d = dict(row)
            for field in ("member_coverage", "gap_areas"):
                if d.get(field):
                    try:
                        d[field] = json.loads(d[field])
                    except (json.JSONDecodeError, TypeError):
                        pass
            coverage = d.get("overall_coverage", 1.0)
            if coverage < 0.2:
                severity = "critical"
            elif coverage < 0.4:
                severity = "high"
            elif coverage < 0.6:
                severity = "medium"
            else:
                severity = "low"
            d["severity"] = severity
            sev = severity_order.get(severity, 0)
            if sev >= min_sev:
                if coverage < 0.2:
                    d["recommendation"] = f"🔴 严重缺口 ({domain or d.get('domain','')})：仅 {coverage*100:.0f}% 覆盖率，建议立即安排知识转移"
                elif coverage < 0.4:
                    d["recommendation"] = f"🟡 低覆盖 ({domain or d.get('domain','')})：{coverage*100:.0f}% 覆盖率，鼓励团队成员记录经验"
                elif coverage < 0.6:
                    d["recommendation"] = f"🟠 中等缺口 ({domain or d.get('domain','')})：{coverage*100:.0f}% 覆盖率，建议配对学习"
                results.append(d)
        results.sort(key=lambda x: severity_order.get(x.get("severity","low"), 0), reverse=True)
        return results

    # --- Chunks (for alert joins) ---
    def insert_chunk(self, chunk_id, content, summary=None, owner=None, visibility="shared"):
        now = int(time.time() * 1000)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY, content TEXT, summary TEXT,
                owner TEXT, visibility TEXT, createdAt INTEGER, updatedAt INTEGER
            )
        """)
        self.conn.execute(
            "INSERT OR REPLACE INTO chunks (id, content, summary, owner, visibility, createdAt, updatedAt) VALUES (?,?,?,?,?,?,?)",
            (chunk_id, content, summary, owner, visibility, now, now)
        )
        self.conn.commit()


# ============================================================================
# Demo scenario data
# ============================================================================

def seed_demo_data(store: DemoStore):
    """Seed the database with realistic demo data."""
    info("正在初始化演示数据...")

    # --- User 1: 张三 (后端工程师) ---
    zhangsan_chunks = [
        ("chunk-zs-001", "Kubernetes deployment strategy: use rolling updates with maxSurge=1 and maxUnavailable=0 for zero-downtime deployments. Always test with staging cluster first.",
         "K8s 部署策略", "zhangsan"),
        ("chunk-zs-002", "Backend API rate limiting: implemented token bucket algorithm with Redis backend. Rate limits: 100 req/min for standard, 1000 req/min for premium users.",
         "API 限流实现", "zhangsan"),
        ("chunk-zs-003", "Database migration strategy for PostgreSQL: always use backward-compatible migrations. Never rename columns directly — create new column, migrate data, then drop old.",
         "数据库迁移策略", "zhangsan"),
        ("chunk-zs-004", "CI/CD pipeline optimization: parallelized test stages reduced build time from 15min to 6min. Key insight: separate unit tests from integration tests.",
         "CI/CD 优化", "zhangsan"),
        ("chunk-zs-005", "Architecture decision: chose message queue (RabbitMQ) over direct HTTP calls for inter-service communication. Reason: better fault tolerance and async processing.",
         "架构决策 — 消息队列", "zhangsan"),
    ]

    # --- User 2: 李四 (前端工程师) ---
    lisi_chunks = [
        ("chunk-ls-001", "React component optimization: use React.memo with custom comparator. Avoid re-rendering by structuring state at the lowest common ancestor. useMemo for expensive calculations.",
         "React 性能优化", "lisi"),
        ("chunk-ls-002", "CSS architecture decision: adopted CSS Modules over styled-components. Rationale: better build-time optimization, native browser debugging, smaller bundle size.",
         "CSS 架构决策", "lisi"),
        ("chunk-ls-003", "Frontend testing strategy: Cypress for E2E tests, React Testing Library for unit tests. Never test implementation details — test user behavior.",
         "前端测试策略", "lisi"),
        ("chunk-ls-004", "Authentication flow: implemented PKCE OAuth2 flow for SPA. Token refresh happens 5 minutes before expiry. Access token stored in memory, refresh token in httpOnly cookie.",
         "OAuth2 认证流程", "lisi"),
    ]

    # --- User 3: 王五 (DevOps工程师) ---
    wangwu_chunks = [
        ("chunk-ww-001", "Terraform module for AWS ECS: standardized deployment with Fargate. Includes auto-scaling policies based on CPU/memory metrics. CloudWatch alarms for error rate > 1%.",
         "Terraform ECS 模块", "wangwu"),
        ("chunk-ww-002", "Monitoring stack: Prometheus + Grafana for metrics, ELK for logs, PagerDuty for alerting. SLO target: 99.9% uptime, p99 latency < 200ms.",
         "监控技术栈", "wangwu"),
        ("chunk-ww-003", "Secrets management: migrated from environment variables to AWS Secrets Manager. Rotation policy: database passwords every 30 days, API keys every 90 days.",
         "密钥管理", "wangwu"),
    ]

    # Insert all chunks
    for chunks in [zhangsan_chunks, lisi_chunks, wangwu_chunks]:
        for chunk_id, content, summary, owner in chunks:
            store.insert_chunk(chunk_id, content, summary, owner)

    # --- Knowledge health records with different freshness statuses ---
    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000

    health_entries = [
        # Fresh knowledge
        ("chunk-zs-001", "eng-team", 0.8, "fresh", "devops"),
        ("chunk-ls-001", "eng-team", 0.75, "fresh", "frontend"),
        ("chunk-ww-001", "eng-team", 0.85, "fresh", "infrastructure"),
        # Aging knowledge
        ("chunk-zs-002", "eng-team", 0.7, "aging", "backend"),
        ("chunk-ls-003", "eng-team", 0.65, "aging", "testing"),
        # Stale knowledge (not accessed for 35 days)
        ("chunk-zs-003", "eng-team", 0.6, "stale", "backend"),
        ("chunk-ls-004", "eng-team", 0.7, "stale", "security"),
        # Forgotten knowledge (not accessed for 95 days)
        ("chunk-zs-005", "eng-team", 0.9, "forgotten", "architecture"),
        ("chunk-ww-003", "eng-team", 0.5, "forgotten", "security"),
    ]

    for chunk_id, team_id, importance, status, category in health_entries:
        health_id = str(uuid.uuid4())
        # Set timestamps based on freshness status
        if status == "fresh":
            last_access = now_ms - 3 * day_ms
        elif status == "aging":
            last_access = now_ms - 18 * day_ms
        elif status == "stale":
            last_access = now_ms - 35 * day_ms
        else:  # forgotten
            last_access = now_ms - 95 * day_ms

        store.conn.execute("""
            INSERT OR REPLACE INTO knowledge_health
            (id, chunk_id, team_id, importance_score, last_accessed_at, access_count, freshness_status, last_verified_at, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (health_id, chunk_id, team_id, importance, last_access,
              10 if status == "fresh" else 3 if status == "stale" else 1,
              status, last_access, category))
    store.conn.commit()

    # --- Team knowledge map entries ---
    team_map_data = [
        ("infrastructure", "基础设施与云服务", {"zhangsan": 8, "wangwu": 12}, 0.667,
         [{"issue": "li si lacks infra knowledge", "coverage": 0.667}]),
        ("frontend", "前端开发", {"lisi": 10}, 0.333,
         [{"issue": "Only lisi covers frontend", "coverage": 0.333}]),
        ("backend", "后端服务", {"zhangsan": 7, "lisi": 2}, 0.667, None),
        ("security", "安全", {"lisi": 3}, 0.333,
         [{"issue": "Only lisi covers security", "coverage": 0.333}]),
        ("devops", "DevOps", {"wangwu": 8}, 0.333,
         [{"issue": "Only wangwu covers devops", "coverage": 0.333}]),
        ("architecture", "系统架构", {"zhangsan": 2}, 0.333,
         [{"issue": "Only zhangsan has architecture knowledge", "coverage": 0.333}]),
        ("testing", "测试", {"lisi": 5, "zhangsan": 2}, 0.667, None),
        ("documentation", "文档", {}, 0.0,
         [{"issue": "No documentation coverage", "coverage": 0.0}]),
        ("data", "数据工程", {}, 0.0,
         [{"issue": "No data engineering coverage", "coverage": 0.0}]),
        ("product", "产品", {}, 0.0,
         [{"issue": "No product knowledge coverage", "coverage": 0.0}]),
    ]

    for domain, desc, member_cov, overall, gaps in team_map_data:
        store.upsert_team_knowledge_map(
            team_id="eng-team",
            domain=domain,
            description=f"知识领域: {desc}",
            member_coverage=member_cov,
            overall_coverage=overall,
            gap_areas=gaps,
        )

    success("演示数据初始化完成")
    info("  👤 用户: zhangsan (后端), lisi (前端), wangwu (DevOps)")
    info("  🏢 团队: eng-team (3 人)")
    info(f"  📦 知识条目: {len(zhangsan_chunks) + len(lisi_chunks) + len(wangwu_chunks)} 条")
    info("  🗺️  知识领域: 10 个")


# ============================================================================
# Tool implementations (wrapper functions for the 9 tools)
# ============================================================================

def tool_preference_set(store: DemoStore, owner: str, category: str, key: str, value: str, source: str = "user_explicit"):
    """Tool 1: preference_set — Set a user preference."""
    confidence = 0.95 if source == "user_explicit" else 0.6
    pref_id = store.upsert_user_preference(owner, category, key, value, confidence, source)
    return {"id": pref_id, "owner": owner, "category": category, "key": key, "value": value, "confidence": confidence, "source": source}

def tool_preference_get(store: DemoStore, owner: str, category: str, key: str):
    """Tool 2: preference_get — Retrieve a specific preference."""
    pref = store.get_user_preference(owner, category, key)
    return pref or {"error": f"偏好不存在: {owner}/{category}/{key}"}

def tool_preference_list(store: DemoStore, owner: str, category: str = None):
    """Tool 3: preference_list — List all preferences for a user."""
    prefs = store.list_user_preferences(owner, category)
    by_cat = {}
    for p in prefs:
        cat = p.get("category", "unknown")
        by_cat.setdefault(cat, []).append(p)
    return {"owner": owner, "total": len(prefs), "by_category": by_cat, "preferences": prefs}

def tool_habit_patterns(store: DemoStore, owner: str):
    """Tool 4: habit_patterns — Infer and retrieve behavior patterns."""
    # Simulate habit inference from stored patterns
    patterns = store.get_behavior_patterns(owner)
    return {"owner": owner, "total_patterns": len(patterns), "patterns": patterns}

def tool_knowledge_health(store: DemoStore, team_id: str = None):
    """Tool 5: knowledge_health — Check knowledge freshness status."""
    all_health = store.list_knowledge_health(team_id, limit=100)
    status_counts = {}
    for h in all_health:
        s = h.get("freshness_status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1
    return {
        "team_id": team_id,
        "total_entries": len(all_health),
        "status_distribution": status_counts,
        "entries": all_health,
    }

def tool_knowledge_gaps(store: DemoStore, team_id: str, domain: str = None):
    """Tool 6: knowledge_gaps — Detect team knowledge gaps."""
    gaps = store.list_knowledge_gaps(team_id, domain)
    return {"team_id": team_id, "total_gaps": len(gaps), "gaps": gaps}

def tool_knowledge_alerts(store: DemoStore, team_id: str = None, alert_type: str = "all"):
    """Tool 7: knowledge_alerts — Get knowledge health alerts."""
    alerts = store.get_knowledge_alerts(team_id, alert_type)
    return {"team_id": team_id, "alert_type": alert_type, "total_alerts": len(alerts), "alerts": alerts}

def tool_team_knowledge_map(store: DemoStore, team_id: str):
    """Tool 8: team_knowledge_map — Get the team knowledge map."""
    tkm = store.get_team_knowledge_map(team_id)
    if not tkm:
        return {"error": f"团队 {team_id} 的知识地图为空"}
    return tkm

def tool_knowledge_freshness(store: DemoStore, team_id: str = None):
    """Tool 9: knowledge_freshness — Monitor knowledge freshness lifecycle."""
    health = store.list_knowledge_health(team_id, limit=100)
    now_ms = int(time.time() * 1000)
    day_ms = 86400 * 1000

    lifecycle = {"fresh": [], "aging": [], "stale": [], "forgotten": []}
    for entry in health:
        status = entry.get("freshness_status", "fresh")
        last_accessed = entry.get("last_accessed_at", 0)
        days_since = (now_ms - last_accessed) / day_ms if last_accessed else None

        lifecycle_item = {
            "chunk_id": entry.get("chunk_id"),
            "category": entry.get("category"),
            "importance": entry.get("importance_score", 0),
            "days_since_access": round(days_since, 1) if days_since else None,
        }
        lifecycle.setdefault(status, []).append(lifecycle_item)

    # Generate recommendations
    recommendations = []
    for entry in health:
        status = entry.get("freshness_status", "fresh")
        importance = entry.get("importance_score", 0.5)
        if status == "forgotten" and importance > 0.7:
            recommendations.append(f"🔴 高重要度知识被遗忘 (importance={importance:.2f})，建议立即重新验证")
        elif status == "stale" and importance > 0.6:
            recommendations.append(f"🟡 中等重要度知识过期 (importance={importance:.2f})，建议审查更新")

    return {
        "team_id": team_id,
        "total_entries": len(health),
        "lifecycle": {k: len(v) for k, v in lifecycle.items()},
        "details": lifecycle,
        "recommendations": recommendations,
    }


# ============================================================================
# Main demo flow
# ============================================================================

def run_demo():
    """Run the full enterprise memory demo."""
    banner("🧠 企业级长期协作记忆系统 — CLI 演示")
    print(f"  {Colors.DIM}Feishu OpenClaw 大赛参赛作品{Colors.END}")
    print(f"  {Colors.DIM}Enterprise-level Long-term Collaboration Memory System{Colors.END}")
    print()

    # Initialize
    db_path = "/tmp/enterprise_memory_demo.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    store = DemoStore(db_path)
    info(f"数据库已初始化: {db_path}")

    # Seed data
    print()
    seed_demo_data(store)

    # ==================================================================
    # Tool 1: preference_set
    # ==================================================================
    step(1, "preference_set — 设置用户偏好 (方向 C)")

    info("张三设置显式偏好...")
    r = tool_preference_set(store, "zhangsan", "tool_preference", "ide", "VSCode")
    success(f"设置: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']})")

    r = tool_preference_set(store, "zhangsan", "schedule", "deep_work_time", "09:00-12:00")
    success(f"设置: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']})")

    r = tool_preference_set(store, "zhangsan", "work_pattern", "code_review_style", "detailed with suggestions")
    success(f"设置: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']})")

    r = tool_preference_set(store, "zhangsan", "style", "documentation_language", "中文为主，技术术语英文")
    success(f"设置: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']})")

    info("系统自动推断偏好...")
    r = tool_preference_set(store, "zhangsan", "tool_preference", "most_used_tool", "terminal", source="habit_inference")
    success(f"推断: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']}, 来源: 习惯推断)")

    r = tool_preference_set(store, "zhangsan", "schedule", "peak_active_hours", "09:00-12:00, 14:00-17:00", source="habit_inference")
    success(f"推断: {r['category']}/{r['key']} = {r['value']} (置信度: {r['confidence']}, 来源: 习惯推断)")

    info("李四设置偏好...")
    tool_preference_set(store, "lisi", "tool_preference", "css_framework", "CSS Modules")
    tool_preference_set(store, "lisi", "work_pattern", "testing_approach", "TDD with React Testing Library")
    tool_preference_set(store, "lisi", "schedule", "preferred_meeting_time", "下午 14:00-16:00")
    success("李四的偏好已设置 (3 项)")

    # ==================================================================
    # Tool 2: preference_get
    # ==================================================================
    step(2, "preference_get — 查询单个偏好")

    r = tool_preference_get(store, "zhangsan", "tool_preference", "ide")
    result("查询结果", r)

    r = tool_preference_get(store, "zhangsan", "schedule", "deep_work_time")
    result("查询结果", r)

    r = tool_preference_get(store, "zhangsan", "tool_preference", "nonexistent")
    result("查询不存在的偏好", r)

    # ==================================================================
    # Tool 3: preference_list
    # ==================================================================
    step(3, "preference_list — 列出所有偏好")

    r = tool_preference_list(store, "zhangsan")
    print(f"\n  {Colors.BOLD}📊 张三的偏好概览:{Colors.END}")
    data_table(
        ["类别", "键", "值", "置信度", "来源"],
        [
            [p.get("category", ""), p.get("key", ""), p.get("value", "")[:30],
             f"{p.get('confidence', 0):.2f}", p.get("source", "")]
            for p in r["preferences"]
        ]
    )
    info(f"总计: {r['total']} 项偏好")

    r = tool_preference_list(store, "lisi", category="tool_preference")
    print(f"\n  {Colors.BOLD}📊 李四的工具偏好:{Colors.END}")
    for p in r["preferences"]:
        print(f"    • {p['key']}: {p['value']} (置信度: {p['confidence']:.2f})")

    # ==================================================================
    # Tool 4: habit_patterns
    # ==================================================================
    step(4, "habit_patterns — 习惯推断分析 (方向 C)")

    # Simulate habit inference by inserting patterns
    info("模拟行为数据采集 (500 条工具日志)...")

    patterns_data = [
        ("time_pattern", "最活跃时段: 09:00-12:00, 14:00-17:00", {"peak_hours": {"9": 85, "10": 92, "11": 78, "14": 71, "15": 68}, "total_samples": 500}, 0.88, 500),
        ("tool_frequency", "常用工具: terminal (180×), browser (95×), editor (85×), git (72×), docker (45×)", {"tool_ranking": {"terminal": 180, "browser": 95, "editor": 85, "git": 72, "docker": 45}}, 0.82, 500),
        ("topic_cluster", "高频主题: 'kubernetes' (12 条相关记忆)", {"keyword": "kubernetes", "cluster_size": 12}, 0.75, 12),
        ("topic_cluster", "高频主题: 'deployment' (9 条相关记忆)", {"keyword": "deployment", "cluster_size": 9}, 0.68, 9),
        ("workflow", "重复工作流 (8×): terminal → editor → terminal → git", {"sequence": ["terminal", "editor", "terminal", "git"], "occurrence_count": 8}, 0.72, 8),
    ]

    for ptype, desc, data, conf, samples in patterns_data:
        store.insert_behavior_pattern("zhangsan", ptype, desc, data, conf, samples)

    r = tool_habit_patterns(store, "zhangsan")
    print(f"\n  {Colors.BOLD}🧩 张三的行为模式 ({r['total_patterns']} 条):{Colors.END}")
    for p in r["patterns"]:
        ptype_emoji = {"time_pattern": "⏰", "tool_frequency": "🔧", "topic_cluster": "📚", "workflow": "🔄"}.get(p["pattern_type"], "📊")
        print(f"    {ptype_emoji} [{p['pattern_type']}] {p['description']}")
        print(f"       {Colors.DIM}置信度: {p['confidence']:.2f} | 样本数: {p['sample_count']}{Colors.END}")

    # ==================================================================
    # Tool 5: knowledge_health
    # ==================================================================
    step(5, "knowledge_health — 知识健康状态检查 (方向 D)")

    r = tool_knowledge_health(store, "eng-team")
    print(f"\n  {Colors.BOLD}🩺 团队知识健康概览:{Colors.END}")
    result("状态分布", r["status_distribution"])
    result("总条目", r["total_entries"])

    print(f"\n  {Colors.BOLD}📋 各条目详情:{Colors.END}")
    data_table(
        ["Chunk ID", "类别", "重要度", "状态", "访问次数"],
        [
            [e.get("chunk_id", "")[:20], e.get("category", ""), f"{e.get('importance_score', 0):.2f}",
             e.get("freshness_status", ""), str(e.get("access_count", 0))]
            for e in r["entries"]
        ]
    )

    # ==================================================================
    # Tool 6: knowledge_gaps
    # ==================================================================
    step(6, "knowledge_gaps — 团队知识缺口检测")

    r = tool_knowledge_gaps(store, "eng-team")
    print(f"\n  {Colors.BOLD}🔎 检测到 {r['total_gaps']} 个知识缺口:{Colors.END}")
    for gap in r["gaps"]:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(gap["severity"], "⚪")
        print(f"\n    {severity_emoji} [{gap['severity'].upper()}] {gap['domain']}")
        print(f"       覆盖率: {gap.get('overall_coverage', 0) * 100:.0f}%")
        print(f"       有知识的成员: {', '.join(gap.get('members_with_knowledge', [])) or '无'}")
        print(f"       建议: {gap.get('recommendation', '')}")

    # Focus on specific domain
    r = tool_knowledge_gaps(store, "eng-team", domain="security")
    result("安全领域缺口分析", r["gaps"] if r["gaps"] else "无数据")

    # ==================================================================
    # Tool 7: knowledge_alerts
    # ==================================================================
    step(7, "knowledge_alerts — 知识预警推送")

    r = tool_knowledge_alerts(store, "eng-team")
    print(f"\n  {Colors.BOLD}⚠️ 收到 {r['total_alerts']} 条预警:{Colors.END}")
    for alert in r["alerts"]:
        status = alert.get("freshness_status", "")
        emoji = {"forgotten": "🔴", "stale": "🟡", "aging": "🔵"}.get(status, "⚪")
        print(f"\n    {emoji} {alert.get('alert_message', '')}")
        print(f"       {Colors.DIM}Chunk: {alert.get('chunk_id', 'N/A')} | 类别: {alert.get('category', 'N/A')}{Colors.END}")

    # Filter for forgotten only
    r = tool_knowledge_alerts(store, "eng-team", alert_type="forgotten")
    print(f"\n  {Colors.BOLD}🔴 仅被遗忘的知识 ({r['total_alerts']} 条):{Colors.END}")
    for alert in r["alerts"]:
        print(f"    • {alert.get('alert_message', '')}")

    # ==================================================================
    # Tool 8: team_knowledge_map
    # ==================================================================
    step(8, "team_knowledge_map — 团队知识地图")

    r = tool_team_knowledge_map(store, "eng-team")
    print(f"\n  {Colors.BOLD}🗺️  团队知识地图 — {r['team_id']}{Colors.END}")
    print(f"    总领域数: {r['total_domains']}")
    print(f"    平均覆盖率: {r['average_coverage'] * 100:.1f}%")
    print(f"    低覆盖率领域: {r['low_coverage_domains']} 个")

    print(f"\n  {Colors.BOLD}📊 各领域覆盖详情:{Colors.END}")
    data_table(
        ["领域", "覆盖率", "有知识的成员", "缺口等级"],
        [
            [d.get("domain", ""), f"{d.get('overall_coverage', 0) * 100:.0f}%",
             ", ".join(d.get("members_with_knowledge", [])) if "members_with_knowledge" in d else
             ", ".join(d.get("member_coverage", {}).keys()) if d.get("member_coverage") else "无",
             "✅" if d.get("overall_coverage", 0) >= 0.6 else "⚠️" if d.get("overall_coverage", 0) >= 0.3 else "🔴"]
            for d in r["domains"]
        ]
    )

    # Visual coverage bar chart
    print(f"\n  {Colors.BOLD}📈 覆盖率可视化:{Colors.END}")
    for d in r["domains"]:
        domain = d.get("domain", "")
        coverage = d.get("overall_coverage", 0)
        bar_len = int(coverage * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)
        color = Colors.GREEN if coverage >= 0.6 else Colors.YELLOW if coverage >= 0.3 else Colors.RED
        print(f"    {domain:<15} {color}{bar}{Colors.END} {coverage*100:.0f}%")

    # ==================================================================
    # Tool 9: knowledge_freshness
    # ==================================================================
    step(9, "knowledge_freshness — 新鲜度生命周期监控")

    r = tool_knowledge_freshness(store, "eng-team")
    print(f"\n  {Colors.BOLD}🌊 知识新鲜度生命周期:{Colors.END}")
    for status, count in r["lifecycle"].items():
        emoji = {"fresh": "🟢", "aging": "🔵", "stale": "🟡", "forgotten": "🔴"}.get(status, "⚪")
        print(f"    {emoji} {status}: {count} 条")

    if r["recommendations"]:
        print(f"\n  {Colors.BOLD}📋 系统建议:{Colors.END}")
        for rec in r["recommendations"]:
            print(f"    {rec}")

    # Detail per status
    for status in ["forgotten", "stale"]:
        entries = r["details"].get(status, [])
        if entries:
            print(f"\n  {Colors.BOLD}{'🔴' if status == 'forgotten' else '🟡'} {status.upper()} 知识详情:{Colors.END}")
            for e in entries:
                print(f"    • Chunk: {e['chunk_id']} | 类别: {e['category']} | 重要度: {e['importance']:.2f} | 未访问: {e['days_since_access']:.0f} 天")

    # ==================================================================
    # Bonus: Preference Decay Simulation
    # ==================================================================
    banner("🔄 附加演示: 偏好置信度衰减")
    info("模拟时间推移，展示偏好置信度衰减机制...")
    info("衰减前:")
    prefs_before = tool_preference_list(store, "zhangsan")
    for p in prefs_before["preferences"][:3]:
        info(f"  {p['key']}: 置信度 = {p['confidence']:.4f}")

    # Apply multiple rounds of decay
    for i in range(5):
        store.decay_preference_confidence(decay_factor=0.9)

    info("衰减后 (5 轮 × 0.9):")
    prefs_after = tool_preference_list(store, "zhangsan")
    for p in prefs_after["preferences"][:3]:
        info(f"  {p['key']}: 置信度 = {p['confidence']:.4f}")

    # ==================================================================
    # Summary
    # ==================================================================
    banner("📊 演示总结")

    print(f"  {Colors.BOLD}{Colors.GREEN}✅ 成功演示了全部 9 个企业级记忆工具:{Colors.END}")
    print()
    tools_summary = [
        ("1. preference_set",     "C", "设置用户偏好 (显式 + 推断)"),
        ("2. preference_get",     "C", "查询单个偏好"),
        ("3. preference_list",    "C", "列出用户所有偏好"),
        ("4. habit_patterns",     "C", "行为模式推断分析"),
        ("5. knowledge_health",   "D", "知识健康状态检查"),
        ("6. knowledge_gaps",     "D", "团队知识缺口检测"),
        ("7. knowledge_alerts",   "D", "知识预警推送"),
        ("8. team_knowledge_map", "D", "团队知识地图"),
        ("9. knowledge_freshness","D", "新鲜度生命周期监控"),
    ]
    data_table(
        ["工具", "方向", "说明"],
        [[t[0], t[1], t[2]] for t in tools_summary]
    )
    print()
    print(f"  {Colors.BOLD}{Colors.CYAN}方向 C — 个人工作习惯记忆:{Colors.END}")
    print(f"    • 6 项偏好 (4 显式 + 2 推断)")
    print(f"    • 5 种行为模式 (时间、工具、主题、工作流)")
    print()
    print(f"  {Colors.BOLD}{Colors.CYAN}方向 D — 团队知识健康:{Colors.END}")
    print(f"    • 9 条知识条目监控 (3 fresh, 2 aging, 2 stale, 2 forgotten)")
    print(f"    • 5 个知识缺口 (2 critical, 3 high)")
    print(f"    • 9 条预警推送")
    print(f"    • 10 个领域的知识地图")
    print()

    # Cleanup
    store.close()
    if os.path.exists(db_path):
        os.remove(db_path)

    print(f"  {Colors.BOLD}{Colors.GREEN}🎉 演示完成！{Colors.END}")
    print(f"  {Colors.DIM}数据库已清理，感谢观看。{Colors.END}")
    print()


if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠ 演示已中断{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.RED}❌ 演示出错: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
