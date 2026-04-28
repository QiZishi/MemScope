"""
Enterprise Memory — Schema v2 Extensions

Adds four new tables to the existing memos SQLite database:
  - user_preferences      (Direction C: personal habit / preference memory)
  - behavior_patterns     (Direction C: inferred behavior patterns)
  - knowledge_health      (Direction D: knowledge freshness tracking)
  - team_knowledge_map    (Direction D: team coverage analysis)

This module is designed to be called once during initialization via
``apply_v2_schema(conn)``. It is fully idempotent — safe to run on
every startup.
"""

import json
import logging
import sqlite3
import time
import uuid
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Schema version marker
# ---------------------------------------------------------------------------

_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Schema migration
# ---------------------------------------------------------------------------

def apply_v2_schema(conn: sqlite3.Connection) -> None:
    """Apply v2 enterprise tables to an existing memos database.

    Args:
        conn: An open sqlite3.Connection (check_same_thread=False is fine).
    """
    cursor = conn.cursor()

    # ---- Schema version tracking table ----
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at INTEGER NOT NULL,
            description TEXT
        )
    """)

    # Check if v2 is already applied
    cursor.execute("SELECT version FROM schema_version WHERE version = ?", (_SCHEMA_VERSION,))
    if cursor.fetchone():
        logger.debug("enterprise-memory: schema v2 already applied")
        # Ensure unique index exists for behavior_patterns (migration for existing tables)
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bp_owner_type_unique ON behavior_patterns(owner, pattern_type)")
        conn.commit()
        return

    now_ms = int(time.time() * 1000)

    # =====================================================================
    # user_preferences — structured storage of personal work habits
    # =====================================================================
    cursor.execute("""
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
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_owner ON user_preferences(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_category ON user_preferences(category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_owner_cat ON user_preferences(owner, category)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pref_confidence ON user_preferences(confidence)")

    # =====================================================================
    # behavior_patterns — inferred habits from historical interaction data
    # =====================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS behavior_patterns (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            description TEXT NOT NULL,
            data TEXT,
            confidence REAL DEFAULT 0.5,
            sample_count INTEGER DEFAULT 0,
            createdAt INTEGER NOT NULL,
            updatedAt INTEGER NOT NULL,
            UNIQUE(owner, pattern_type)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bp_owner ON behavior_patterns(owner)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bp_type ON behavior_patterns(pattern_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_bp_owner_type ON behavior_patterns(owner, pattern_type)")

    # =====================================================================
    # knowledge_health — freshness / importance tracking per chunk
    # =====================================================================
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_health (
            id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL UNIQUE,
            team_id TEXT,
            importance_score REAL DEFAULT 0.5,
            last_accessed_at INTEGER,
            access_count INTEGER DEFAULT 0,
            freshness_status TEXT DEFAULT 'fresh',
            last_verified_at INTEGER,
            category TEXT,
            FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_chunk ON knowledge_health(chunk_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_team ON knowledge_health(team_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_status ON knowledge_health(freshness_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_kh_importance ON knowledge_health(importance_score)")

    # =====================================================================
    # team_knowledge_map — per-team domain coverage analysis
    # =====================================================================
    cursor.execute("""
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
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tkm_team ON team_knowledge_map(team_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tkm_domain ON team_knowledge_map(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tkm_coverage ON team_knowledge_map(overall_coverage)")

    # Record schema version
    cursor.execute(
        "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
        (_SCHEMA_VERSION, now_ms, "Enterprise memory: preferences, patterns, knowledge health, team map"),
    )

    conn.commit()
    logger.info("enterprise-memory: schema v2 applied successfully")


# ---------------------------------------------------------------------------
# CRUD helpers — These are mixed into SqliteStore at runtime via monkey-
# patching or by subclassing.  Kept here as pure functions for testability.
# ---------------------------------------------------------------------------

def _generate_id() -> str:
    """Generate a unique identifier."""
    return str(uuid.uuid4())


def _now_ms() -> int:
    """Current timestamp in milliseconds."""
    return int(time.time() * 1000)


# ---- user_preferences ----------------------------------------------------

def upsert_user_preference(
    conn: sqlite3.Connection,
    owner: str,
    category: str,
    key: str,
    value: str,
    confidence: float = 0.5,
    evidence_count: int = 1,
    source: Optional[str] = None,
) -> str:
    """Insert or update a user preference.  Returns the preference ID."""
    now = _now_ms()
    pref_id = _generate_id()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO user_preferences (id, owner, category, key, value, confidence, evidence_count, source, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owner, category, key) DO UPDATE SET
            value = excluded.value,
            confidence = CASE
                WHEN excluded.confidence > user_preferences.confidence THEN excluded.confidence
                ELSE user_preferences.confidence
            END,
            evidence_count = user_preferences.evidence_count + 1,
            source = COALESCE(excluded.source, user_preferences.source),
            updatedAt = excluded.updatedAt
    """, (pref_id, owner, category, key, value, confidence, evidence_count, source, now, now))

    conn.commit()
    return pref_id


def get_user_preference(
    conn: sqlite3.Connection,
    owner: str,
    category: str,
    key: str,
) -> Optional[Dict[str, Any]]:
    """Get a single preference by owner + category + key."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM user_preferences
        WHERE owner = ? AND category = ? AND key = ?
    """, (owner, category, key))
    row = cursor.fetchone()
    return dict(row) if row else None


def list_user_preferences(
    conn: sqlite3.Connection,
    owner: str,
    category: Optional[str] = None,
    min_confidence: float = 0.0,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    """List preferences for a user, optionally filtered by category and confidence."""
    cursor = conn.cursor()
    params: list = [owner, min_confidence]
    where = "owner = ? AND confidence >= ?"

    if category:
        where += " AND category = ?"
        params.append(category)

    cursor.execute(f"""
        SELECT * FROM user_preferences
        WHERE {where}
        ORDER BY confidence DESC, updatedAt DESC
        LIMIT ?
    """, params + [limit])

    return [dict(row) for row in cursor.fetchall()]


def delete_user_preference(
    conn: sqlite3.Connection,
    owner: str,
    category: str,
    key: str,
) -> bool:
    """Delete a user preference. Returns True if a row was deleted."""
    cursor = conn.cursor()
    cursor.execute("""
        DELETE FROM user_preferences
        WHERE owner = ? AND category = ? AND key = ?
    """, (owner, category, key))
    conn.commit()
    return cursor.rowcount > 0


def decay_preference_confidence(
    conn: sqlite3.Connection,
    decay_factor: float = 0.95,
    min_confidence: float = 0.1,
) -> int:
    """Apply confidence decay to all preferences.

    Called periodically to reduce confidence of preferences that
    haven't received new evidence.

    Returns:
        Number of preferences updated.
    """
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE user_preferences
        SET confidence = MAX(confidence * ?, ?),
            updatedAt = ?
        WHERE confidence > ?
    """, (decay_factor, min_confidence, _now_ms(), min_confidence))
    conn.commit()
    return cursor.rowcount


# ---- behavior_patterns ---------------------------------------------------

def insert_behavior_pattern(
    conn: sqlite3.Connection,
    owner: str,
    pattern_type: str,
    description: str,
    data: Optional[Dict[str, Any]] = None,
    confidence: float = 0.5,
    sample_count: int = 0,
) -> str:
    """Insert a new behavior pattern. Returns the pattern ID."""
    pattern_id = _generate_id()
    now = _now_ms()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO behavior_patterns
        (id, owner, pattern_type, description, data, confidence, sample_count, createdAt, updatedAt)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(owner, pattern_type) DO UPDATE SET
            description = excluded.description,
            data = excluded.data,
            confidence = excluded.confidence,
            sample_count = excluded.sample_count,
            updatedAt = excluded.updatedAt
    """, (
        pattern_id, owner, pattern_type, description,
        json.dumps(data) if data else None,
        confidence, sample_count, now, now,
    ))
    conn.commit()
    return pattern_id


def get_behavior_patterns(
    conn: sqlite3.Connection,
    owner: str,
    pattern_type: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get behavior patterns for a user."""
    cursor = conn.cursor()
    params: list = [owner]
    where = "owner = ?"

    if pattern_type:
        where += " AND pattern_type = ?"
        params.append(pattern_type)

    cursor.execute(f"""
        SELECT * FROM behavior_patterns
        WHERE {where}
        ORDER BY confidence DESC, updatedAt DESC
        LIMIT ?
    """, params + [limit])

    results = []
    for row in cursor.fetchall():
        d = dict(row)
        # Deserialize JSON data field
        if d.get("data"):
            try:
                d["data"] = json.loads(d["data"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(d)
    return results


def update_behavior_pattern(
    conn: sqlite3.Connection,
    pattern_id: str,
    *,
    description: Optional[str] = None,
    data: Optional[Dict[str, Any]] = None,
    confidence: Optional[float] = None,
    sample_count: Optional[int] = None,
) -> bool:
    """Update fields of a behavior pattern."""
    now = _now_ms()
    fields, params = [], []

    if description is not None:
        fields.append("description = ?")
        params.append(description)
    if data is not None:
        fields.append("data = ?")
        params.append(json.dumps(data))
    if confidence is not None:
        fields.append("confidence = ?")
        params.append(confidence)
    if sample_count is not None:
        fields.append("sample_count = ?")
        params.append(sample_count)

    if not fields:
        return False

    fields.append("updatedAt = ?")
    params.append(now)
    params.append(pattern_id)

    cursor = conn.cursor()
    cursor.execute(f"""
        UPDATE behavior_patterns SET {', '.join(fields)} WHERE id = ?
    """, params)
    conn.commit()
    return cursor.rowcount > 0


# ---- knowledge_health ----------------------------------------------------

def upsert_knowledge_health(
    conn: sqlite3.Connection,
    chunk_id: str,
    team_id: Optional[str] = None,
    importance_score: float = 0.5,
    freshness_status: str = "fresh",
    category: Optional[str] = None,
) -> str:
    """Insert or update a knowledge health record. Returns the record ID."""
    health_id = _generate_id()
    now = _now_ms()

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO knowledge_health
        (id, chunk_id, team_id, importance_score, last_accessed_at, access_count,
         freshness_status, last_verified_at, category)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
        ON CONFLICT(chunk_id) DO UPDATE SET
            team_id = COALESCE(excluded.team_id, knowledge_health.team_id),
            importance_score = excluded.importance_score,
            freshness_status = excluded.freshness_status,
            last_verified_at = excluded.last_verified_at,
            category = COALESCE(excluded.category, knowledge_health.category)
    """, (health_id, chunk_id, team_id, importance_score, now, freshness_status, now, category))
    conn.commit()
    return health_id


def record_knowledge_access(
    conn: sqlite3.Connection,
    chunk_id: str,
) -> None:
    """Record that a chunk was accessed (bumps access_count and last_accessed_at)."""
    now = _now_ms()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE knowledge_health
        SET last_accessed_at = ?,
            access_count = access_count + 1,
            freshness_status = CASE
                WHEN freshness_status IN ('stale', 'forgotten') THEN 'aging'
                ELSE freshness_status
            END
        WHERE chunk_id = ?
    """, (now, chunk_id))
    conn.commit()


def get_knowledge_health(
    conn: sqlite3.Connection,
    chunk_id: str,
) -> Optional[Dict[str, Any]]:
    """Get the health record for a specific chunk."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM knowledge_health WHERE chunk_id = ?
    """, (chunk_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def list_knowledge_health(
    conn: sqlite3.Connection,
    team_id: Optional[str] = None,
    status_filter: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """List knowledge health records with optional filters."""
    cursor = conn.cursor()
    conditions: list = []
    params: list = []

    if team_id:
        conditions.append("team_id = ?")
        params.append(team_id)
    if status_filter:
        conditions.append("freshness_status = ?")
        params.append(status_filter)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT * FROM knowledge_health {where}
        ORDER BY importance_score DESC, last_accessed_at DESC
        LIMIT ?
    """, params + [limit])

    return [dict(row) for row in cursor.fetchall()]


def update_freshness_status(
    conn: sqlite3.Connection,
    chunk_id: str,
    status: str,
) -> bool:
    """Update the freshness status of a knowledge entry."""
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE knowledge_health SET freshness_status = ? WHERE chunk_id = ?
    """, (status, chunk_id))
    conn.commit()
    return cursor.rowcount > 0


def get_knowledge_alerts(
    conn: sqlite3.Connection,
    team_id: Optional[str] = None,
    alert_type: str = "all",
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Get knowledge health alerts based on freshness status and risk indicators."""
    cursor = conn.cursor()
    conditions: list = []
    params: list = []

    if team_id:
        conditions.append("kh.team_id = ?")
        params.append(team_id)

    if alert_type == "stale":
        conditions.append("kh.freshness_status = 'stale'")
    elif alert_type == "forgotten":
        conditions.append("kh.freshness_status = 'forgotten'")
    elif alert_type == "degraded":
        conditions.append("kh.freshness_status IN ('stale', 'forgotten')")
    # "all" and "single_point" handled below

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    cursor.execute(f"""
        SELECT kh.*, c.summary, c.content, c.owner, c.visibility
        FROM knowledge_health kh
        LEFT JOIN chunks c ON kh.chunk_id = c.id
        {where}
        ORDER BY kh.importance_score DESC, kh.last_accessed_at ASC
        LIMIT ?
    """, params + [limit])

    results = []
    for row in cursor.fetchall():
        d = dict(row)
        # Generate human-readable alert message
        status = d.get("freshness_status", "fresh")
        if status == "stale":
            d["alert_message"] = f"Knowledge is stale (importance: {d.get('importance_score', 0):.2f}). Consider verifying or updating."
        elif status == "forgotten":
            d["alert_message"] = f"Knowledge has been forgotten — not accessed for a long time (importance: {d.get('importance_score', 0):.2f})."
        elif status == "aging":
            d["alert_message"] = f"Knowledge is aging (importance: {d.get('importance_score', 0):.2f}). May need review soon."
        results.append(d)

    return results


# ---- team_knowledge_map --------------------------------------------------

def upsert_team_knowledge_map(
    conn: sqlite3.Connection,
    team_id: str,
    domain: str,
    description: Optional[str] = None,
    member_coverage: Optional[Dict[str, float]] = None,
    overall_coverage: float = 0.0,
    gap_areas: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Insert or update a team knowledge map entry. Returns the entry ID."""
    map_id = _generate_id()
    now = _now_ms()

    cursor = conn.cursor()

    # Try to find existing entry for this team+domain
    cursor.execute("""
        SELECT id FROM team_knowledge_map
        WHERE team_id = ? AND domain = ?
    """, (team_id, domain))
    existing = cursor.fetchone()

    if existing:
        map_id = existing[0]
        cursor.execute("""
            UPDATE team_knowledge_map
            SET description = ?,
                member_coverage = ?,
                overall_coverage = ?,
                gap_areas = ?,
                last_analysis_at = ?,
                updatedAt = ?
            WHERE id = ?
        """, (
            description,
            json.dumps(member_coverage) if member_coverage else None,
            overall_coverage,
            json.dumps(gap_areas) if gap_areas else None,
            now, now, map_id,
        ))
    else:
        cursor.execute("""
            INSERT INTO team_knowledge_map
            (id, team_id, domain, description, member_coverage, overall_coverage,
             gap_areas, last_analysis_at, createdAt, updatedAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            map_id, team_id, domain, description,
            json.dumps(member_coverage) if member_coverage else None,
            overall_coverage,
            json.dumps(gap_areas) if gap_areas else None,
            now, now, now,
        ))

    conn.commit()
    return map_id


def get_team_knowledge_map(
    conn: sqlite3.Connection,
    team_id: str,
) -> Optional[Dict[str, Any]]:
    """Get the complete team knowledge map for a team."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM team_knowledge_map
        WHERE team_id = ?
        ORDER BY overall_coverage ASC
    """, (team_id,))

    rows = cursor.fetchall()
    if not rows:
        return None

    domains = []
    for row in rows:
        d = dict(row)
        # Deserialize JSON fields
        for field in ("member_coverage", "gap_areas"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass
        domains.append(d)

    # Compute team-level summary
    total_domains = len(domains)
    avg_coverage = sum(d.get("overall_coverage", 0) for d in domains) / total_domains if total_domains else 0
    low_coverage_count = sum(1 for d in domains if d.get("overall_coverage", 0) < 0.5)

    return {
        "team_id": team_id,
        "total_domains": total_domains,
        "average_coverage": round(avg_coverage, 3),
        "low_coverage_domains": low_coverage_count,
        "domains": domains,
        "last_analysis_at": domains[0].get("last_analysis_at") if domains else None,
    }


def list_knowledge_gaps(
    conn: sqlite3.Connection,
    team_id: str,
    domain: Optional[str] = None,
    min_severity: str = "low",
) -> List[Dict[str, Any]]:
    """List knowledge gaps from the team knowledge map."""
    severity_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
    min_sev = severity_order.get(min_severity, 0)

    cursor = conn.cursor()
    params: list = [team_id]
    where = "team_id = ?"

    if domain:
        where += " AND domain = ?"
        params.append(domain)

    cursor.execute(f"""
        SELECT * FROM team_knowledge_map
        WHERE {where}
        ORDER BY overall_coverage ASC
    """, params)

    results = []
    for row in cursor.fetchall():
        d = dict(row)
        for field in ("member_coverage", "gap_areas"):
            if d.get(field):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    pass

        # Derive severity from coverage
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
        d["severity_order"] = severity_order.get(severity, 0)

        if d["severity_order"] >= min_sev:
            # Generate recommendation
            if coverage < 0.2:
                d["recommendation"] = "Critical gap: Consider assigning a knowledge owner and scheduling knowledge transfer sessions."
            elif coverage < 0.4:
                d["recommendation"] = "Low coverage: Encourage team members to document experiences in this domain."
            elif coverage < 0.6:
                d["recommendation"] = "Moderate gap: Pair team members with domain experts for shadowing."
            else:
                d["recommendation"] = "Adequate coverage but monitor for degradation."
            results.append(d)

    # Sort by severity (most severe first)
    results.sort(key=lambda x: x.get("severity_order", 0), reverse=True)
    return results
