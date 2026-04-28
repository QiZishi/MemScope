"""
Enterprise Memory Engine — pytest fixtures and test infrastructure.

Provides:
  - In-memory / temp-file SQLite store with v2 schema
  - Mock LLM that returns deterministic answers
  - Reusable test data generators (conversations, noise, queries)
  - Convenience wrappers for metric calculation
"""

import json
import os
import sqlite3
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# Make modules importable
# ---------------------------------------------------------------------------
_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..")
_OUTPUT_DIR = os.path.abspath(_OUTPUT_DIR)
_SRC_DIR = os.path.join(_OUTPUT_DIR, "src")

# Direction module paths
_DIRECTION_A_SRC = os.path.join(_SRC_DIR, "direction_a")
_DIRECTION_B_SRC = os.path.join(_SRC_DIR, "direction_b")
_DIRECTION_C_SRC = os.path.join(_SRC_DIR, "direction_c")
_DIRECTION_D_SRC = os.path.join(_SRC_DIR, "direction_d")

for p in (_OUTPUT_DIR, _SRC_DIR, _DIRECTION_A_SRC, _DIRECTION_B_SRC,
          _DIRECTION_C_SRC, _DIRECTION_D_SRC):
    if p not in sys.path:
        sys.path.insert(0, p)


# ---------------------------------------------------------------------------
# Mock LLM — deterministic, token-countable
# ---------------------------------------------------------------------------
class MockLLM:
    """A fake LLM that returns templated answers and tracks token usage."""

    def __init__(self, default_answer: str = "No relevant information found."):
        self._default_answer = default_answer
        self._call_log: List[Dict[str, Any]] = []
        self.total_tokens = 0

    def query(self, prompt: str, context: str = "", **kwargs) -> Dict[str, Any]:
        """Simulate an LLM call.

        Returns:
            {"answer": str, "tokens_used": int, "latency_ms": float}
        """
        start = time.perf_counter()
        # Build a deterministic answer from context keywords
        answer = self._default_answer
        tokens = max(1, len(prompt.split()) + len(context.split()))

        self._call_log.append({
            "prompt": prompt,
            "context": context[:200],
            "tokens": tokens,
        })
        self.total_tokens += tokens

        latency_ms = (time.perf_counter() - start) * 1000
        # Add a tiny fake latency so tests can measure it
        time.sleep(0.001)
        latency_ms += 1.0

        return {"answer": answer, "tokens_used": tokens, "latency_ms": latency_ms}

    @property
    def call_count(self) -> int:
        return len(self._call_log)


class KeywordLLM(MockLLM):
    """Mock LLM that searches for keywords in context and returns matching lines."""

    def query(self, prompt: str, context: str = "", **kwargs) -> Dict[str, Any]:
        start = time.perf_counter()
        # Extract meaningful query terms (>=2 chars, skip stopwords)
        stopwords = {
            "the", "is", "in", "at", "of", "on", "for", "to", "a", "an",
            "我", "的", "是", "在", "了", "有", "和", "吗", "吧",
            "什么", "怎么", "哪个", "哪些", "请", "帮", "帮",
        }
        terms = [
            t for t in prompt.replace("？", " ").replace("?", " ").split()
            if len(t) >= 2 and t not in stopwords
        ]

        # Search context for matching lines
        matched_lines = []
        for line in context.split("\n"):
            line_lower = line.lower()
            if any(t.lower() in line_lower for t in terms):
                matched_lines.append(line.strip())

        if matched_lines:
            answer = "；".join(matched_lines[:5])
        else:
            answer = "未找到相关信息"

        tokens = len(prompt.split()) + len(context.split())
        self.total_tokens += tokens
        latency_ms = (time.perf_counter() - start) * 1000 + 1.0

        self._call_log.append({
            "prompt": prompt,
            "context": context[:200],
            "tokens": tokens,
            "answer_preview": answer[:80],
        })
        return {"answer": answer, "tokens_used": tokens, "latency_ms": latency_ms}


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_path(tmp_path):
    """Provide a fresh SQLite database path with base schema + v2 extensions."""
    path = str(tmp_path / "test_memory.db")
    yield path


@pytest.fixture
def raw_conn(db_path):
    """Provide a raw sqlite3.Connection with base + v2 schema."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Base schema (mimicking SqliteStore._init_schema)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            sessionKey TEXT NOT NULL,
            turnId TEXT NOT NULL,
            seq INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            kind TEXT DEFAULT 'paragraph',
            summary TEXT,
            owner TEXT DEFAULT 'local',
            visibility TEXT DEFAULT 'private',
            sharedWith TEXT,
            taskId TEXT,
            skillId TEXT,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(sessionKey, turnId, seq)
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            summary TEXT,
            owner TEXT DEFAULT 'local',
            startedAt INTEGER NOT NULL,
            endedAt INTEGER,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            taskId TEXT,
            owner TEXT DEFAULT 'local',
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_skills (
            taskId TEXT NOT NULL,
            skillId TEXT NOT NULL,
            relation TEXT DEFAULT 'derived',
            PRIMARY KEY (taskId, skillId)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_session ON chunks(sessionKey)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_role ON chunks(role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_chunks_visibility ON chunks(visibility)")

    # FTS5
    try:
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                content, summary, content='chunks', content_rowid='rowid'
            )
        """)
    except Exception:
        pass

    # tool_logs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_logs (
            id TEXT PRIMARY KEY,
            tool TEXT NOT NULL,
            args TEXT,
            result TEXT,
            ts INTEGER NOT NULL,
            owner TEXT DEFAULT 'local'
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_logs_owner ON tool_logs(owner)")

    # embeddings
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS embeddings (
            chunkId TEXT PRIMARY KEY,
            embedding BLOB NOT NULL,
            createdAt INTEGER NOT NULL,
            FOREIGN KEY (chunkId) REFERENCES chunks(id) ON DELETE CASCADE
        )
    """)

    conn.commit()

    # Apply v2 enterprise schema
    from schema_v2 import apply_v2_schema
    apply_v2_schema(conn)

    yield conn
    conn.close()


@pytest.fixture
def store(raw_conn):
    """Provide a minimal SqliteStore-like object (the real class needs more
    methods, so we monkey-patch the essential ones)."""

    class MiniStore:
        """Lightweight stand-in for SqliteStore used in tests."""
        def __init__(self, conn):
            self.conn = conn

        # --- chunk operations ---
        def insert_chunk(self, chunk: Dict[str, Any]) -> str:
            chunk_id = chunk.get("id") or str(uuid.uuid4())
            now = int(time.time() * 1000)
            c = self.conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO chunks
                (id, sessionKey, turnId, seq, role, content, kind, summary,
                 owner, visibility, sharedWith, taskId, skillId, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                chunk_id,
                chunk.get("sessionKey", "default"),
                chunk.get("turnId", str(now)),
                chunk.get("seq", 0),
                chunk.get("role", "assistant"),
                chunk.get("content", ""),
                chunk.get("kind", "paragraph"),
                chunk.get("summary"),
                chunk.get("owner", "local"),
                chunk.get("visibility", "private"),
                chunk.get("sharedWith"),
                chunk.get("taskId"),
                chunk.get("skillId"),
                now,
                now,
            ))
            self.conn.commit()
            # Sync FTS
            try:
                c.execute(
                    "INSERT INTO chunks_fts(rowid, content, summary) SELECT rowid, content, summary FROM chunks WHERE id = ?",
                    (chunk_id,),
                )
                self.conn.commit()
            except Exception:
                pass
            return chunk_id

        def get_chunk(self, chunk_id: str) -> Optional[Dict[str, Any]]:
            c = self.conn.cursor()
            c.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,))
            row = c.fetchone()
            return dict(row) if row else None

        def search_chunks(self, query, max_results=10, **kwargs):
            c = self.conn.cursor()
            # Split query into individual terms for better Chinese text matching
            import re
            terms = re.findall(r'[\w\u4e00-\u9fff]{2,}', query)
            if not terms:
                terms = [query]
            # Build OR conditions for each term
            conditions = []
            params = []
            for term in terms:
                conditions.append("(content LIKE ? OR summary LIKE ?)")
                params.extend([f"%{term}%", f"%{term}%"])
            where_clause = " OR ".join(conditions)
            c.execute(f"""
                SELECT * FROM chunks
                WHERE {where_clause}
                ORDER BY createdAt DESC
                LIMIT ?
            """, params + [max_results])
            return [dict(r) for r in c.fetchall()]

        def fts_search(self, query, limit=10, scope="all", agent_id="default"):
            c = self.conn.cursor()
            try:
                c.execute("""
                    SELECT c.* FROM chunks c
                    JOIN chunks_fts f ON c.rowid = f.rowid
                    WHERE chunks_fts MATCH ?
                    ORDER BY rank
                    LIMIT ?
                """, (query, limit))
                return [dict(r) for r in c.fetchall()]
            except Exception:
                return self.search_chunks(query, max_results=limit)

        def get_all_chunks(self, limit=200, offset=0):
            c = self.conn.cursor()
            c.execute("SELECT * FROM chunks ORDER BY createdAt DESC LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in c.fetchall()]

        def get_tool_logs(self, limit=100, owner="local"):
            c = self.conn.cursor()
            c.execute(
                "SELECT * FROM tool_logs WHERE owner = ? ORDER BY ts DESC LIMIT ?",
                (owner, limit),
            )
            return [dict(r) for r in c.fetchall()]

        def insert_tool_log(self, log: Dict[str, Any]) -> str:
            log_id = log.get("id", str(uuid.uuid4()))
            c = self.conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO tool_logs (id, tool, args, result, ts, owner)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                log_id,
                log.get("tool", ""),
                log.get("args"),
                log.get("result"),
                log.get("ts", int(time.time() * 1000)),
                log.get("owner", "local"),
            ))
            self.conn.commit()
            return log_id

        # --- v2 schema methods (delegate to raw SQL) ---
        def upsert_user_preference(self, **kwargs):
            from schema_v2 import upsert_user_preference
            return upsert_user_preference(self.conn, **kwargs)

        def get_user_preference(self, owner, category, key):
            from schema_v2 import get_user_preference
            return get_user_preference(self.conn, owner, category, key)

        def list_user_preferences(self, owner, category=None, min_confidence=0.0, limit=100):
            from schema_v2 import list_user_preferences
            return list_user_preferences(self.conn, owner, category, min_confidence, limit)

        def delete_user_preference(self, owner, category, key):
            from schema_v2 import delete_user_preference
            return delete_user_preference(self.conn, owner, category, key)

        def decay_preference_confidence(self, owner=None, decay_factor=0.95, min_confidence=0.1):
            from schema_v2 import decay_preference_confidence
            return decay_preference_confidence(self.conn, decay_factor, min_confidence)

        def insert_behavior_pattern(self, owner, pattern_type, description, data=None, confidence=0.5, sample_count=0):
            from schema_v2 import insert_behavior_pattern
            return insert_behavior_pattern(self.conn, owner, pattern_type, description, data, confidence, sample_count)

        def get_behavior_patterns(self, owner, pattern_type=None, limit=20):
            from schema_v2 import get_behavior_patterns
            return get_behavior_patterns(self.conn, owner, pattern_type, limit)

        def upsert_knowledge_health(self, *args, **kwargs):
            if 'chunk_id' in kwargs:
                # Old conftest-style API: (chunk_id, team_id, importance_score, freshness_status, category)
                from schema_v2 import upsert_knowledge_health as _old_upsert
                return _old_upsert(
                    self.conn,
                    kwargs.get('chunk_id'),
                    kwargs.get('team_id'),
                    kwargs.get('importance_score', 0.5),
                    kwargs.get('freshness_status', 'fresh'),
                    kwargs.get('category'),
                )
            else:
                # New API from FreshnessMonitor: (owner, topic, source, freshness_score, accuracy_score, completeness_score, metadata)
                owner = kwargs.get('owner', 'default')
                topic = kwargs.get('topic', '')
                source = kwargs.get('source')
                freshness_score = kwargs.get('freshness_score', 1.0)
                accuracy_score = kwargs.get('accuracy_score', 1.0)
                completeness_score = kwargs.get('completeness_score', 1.0)
                metadata = kwargs.get('metadata')
                now = int(time.time() * 1000)
                c = self.conn.cursor()
                c.execute(
                    "SELECT id FROM knowledge_health WHERE owner = ? AND topic = ?",
                    (owner, topic),
                )
                row = c.fetchone()
                if row:
                    kh_id = row[0]
                    c.execute(
                        """UPDATE knowledge_health
                        SET source=?, freshness_score=?, accuracy_score=?,
                            completeness_score=?, last_verified_at=?, metadata=?, updatedAt=?
                        WHERE id=?""",
                        (source, freshness_score, accuracy_score, completeness_score,
                         now, metadata, now, kh_id),
                    )
                else:
                    kh_id = str(uuid.uuid4())
                    c.execute(
                        """INSERT INTO knowledge_health
                        (id, owner, topic, source, freshness_score, accuracy_score,
                         completeness_score, last_verified_at, metadata, createdAt, updatedAt)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                        (kh_id, owner, topic, source, freshness_score, accuracy_score,
                         completeness_score, now, metadata, now, now),
                    )
                self.conn.commit()
                return kh_id

        def record_knowledge_access(self, chunk_id):
            from schema_v2 import record_knowledge_access
            return record_knowledge_access(self.conn, chunk_id)

        def get_knowledge_health(self, chunk_id):
            from schema_v2 import get_knowledge_health
            return get_knowledge_health(self.conn, chunk_id)

        def list_knowledge_health(self, team_id=None, status_filter=None, limit=20):
            from schema_v2 import list_knowledge_health
            return list_knowledge_health(self.conn, team_id, status_filter, limit)

        def update_freshness_status(self, chunk_id, status):
            from schema_v2 import update_freshness_status
            return update_freshness_status(self.conn, chunk_id, status)

        def get_knowledge_alerts(self, team_id=None, alert_type="all", limit=20):
            from schema_v2 import get_knowledge_alerts
            return get_knowledge_alerts(self.conn, team_id, alert_type, limit)

        def upsert_team_knowledge_map(self, *args, **kwargs):
            if 'domain' in kwargs:
                # Old conftest-style API: (team_id, domain, description, member_coverage, overall_coverage, gap_areas)
                from schema_v2 import upsert_team_knowledge_map as _old_upsert
                return _old_upsert(
                    self.conn,
                    kwargs.get('team_id'),
                    kwargs.get('domain'),
                    kwargs.get('description'),
                    kwargs.get('member_coverage'),
                    kwargs.get('overall_coverage', 0.0),
                    kwargs.get('gap_areas'),
                )
            else:
                # New API from GapDetector: (owner, topic, expert, description, tags)
                owner = kwargs.get('owner', 'default')
                topic = kwargs.get('topic', '')
                expert = kwargs.get('expert')
                description = kwargs.get('description')
                tags = kwargs.get('tags')
                now = int(time.time() * 1000)
                c = self.conn.cursor()
                c.execute(
                    "SELECT id FROM team_knowledge_map WHERE owner = ? AND topic = ?",
                    (owner, topic),
                )
                row = c.fetchone()
                if row:
                    tkm_id = row[0]
                    c.execute(
                        """UPDATE team_knowledge_map
                        SET expert=?, description=?, tags=?, updatedAt=?
                        WHERE id=?""",
                        (expert, description, tags, now, tkm_id),
                    )
                else:
                    tkm_id = str(uuid.uuid4())
                    c.execute(
                        """INSERT INTO team_knowledge_map
                        (id, owner, topic, expert, resource_url, description, tags, createdAt, updatedAt)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (tkm_id, owner, topic, expert, None, description, tags, now, now),
                    )
                self.conn.commit()
                return tkm_id

        def get_team_knowledge_map(self, team_id):
            from schema_v2 import get_team_knowledge_map
            return get_team_knowledge_map(self.conn, team_id)

        def list_knowledge_gaps(self, team_id, domain=None, min_severity="low"):
            from schema_v2 import list_knowledge_gaps
            return list_knowledge_gaps(self.conn, team_id, domain, min_severity)

        # --- PreferenceManager-compatible methods ---
        def upsert_preference(self, owner, category, key, value, source='explicit', confidence=0.5):
            from schema_v2 import upsert_user_preference
            return upsert_user_preference(self.conn, owner=owner, category=category, key=key, value=value, confidence=confidence, source=source)

        def get_preference(self, owner, category, key):
            from schema_v2 import get_user_preference
            return get_user_preference(self.conn, owner, category, key)

        def list_preferences(self, owner, category=None):
            from schema_v2 import list_user_preferences
            return list_user_preferences(self.conn, owner, category)

        def delete_preference(self, owner, category, key):
            from schema_v2 import delete_user_preference
            return delete_user_preference(self.conn, owner, category, key)

        # --- FreshnessMonitor-compatible methods ---
        def update_freshness(self, owner, topic, freshness_score):
            now = int(time.time() * 1000)
            c = self.conn.cursor()
            c.execute(
                "UPDATE knowledge_health SET freshness_score = ?, updatedAt = ? WHERE owner = ? AND topic = ?",
                (freshness_score, now, owner, topic),
            )
            self.conn.commit()
            return c.rowcount > 0

        def insert_forgetting_schedule(self, owner, chunk_id=None, topic=None, interval_days=1.0, ease_factor=2.5):
            now = int(time.time() * 1000)
            sched_id = str(uuid.uuid4())
            next_review = now + int(interval_days * 86400000)
            try:
                c = self.conn.cursor()
                c.execute(
                    """INSERT INTO forgetting_schedule
                    (id, owner, chunk_id, topic, interval_days, ease_factor, repetitions, next_review_at, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?)""",
                    (sched_id, owner, chunk_id, topic, interval_days, ease_factor, next_review, now, now),
                )
                self.conn.commit()
                return sched_id
            except Exception:
                return ""

        def get_due_reviews(self, owner):
            now = int(time.time() * 1000)
            try:
                c = self.conn.cursor()
                c.execute(
                    "SELECT * FROM forgetting_schedule WHERE owner = ? AND next_review_at <= ? AND status = 'pending' ORDER BY next_review_at",
                    (owner, now),
                )
                return [dict(r) for r in c.fetchall()]
            except Exception:
                return []

        # --- Direction A: Command tracking ---
        def log_command(self, owner, command, args=None, project_path=None,
                        exit_code=None, working_dir=None, session_key=None):
            cmd_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            try:
                c = self.conn.cursor()
                c.execute(
                    """
                    INSERT INTO command_history
                    (id, owner, command, args, project_path, exit_code, working_dir, session_key, createdAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cmd_id, owner, command, args, project_path, exit_code, working_dir, session_key, now),
                )
                self.conn.commit()
                return cmd_id
            except Exception as e:
                return ""

        def get_command_history(self, owner, project_path=None, limit=100, offset=0):
            c = self.conn.cursor()
            if project_path:
                c.execute(
                    """
                    SELECT * FROM command_history
                    WHERE owner = ? AND project_path = ?
                    ORDER BY createdAt DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner, project_path, limit, offset),
                )
            else:
                c.execute(
                    """
                    SELECT * FROM command_history
                    WHERE owner = ?
                    ORDER BY createdAt DESC
                    LIMIT ? OFFSET ?
                    """,
                    (owner, limit, offset),
                )
            return [dict(row) for row in c.fetchall()]

        def get_command_patterns(self, owner, project_path=None, limit=50):
            c = self.conn.cursor()
            if project_path:
                c.execute(
                    """
                    SELECT * FROM command_patterns
                    WHERE owner = ? AND project_path = ?
                    ORDER BY frequency DESC, last_used_at DESC
                    LIMIT ?
                    """,
                    (owner, project_path, limit),
                )
            else:
                c.execute(
                    """
                    SELECT * FROM command_patterns
                    WHERE owner = ?
                    ORDER BY frequency DESC, last_used_at DESC
                    LIMIT ?
                    """,
                    (owner, limit),
                )
            return [dict(row) for row in c.fetchall()]

        def update_command_pattern(self, owner, command, project_path=None, exit_code=None):
            now = int(time.time() * 1000)
            c = self.conn.cursor()
            c.execute(
                """
                SELECT id, frequency, success_rate, avg_exit_code FROM command_patterns
                WHERE owner = ? AND command = ? AND (project_path = ? OR (project_path IS NULL AND ? IS NULL))
                """,
                (owner, command, project_path, project_path),
            )
            row = c.fetchone()
            if row:
                pat_id = row[0]
                freq = row[1] + 1
                old_sr = row[2] or 1.0
                old_avg = row[3] or 0.0
                success = 1.0 if (exit_code is None or exit_code == 0) else 0.0
                new_sr = (old_sr * (freq - 1) + success) / freq
                new_avg = (old_avg * (freq - 1) + (exit_code or 0)) / freq
                c.execute(
                    """
                    UPDATE command_patterns
                    SET frequency = ?, last_used_at = ?, success_rate = ?, avg_exit_code = ?, updatedAt = ?
                    WHERE id = ?
                    """,
                    (freq, now, new_sr, new_avg, now, pat_id),
                )
            else:
                pat_id = str(uuid.uuid4())
                sr = 1.0 if (exit_code is None or exit_code == 0) else 0.0
                c.execute(
                    """
                    INSERT INTO command_patterns
                    (id, owner, command, project_path, frequency, last_used_at, success_rate, avg_exit_code, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?)
                    """,
                    (pat_id, owner, command, project_path, now, sr, float(exit_code or 0), now, now),
                )
            self.conn.commit()

        # --- Direction B: Decisions ---
        def insert_decision(self, owner, title, project=None, context=None,
                            chosen=None, alternatives=None, tags=None):
            decision_id = str(uuid.uuid4())
            now = int(time.time() * 1000)
            try:
                c = self.conn.cursor()
                c.execute(
                    """
                    INSERT INTO decisions
                    (id, owner, project, title, context, chosen, alternatives, tags, createdAt, updatedAt)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (decision_id, owner, project, title, context, chosen, alternatives, tags, now, now),
                )
                self.conn.commit()
                return decision_id
            except Exception as e:
                return ""

        def get_decision(self, decision_id):
            c = self.conn.cursor()
            c.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,))
            row = c.fetchone()
            return dict(row) if row else None

        def search_decisions(self, owner, query=None, project=None, limit=20):
            c = self.conn.cursor()
            conditions = ["owner = ?"]
            params = [owner]
            if query:
                conditions.append("(title LIKE ? OR context LIKE ? OR chosen LIKE ?)")
                params.extend([f"%{query}%", f"%{query}%", f"%{query}%"])
            if project:
                conditions.append("project = ?")
                params.append(project)
            where = " AND ".join(conditions)
            c.execute(
                f"SELECT * FROM decisions WHERE {where} ORDER BY createdAt DESC LIMIT ?",
                params + [limit],
            )
            return [dict(row) for row in c.fetchall()]

        def update_decision(self, decision_id, updates):
            now = int(time.time() * 1000)
            allowed = {"title", "context", "chosen", "alternatives", "outcome", "status", "tags"}
            fields = []
            params = []
            for k, v in updates.items():
                if k in allowed:
                    fields.append(f"{k} = ?")
                    params.append(v)
            if not fields:
                return False
            fields.append("updatedAt = ?")
            params.append(now)
            params.append(decision_id)
            c = self.conn.cursor()
            c.execute(f"UPDATE decisions SET {', '.join(fields)} WHERE id = ?", params)
            self.conn.commit()
            return c.rowcount > 0

        def get_decisions_by_project(self, owner, project, limit=50):
            c = self.conn.cursor()
            c.execute(
                """
                SELECT * FROM decisions
                WHERE owner = ? AND project = ?
                ORDER BY createdAt DESC
                LIMIT ?
                """,
                (owner, project, limit),
            )
            return [dict(row) for row in c.fetchall()]

    return MiniStore(raw_conn)


@pytest.fixture
def mock_llm():
    """Provide a fresh MockLLM instance."""
    return MockLLM()


@pytest.fixture
def keyword_llm():
    """Provide a KeywordLLM that returns context-aware answers."""
    return KeywordLLM()


# ---------------------------------------------------------------------------
# Data generation helpers (available as fixtures too)
# ---------------------------------------------------------------------------

@pytest.fixture
def data_gen():
    """Provide the ConversationFactory helper."""
    return ConversationFactory()


class ConversationFactory:
    """Factory for generating test conversations, noise, and queries."""

    @staticmethod
    def make_conversation(
        user_msg: str,
        assistant_msg: str,
        timestamp: Optional[str] = None,
        session_key: Optional[str] = None,
        owner: str = "local",
    ) -> Dict[str, Any]:
        ts = timestamp or datetime.now().isoformat()
        return {
            "user": user_msg,
            "assistant": assistant_msg,
            "timestamp": ts,
            "sessionKey": session_key or f"session-{uuid.uuid4().hex[:8]}",
            "owner": owner,
        }

    @staticmethod
    def make_chunks_from_conversation(conv: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert a conversation dict into chunk dicts for the store."""
        ts = conv.get("timestamp", datetime.now().isoformat())
        try:
            ts_ms = int(datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            ts_ms = int(time.time() * 1000)

        chunks = []
        if "user" in conv:
            chunks.append({
                "id": str(uuid.uuid4()),
                "sessionKey": conv.get("sessionKey", "default"),
                "turnId": str(ts_ms),
                "seq": 0,
                "role": "user",
                "content": conv["user"],
                "owner": conv.get("owner", "local"),
                "visibility": conv.get("visibility", "private"),
                "createdAt": ts_ms,
                "updatedAt": ts_ms,
            })
        if "assistant" in conv:
            chunks.append({
                "id": str(uuid.uuid4()),
                "sessionKey": conv.get("sessionKey", "default"),
                "turnId": str(ts_ms),
                "seq": 1,
                "role": "assistant",
                "content": conv["assistant"],
                "owner": conv.get("owner", "local"),
                "visibility": conv.get("visibility", "private"),
                "createdAt": ts_ms,
                "updatedAt": ts_ms,
            })
        return chunks

    @staticmethod
    def generate_noise(count: int, category: str = "general") -> List[Dict[str, Any]]:
        """Generate N noise conversations."""
        noise_templates = {
            "general": [
                ("今天天气不错", "是的，天气很好。"),
                ("帮我订一杯拿铁咖啡", "已为您下单。"),
                ("最近有部新电影上映", "是的，您可以看看评分。"),
                ("明天要开会吗", "您明天上午10点有周会。"),
                ("周末有什么计划", "这周末天气不错，可以出去走走。"),
                ("帮我看看这封邮件", "这封邮件是关于项目进度的。"),
                ("午餐吃什么", "推荐试试楼下的日料。"),
                ("最近在追什么剧", "在看一部悬疑剧，挺好看的。"),
            ],
            "project": [
                ("项目X进度怎么样了", "项目X进展顺利。"),
                ("项目Y的测试报告出来了", "测试报告已发送到群里。"),
                ("项目Z的需求变更了", "已收到变更通知。"),
                ("下周有哪些项目评审", "下周三有项目A的评审。"),
            ],
            "role_confusion": [
                ("张三下周三也要去拜访客户A", "已记录张三的行程。"),
                ("李四下周三去客户B", "已记录李四的行程。"),
                ("王五这周请假了", "已记录王五的请假信息。"),
                ("赵六要去出差", "已记录赵六的出差安排。"),
            ],
        }
        templates = noise_templates.get(category, noise_templates["general"])
        noise = []
        base_time = datetime(2026, 5, 1, 10, 5, 0)
        for i in range(count):
            tmpl = templates[i % len(templates)]
            ts = (base_time + timedelta(minutes=i * 5)).isoformat()
            noise.append({
                "user": tmpl[0],
                "assistant": tmpl[1],
                "timestamp": ts,
                "sessionKey": f"noise-{uuid.uuid4().hex[:8]}",
            })
        return noise

    @staticmethod
    def make_team_chunks(
        members: List[str],
        domain_content: Dict[str, List[str]],
        team_id: str = "team-1",
    ) -> List[Dict[str, Any]]:
        """Generate chunks for team knowledge testing.

        Args:
            members: List of member names/IDs.
            domain_content: Dict mapping member -> list of content strings.
            team_id: Team identifier.
        """
        chunks = []
        base_time = int(datetime(2026, 4, 1).timestamp() * 1000)
        offset = 0  # Global offset to avoid UNIQUE constraint collisions
        for member, contents in domain_content.items():
            for i, content in enumerate(contents):
                chunks.append({
                    "id": str(uuid.uuid4()),
                    "sessionKey": f"team-{team_id}-session-{member}",
                    "turnId": str(base_time + offset * 60000),
                    "seq": 0,
                    "role": "user",
                    "content": content,
                    "owner": member,
                    "visibility": "shared",
                    "createdAt": base_time + offset * 60000,
                    "updatedAt": base_time + offset * 60000,
                })
                offset += 1
        return chunks

    @staticmethod
    def days_ago_ts(days: int) -> int:
        """Return timestamp in ms for N days ago."""
        return int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

    @staticmethod
    def days_from_now_ts(days: int) -> int:
        """Return timestamp in ms for N days from now."""
        return int((datetime.now() + timedelta(days=days)).timestamp() * 1000)


# ---------------------------------------------------------------------------
# Metric calculation helpers
# ---------------------------------------------------------------------------

class MetricCalculator:
    """Helper class for computing evaluation metrics."""

    @staticmethod
    def precision(found_items: List[str], expected_items: List[str]) -> float:
        if not found_items:
            return 0.0
        correct = sum(1 for item in found_items if item in expected_items)
        return correct / len(found_items)

    @staticmethod
    def recall(found_items: List[str], expected_items: List[str]) -> float:
        if not expected_items:
            return 1.0
        found_set = set(found_items)
        correct = sum(1 for item in expected_items if item in found_set)
        return correct / len(expected_items)

    @staticmethod
    def f1(precision_val: float, recall_val: float) -> float:
        if precision_val + recall_val == 0:
            return 0.0
        return 2 * precision_val * recall_val / (precision_val + recall_val)

    @staticmethod
    def noise_rate(found_items: List[str], noise_items: List[str]) -> float:
        if not found_items:
            return 0.0
        noise_found = sum(1 for item in found_items if item in noise_items)
        return noise_found / len(found_items)

    @staticmethod
    def percentile(data: List[float], p: float) -> float:
        if not data:
            return 0.0
        sorted_data = sorted(data)
        idx = int(len(sorted_data) * p / 100)
        idx = min(idx, len(sorted_data) - 1)
        return sorted_data[idx]

    @staticmethod
    def text_contains_keywords(text: str, keywords: List[str]) -> float:
        """Return fraction of keywords found in text."""
        if not keywords:
            return 1.0
        text_lower = text.lower()
        found = sum(1 for kw in keywords if kw.lower() in text_lower)
        return found / len(keywords)

    @staticmethod
    def text_not_contains(text: str, forbidden: List[str]) -> bool:
        """Return True if none of the forbidden terms appear in text."""
        text_lower = text.lower()
        return not any(f.lower() in text_lower for f in forbidden)


@pytest.fixture
def metrics():
    """Provide the MetricCalculator."""
    return MetricCalculator()


# ---------------------------------------------------------------------------
# Report collection hook
# ---------------------------------------------------------------------------

class ReportCollector:
    """Collects test results for the evaluation runner."""

    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self._start_time = time.time()

    def add(self, test_id: str, test_name: str, status: str,
            metrics: Dict[str, Any], details: str = "",
            latency_ms: float = 0.0, token_count: int = 0,
            error_message: str = ""):
        self.results.append({
            "test_id": test_id,
            "test_name": test_name,
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "metrics": metrics,
            "latency_ms": round(latency_ms, 2),
            "token_count": token_count,
            "details": details,
            "error_message": error_message,
        })

    def to_json(self) -> str:
        return json.dumps(self.results, indent=2, ensure_ascii=False)


_report_collector = ReportCollector()


@pytest.fixture
def report_collector():
    """Provide the global ReportCollector singleton."""
    return _report_collector
