"""
Schema v2 — Enterprise Memory Engine extended schema and helper functions.

Provides:
  - apply_v2_schema(): creates all v2 tables
  - Standalone functions for preference, behavior, knowledge health, and
    team knowledge map operations (used by conftest.py MiniStore delegates)
"""

import logging
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# =========================================================================
# Schema creation
# =========================================================================

def apply_v2_schema(conn) -> None:
    """Create all v2 enterprise tables on the given SQLite connection."""
    cursor = conn.cursor()

    # Direction A: Command History & Patterns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_history (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            command TEXT NOT NULL,
            args TEXT,
            project_path TEXT,
            exit_code INTEGER,
            working_dir TEXT,
            session_key TEXT,
            createdAt INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_history_owner ON command_history(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_history_project ON command_history(project_path)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS command_patterns (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            command TEXT NOT NULL,
            project_path TEXT,
            frequency INTEGER DEFAULT 1,
            last_used_at INTEGER NOT NULL,
            success_rate REAL DEFAULT 1.0,
            avg_exit_code REAL DEFAULT 0.0,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(owner, command, project_path)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_cmd_patterns_owner ON command_patterns(owner)")

    # Direction B: Decisions
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            project TEXT,
            title TEXT NOT NULL,
            context TEXT,
            chosen TEXT,
            alternatives TEXT,
            outcome TEXT,
            status TEXT DEFAULT 'active',
            tags TEXT,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_owner ON decisions(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_cards (
            id TEXT PRIMARY KEY,
            decision_id TEXT NOT NULL,
            title TEXT NOT NULL,
            summary TEXT,
            rationale TEXT,
            impact TEXT,
            createdAt INTEGER NOT NULL,
            FOREIGN KEY (decision_id) REFERENCES decisions(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision_cards_id ON decision_cards(decision_id)")

    # Direction C: User Preferences & Behavior Patterns
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_preferences (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            confidence REAL DEFAULT 1.0,
            source TEXT DEFAULT 'explicit',
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(owner, category, key)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_owner ON user_preferences(owner)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_patterns (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            description TEXT,
            data TEXT,
            frequency INTEGER DEFAULT 1,
            confidence REAL DEFAULT 1.0,
            last_seen_at INTEGER NOT NULL,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_behavior_owner ON behavior_patterns(owner)")

    # Direction D: Knowledge Health & Forgetting Schedule
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_health (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            topic TEXT NOT NULL,
            source TEXT,
            freshness_score REAL DEFAULT 1.0,
            accuracy_score REAL DEFAULT 1.0,
            completeness_score REAL DEFAULT 1.0,
            last_verified_at INTEGER,
            next_review_at INTEGER,
            metadata TEXT,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(owner, topic)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_owner ON knowledge_health(owner)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS team_knowledge_map (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            topic TEXT NOT NULL,
            expert TEXT,
            resource_url TEXT,
            description TEXT,
            tags TEXT,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(owner, topic)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tkm_owner ON team_knowledge_map(owner)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS forgetting_schedule (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            chunk_id TEXT,
            topic TEXT,
            interval_days REAL DEFAULT 1.0,
            ease_factor REAL DEFAULT 2.5,
            repetitions INTEGER DEFAULT 0,
            next_review_at INTEGER NOT NULL,
            last_reviewed_at INTEGER,
            status TEXT DEFAULT 'pending',
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_owner ON forgetting_schedule(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_fs_due ON forgetting_schedule(next_review_at)")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_alerts (
            id TEXT PRIMARY KEY,
            team_id TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT,
            severity TEXT DEFAULT 'medium',
            resolved INTEGER DEFAULT 0,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_ka_team ON knowledge_alerts(team_id)")

    conn.commit()


# =========================================================================
# Direction C: User Preferences (standalone functions)
# =========================================================================

def upsert_user_preference(conn, **kwargs) -> str:
    """Insert or update a user preference.

    Accepts keyword arguments: owner, category, key, value, confidence, source.
    """
    try:
        owner = kwargs.get("owner", "local")
        category = kwargs.get("category", "")
        key = kwargs.get("key", "")
        value = kwargs.get("value", "")
        confidence = kwargs.get("confidence", 1.0)
        source = kwargs.get("source", "explicit")
        now = int(time.time() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
            (owner, category, key),
        )
        row = cursor.fetchone()
        if row:
            pref_id = row[0]
            cursor.execute(
                """
                UPDATE user_preferences
                SET value = ?, confidence = ?, source = ?, updatedAt = ?
                WHERE id = ?
                """,
                (value, confidence, source, now, pref_id),
            )
        else:
            pref_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO user_preferences
                (id, owner, category, key, value, confidence, source, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (pref_id, owner, category, key, value, confidence, source, now, now),
            )
        conn.commit()
        return pref_id
    except Exception as e:
        logger.error(f"upsert_user_preference failed: {e}")
        return ""


def get_user_preference(conn, owner: str, category: str, key: str) -> Optional[Dict[str, Any]]:
    """Get a specific user preference."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
            (owner, category, key),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_user_preference failed: {e}")
        return None


def list_user_preferences(
    conn, owner: str, category: Optional[str] = None,
    min_confidence: float = 0.0, limit: int = 100,
) -> List[Dict[str, Any]]:
    """List user preferences for an owner, optionally filtered by category."""
    try:
        cursor = conn.cursor()
        if category:
            cursor.execute(
                "SELECT * FROM user_preferences WHERE owner = ? AND category = ? AND confidence >= ? "
                "ORDER BY updatedAt DESC LIMIT ?",
                (owner, category, min_confidence, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM user_preferences WHERE owner = ? AND confidence >= ? "
                "ORDER BY category, key LIMIT ?",
                (owner, min_confidence, limit),
            )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"list_user_preferences failed: {e}")
        return []


def delete_user_preference(conn, owner: str, category: str, key: str) -> bool:
    """Delete a specific user preference."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM user_preferences WHERE owner = ? AND category = ? AND key = ?",
            (owner, category, key),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"delete_user_preference failed: {e}")
        return False


def decay_preference_confidence(
    conn, decay_factor: float = 0.95, min_confidence: float = 0.1,
) -> int:
    """Decay confidence of all preferences. Returns count of affected rows."""
    try:
        now = int(time.time() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE user_preferences
            SET confidence = confidence * ?, updatedAt = ?
            WHERE confidence > ?
            """,
            (decay_factor, now, min_confidence),
        )
        # Remove preferences below minimum confidence
        cursor.execute(
            "DELETE FROM user_preferences WHERE confidence < ?",
            (min_confidence,),
        )
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        logger.error(f"decay_preference_confidence failed: {e}")
        return 0


# =========================================================================
# Direction C: Behavior Patterns (standalone functions)
# =========================================================================

def insert_behavior_pattern(
    conn, owner: str, pattern_type: str, description: Optional[str] = None,
    data: Optional[str] = None, confidence: float = 0.5, sample_count: int = 0,
) -> str:
    """Insert a behavior pattern."""
    try:
        pat_id = str(uuid.uuid4())
        now = int(time.time() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO behavior_patterns
            (id, owner, pattern_type, description, data, frequency, confidence, last_seen_at, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (pat_id, owner, pattern_type, description, data,
             max(1, sample_count), confidence, now, now, now),
        )
        conn.commit()
        return pat_id
    except Exception as e:
        logger.error(f"insert_behavior_pattern failed: {e}")
        return ""


def get_behavior_patterns(
    conn, owner: str, pattern_type: Optional[str] = None, limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get behavior patterns for an owner."""
    try:
        cursor = conn.cursor()
        if pattern_type:
            cursor.execute(
                "SELECT * FROM behavior_patterns WHERE owner = ? AND pattern_type = ? "
                "ORDER BY frequency DESC LIMIT ?",
                (owner, pattern_type, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM behavior_patterns WHERE owner = ? "
                "ORDER BY frequency DESC LIMIT ?",
                (owner, limit),
            )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_behavior_patterns failed: {e}")
        return []


# =========================================================================
# Direction D: Knowledge Health (standalone functions)
# =========================================================================

def upsert_knowledge_health(
    conn, chunk_id: str, team_id: Optional[str] = None,
    importance_score: float = 0.5, freshness_status: str = "fresh",
    category: Optional[str] = None,
) -> str:
    """Insert or update a knowledge health record.

    Maps conftest parameters to the knowledge_health table:
      - chunk_id  → topic (the identifier for the knowledge)
      - team_id   → owner (the team that owns the record)
      - importance_score → accuracy_score
      - freshness_status → mapped to freshness_score (stale=0.2, aging=0.5, fresh=1.0)
      - category → metadata
    """
    try:
        owner = team_id or "default"
        topic = chunk_id
        now = int(time.time() * 1000)

        # Map freshness_status string to numeric score
        freshness_map = {
            "stale": 0.2,
            "aging": 0.5,
            "fresh": 1.0,
            "unknown": 0.3,
        }
        freshness_score = freshness_map.get(freshness_status, 0.5)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM knowledge_health WHERE owner = ? AND topic = ?",
            (owner, topic),
        )
        row = cursor.fetchone()
        if row:
            kh_id = row[0]
            cursor.execute(
                """
                UPDATE knowledge_health
                SET freshness_score = ?, accuracy_score = ?, last_verified_at = ?,
                    metadata = ?, updatedAt = ?
                WHERE id = ?
                """,
                (freshness_score, importance_score, now, category, now, kh_id),
            )
        else:
            kh_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO knowledge_health
                (id, owner, topic, source, freshness_score, accuracy_score,
                 completeness_score, last_verified_at, metadata, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, 1.0, ?, ?, ?, ?)
                """,
                (kh_id, owner, topic, freshness_status, freshness_score,
                 importance_score, now, category, now, now),
            )
        conn.commit()
        return kh_id
    except Exception as e:
        logger.error(f"upsert_knowledge_health failed: {e}")
        return ""


def record_knowledge_access(conn, chunk_id: str) -> None:
    """Record that a knowledge chunk was accessed — updates last_verified_at."""
    try:
        now = int(time.time() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE knowledge_health
            SET last_verified_at = ?, updatedAt = ?
            WHERE topic = ?
            """,
            (now, now, chunk_id),
        )
        conn.commit()
    except Exception as e:
        logger.error(f"record_knowledge_access failed: {e}")


def get_knowledge_health(conn, chunk_id: str) -> Optional[Dict[str, Any]]:
    """Get knowledge health for a specific chunk/topic."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM knowledge_health WHERE topic = ?",
            (chunk_id,),
        )
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"get_knowledge_health failed: {e}")
        return None


def list_knowledge_health(
    conn, team_id: Optional[str] = None,
    status_filter: Optional[str] = None, limit: int = 20,
) -> List[Dict[str, Any]]:
    """List knowledge health records, optionally filtered by team and status."""
    try:
        cursor = conn.cursor()
        conditions: List[str] = []
        params: List[Any] = []
        if team_id:
            conditions.append("owner = ?")
            params.append(team_id)
        if status_filter:
            conditions.append("source = ?")
            params.append(status_filter)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor.execute(
            f"SELECT * FROM knowledge_health{where} ORDER BY topic LIMIT ?",
            params + [limit],
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"list_knowledge_health failed: {e}")
        return []


def update_freshness_status(conn, chunk_id: str, status: str) -> bool:
    """Update the freshness status of a knowledge health record."""
    try:
        freshness_map = {
            "stale": 0.2,
            "aging": 0.5,
            "fresh": 1.0,
            "unknown": 0.3,
        }
        freshness_score = freshness_map.get(status, 0.5)
        now = int(time.time() * 1000)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE knowledge_health
            SET source = ?, freshness_score = ?, last_verified_at = ?, updatedAt = ?
            WHERE topic = ?
            """,
            (status, freshness_score, now, now, chunk_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"update_freshness_status failed: {e}")
        return False


# =========================================================================
# Direction D: Knowledge Alerts (standalone functions)
# =========================================================================

def get_knowledge_alerts(
    conn, team_id: Optional[str] = None,
    alert_type: str = "all", limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get knowledge alerts, optionally filtered by team and type."""
    try:
        cursor = conn.cursor()
        conditions: List[str] = []
        params: List[Any] = []
        if team_id:
            conditions.append("team_id = ?")
            params.append(team_id)
        if alert_type and alert_type != "all":
            conditions.append("alert_type = ?")
            params.append(alert_type)
        where = (" WHERE " + " AND ".join(conditions)) if conditions else ""
        cursor.execute(
            f"SELECT * FROM knowledge_alerts{where} ORDER BY createdAt DESC LIMIT ?",
            params + [limit],
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_knowledge_alerts failed: {e}")
        return []


# =========================================================================
# Direction D: Team Knowledge Map (standalone functions)
# =========================================================================

def upsert_team_knowledge_map(
    conn, team_id: str, domain: str, description: Optional[str] = None,
    member_coverage: Optional[str] = None, overall_coverage: float = 0.0,
    gap_areas: Optional[str] = None,
) -> str:
    """Insert or update a team knowledge map entry.

    Maps conftest parameters to the team_knowledge_map table:
      - team_id → owner
      - domain  → topic
      - description → description
      - member_coverage, overall_coverage, gap_areas → stored in tags as JSON
    """
    try:
        import json as _json
        now = int(time.time() * 1000)
        tags_data = {
            "member_coverage": member_coverage,
            "overall_coverage": overall_coverage,
            "gap_areas": gap_areas,
        }
        tags_str = _json.dumps(tags_data, ensure_ascii=False)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM team_knowledge_map WHERE owner = ? AND topic = ?",
            (team_id, domain),
        )
        row = cursor.fetchone()
        if row:
            tkm_id = row[0]
            cursor.execute(
                """
                UPDATE team_knowledge_map
                SET description = ?, tags = ?, updatedAt = ?
                WHERE id = ?
                """,
                (description, tags_str, now, tkm_id),
            )
        else:
            tkm_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO team_knowledge_map
                (id, owner, topic, expert, resource_url, description, tags, createdAt, updatedAt)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (tkm_id, team_id, domain, None, None, description, tags_str, now, now),
            )
        conn.commit()
        return tkm_id
    except Exception as e:
        logger.error(f"upsert_team_knowledge_map failed: {e}")
        return ""


def get_team_knowledge_map(conn, team_id: str) -> List[Dict[str, Any]]:
    """Get team knowledge map entries for a team."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM team_knowledge_map WHERE owner = ? ORDER BY topic",
            (team_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.error(f"get_team_knowledge_map failed: {e}")
        return []


def list_knowledge_gaps(
    conn, team_id: str, domain: Optional[str] = None,
    min_severity: str = "low",
) -> List[Dict[str, Any]]:
    """List knowledge gaps for a team.

    Returns entries from team_knowledge_map whose tags contain gap_areas.
    Severity is derived from overall_coverage: <0.3 → high, <0.6 → medium, else low.
    """
    try:
        import json as _json
        severity_order = {"low": 0, "medium": 1, "high": 2}
        min_sev = severity_order.get(min_severity, 0)

        cursor = conn.cursor()
        if domain:
            cursor.execute(
                "SELECT * FROM team_knowledge_map WHERE owner = ? AND topic = ?",
                (team_id, domain),
            )
        else:
            cursor.execute(
                "SELECT * FROM team_knowledge_map WHERE owner = ?",
                (team_id,),
            )
        rows = [dict(r) for r in cursor.fetchall()]

        gaps = []
        for row in rows:
            tags = {}
            if row.get("tags"):
                try:
                    tags = _json.loads(row["tags"])
                except Exception:
                    pass
            coverage = tags.get("overall_coverage", 1.0)
            gap_areas = tags.get("gap_areas")
            if not gap_areas:
                continue
            # Derive severity from coverage
            if coverage < 0.3:
                severity = "high"
            elif coverage < 0.6:
                severity = "medium"
            else:
                severity = "low"
            if severity_order.get(severity, 0) < min_sev:
                continue
            gaps.append({
                **row,
                "severity": severity,
                "gap_areas": gap_areas,
                "overall_coverage": coverage,
            })
        return gaps
    except Exception as e:
        logger.error(f"list_knowledge_gaps failed: {e}")
        return []
