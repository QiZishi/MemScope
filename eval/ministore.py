"""MiniStore - 从 conftest.py 提取的轻量级存储实现"""
import json
import os
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

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