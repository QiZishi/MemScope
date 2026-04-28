"""
Enterprise Memory — Knowledge Freshness Monitor

Monitors knowledge freshness by evaluating:
  - Last access time per chunk
  - Access frequency
  - Content-type sensitivity (API docs age faster than architecture decisions)
  - Time-based decay with configurable thresholds

Direction D: Team Knowledge Health / Forgetting Alerts.

Freshness lifecycle:
  fresh → aging → stale → forgotten

Thresholds:
  - fresh:   accessed within stale_threshold_days (default 30)
  - aging:   accessed within forgotten_threshold_days (default 90) but > stale
  - stale:   not accessed for > stale_threshold_days
  - forgotten: not accessed for > forgotten_threshold_days
"""

import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Content types that are time-sensitive (tend to go stale faster)
TIME_SENSITIVE_PATTERNS = [
    r"\bapi\b",
    r"\bendpoint\b",
    r"\bversion\b",
    r"\bdeploy\b",
    r"\brelease\b",
    r"\bchangelog\b",
    r"\bupdate\b",
    r"\bconfig\b",
    r"\bsetting\b",
    r"\benvironment\b",
    r"\bpassword\b",
    r"\btoken\b",
    r"\bcredential\b",
    r"\bsecret\b",
]

# Content types that are more durable
DURABLE_PATTERNS = [
    r"\barchitecture\b",
    r"\bdesign\b",
    r"\bdecision\b",
    r"\brationale\b",
    r"\blesson\b",
    r"\bprinciple\b",
    r"\bpattern\b",
    r"\bstrategy\b",
]


class FreshnessMonitor:
    """Monitors and updates knowledge freshness status."""

    def __init__(
        self,
        store: Any,
        stale_threshold_days: int = 30,
        forgotten_threshold_days: int = 90,
    ):
        """
        Args:
            store: SqliteStore instance with v2 schema tables.
            stale_threshold_days: Days before marking as stale.
            forgotten_threshold_days: Days before marking as forgotten.
        """
        self._store = store
        self._stale_days = stale_threshold_days
        self._forgotten_days = forgotten_threshold_days

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def check_freshness(self, team_id: Optional[str] = None) -> Dict[str, Any]:
        """Run a freshness check across all tracked knowledge.

        This is the main entry point — call periodically (e.g., via cron).

        Args:
            team_id: Optional team filter.

        Returns:
            Summary of the freshness check.
        """
        now_ms = int(time.time() * 1000)
        stale_cutoff = now_ms - (self._stale_days * 86400 * 1000)
        forgotten_cutoff = now_ms - (self._forgotten_days * 86400 * 1000)

        # Get all chunks and ensure they have health records
        self._ensure_health_records(team_id)

        # Update freshness statuses
        updated_count = self._update_statuses(now_ms, stale_cutoff, forgotten_cutoff)

        # Collect summary
        all_health = self._store.list_knowledge_health(team_id=team_id, limit=10000)
        status_counts = {}
        for h in all_health:
            status = h.get("freshness_status", "fresh")
            status_counts[status] = status_counts.get(status, 0) + 1

        summary = {
            "checked_at": now_ms,
            "team_id": team_id,
            "total_entries": len(all_health),
            "updated_count": updated_count,
            "status_distribution": status_counts,
            "thresholds": {
                "stale_days": self._stale_days,
                "forgotten_days": self._forgotten_days,
            },
        }

        logger.info(
            f"freshness_monitor: check complete — "
            f"{len(all_health)} entries, {updated_count} updated, "
            f"statuses={status_counts}"
        )
        return summary

    def get_warnings(self, team_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get freshness warnings for stale and forgotten entries.

        Returns:
            List of warning dicts with chunk info and recommended actions.
        """
        stale = self._store.list_knowledge_health(
            team_id=team_id, status_filter="stale", limit=50,
        )
        forgotten = self._store.list_knowledge_health(
            team_id=team_id, status_filter="forgotten", limit=50,
        )

        warnings: List[Dict[str, Any]] = []

        for entry in stale:
            warnings.append(self._build_warning(entry, "stale"))
        for entry in forgotten:
            warnings.append(self._build_warning(entry, "forgotten"))

        # Sort by importance (most important first)
        warnings.sort(key=lambda w: w.get("importance_score", 0), reverse=True)
        return warnings

    def get_entry_health(self, chunk_id: str) -> Dict[str, Any]:
        """Get detailed freshness info for a single chunk.

        Returns:
            Health info dict, or empty dict if not tracked.
        """
        health = self._store.get_knowledge_health(chunk_id)
        if not health:
            return {"chunk_id": chunk_id, "status": "untracked"}

        now_ms = int(time.time() * 1000)
        last_accessed = health.get("last_accessed_at", 0)
        days_since_access = (now_ms - last_accessed) / 86400000 if last_accessed else None

        # Determine recommended action
        status = health.get("freshness_status", "fresh")
        action = self._recommend_action(health, status)

        return {
            "chunk_id": chunk_id,
            "freshness_status": status,
            "importance_score": health.get("importance_score", 0.5),
            "access_count": health.get("access_count", 0),
            "last_accessed_at": last_accessed,
            "days_since_access": round(days_since_access, 1) if days_since_access else None,
            "category": health.get("category"),
            "recommended_action": action,
        }

    # ------------------------------------------------------------------
    # Internal: Health record management
    # ------------------------------------------------------------------

    def _ensure_health_records(self, team_id: Optional[str] = None) -> None:
        """Ensure all chunks have corresponding health records."""
        from schema_v2 import upsert_knowledge_health

        # Get chunks that don't have health records yet
        cursor = self._store.conn.cursor()
        cursor.execute("""
            SELECT c.id, c.summary, c.content, c.owner, c.createdAt
            FROM chunks c
            LEFT JOIN knowledge_health kh ON c.id = kh.chunk_id
            WHERE kh.chunk_id IS NULL
            LIMIT 500
        """)

        now_ms = int(time.time() * 1000)
        batch = []

        for row in cursor.fetchall():
            chunk_id = row[0]
            summary = row[1] or ""
            content = row[2] or ""
            owner = row[3] or "default"
            created_at = row[4] or now_ms

            # Estimate importance based on content signals
            importance = self._estimate_importance(summary + " " + content)
            category = self._classify_content(summary + " " + content)

            batch.append((chunk_id, team_id or owner, importance, created_at, category))

        # Bulk insert health records
        for chunk_id, tid, importance, created_at, category in batch:
            self._store.upsert_knowledge_health(
                chunk_id=chunk_id,
                team_id=tid,
                importance_score=importance,
                category=category,
            )

        if batch:
            logger.debug(f"freshness_monitor: created {len(batch)} health records")

    def _update_statuses(
        self,
        now_ms: int,
        stale_cutoff: int,
        forgotten_cutoff: int,
    ) -> int:
        """Update freshness statuses based on access times."""
        cursor = self._store.conn.cursor()
        updated = 0

        # Mark as forgotten
        cursor.execute("""
            UPDATE knowledge_health
            SET freshness_status = 'forgotten'
            WHERE freshness_status != 'forgotten'
            AND last_accessed_at IS NOT NULL
            AND last_accessed_at < ?
        """, (forgotten_cutoff,))
        updated += cursor.rowcount

        # Mark as stale
        cursor.execute("""
            UPDATE knowledge_health
            SET freshness_status = 'stale'
            WHERE freshness_status NOT IN ('stale', 'forgotten')
            AND last_accessed_at IS NOT NULL
            AND last_accessed_at < ?
            AND last_accessed_at >= ?
        """, (stale_cutoff, forgotten_cutoff))
        updated += cursor.rowcount

        # Mark as aging (was fresh but hasn't been accessed in a while)
        aging_cutoff = now_ms - (self._stale_days * 86400 * 1000 // 2)  # half of stale threshold
        cursor.execute("""
            UPDATE knowledge_health
            SET freshness_status = 'aging'
            WHERE freshness_status = 'fresh'
            AND last_accessed_at IS NOT NULL
            AND last_accessed_at < ?
        """, (aging_cutoff,))
        updated += cursor.rowcount

        # Entries with no access records — use last_verified_at as creation proxy
        cursor.execute("""
            UPDATE knowledge_health
            SET freshness_status = CASE
                WHEN last_verified_at < ? THEN 'forgotten'
                WHEN last_verified_at < ? THEN 'stale'
                WHEN last_verified_at < ? THEN 'aging'
                ELSE 'fresh'
            END
            WHERE last_accessed_at IS NULL
        """, (forgotten_cutoff, stale_cutoff, aging_cutoff))
        updated += cursor.rowcount

        self._store.conn.commit()
        return updated

    # ------------------------------------------------------------------
    # Internal: Content analysis
    # ------------------------------------------------------------------

    def _estimate_importance(self, text: str) -> float:
        """Estimate knowledge importance based on content signals.

        Returns:
            Float between 0.0 (low) and 1.0 (high).
        """
        if not text:
            return 0.3

        score = 0.5  # Base score
        text_lower = text.lower()

        # Boost for technical depth signals
        depth_signals = [
            (r'\bstep[s]?\b', 0.05),
            (r'\berror\b', 0.03),
            (r'\bbug\b', 0.03),
            (r'\bfix\b', 0.03),
            (r'\bsolution\b', 0.04),
            (r'\bimportant\b', 0.05),
            (r'\bcritical\b', 0.06),
            (r'\bnever\b', 0.03),
            (r'\balways\b', 0.03),
            (r'\bdecided\b', 0.04),
            (r'\btrade-?off\b', 0.05),
            (r'\blesson\b', 0.04),
        ]

        for pattern, boost in depth_signals:
            if re.search(pattern, text_lower):
                score += boost

        # Length-based boost (longer = potentially more detailed)
        word_count = len(text.split())
        if word_count > 100:
            score += 0.05
        if word_count > 300:
            score += 0.05

        # Penalize very short content
        if word_count < 10:
            score -= 0.1

        return max(0.1, min(1.0, score))

    def _classify_content(self, text: str) -> str:
        """Classify content type for freshness calibration."""
        if not text:
            return "general"

        text_lower = text.lower()

        # Check time-sensitive patterns
        time_sensitive_score = sum(
            1 for pat in TIME_SENSITIVE_PATTERNS if re.search(pat, text_lower)
        )
        durable_score = sum(
            1 for pat in DURABLE_PATTERNS if re.search(pat, text_lower)
        )

        if time_sensitive_score > durable_score:
            return "time_sensitive"
        elif durable_score > time_sensitive_score:
            return "durable"
        else:
            return "general"

    def _build_warning(self, entry: Dict[str, Any], status: str) -> Dict[str, Any]:
        """Build a warning dict for a stale/forgotten entry."""
        now_ms = int(time.time() * 1000)
        last_accessed = entry.get("last_accessed_at", 0)
        days_since = (now_ms - last_accessed) / 86400000 if last_accessed else None

        action = self._recommend_action(entry, status)

        return {
            "chunk_id": entry.get("chunk_id", ""),
            "freshness_status": status,
            "importance_score": entry.get("importance_score", 0),
            "access_count": entry.get("access_count", 0),
            "last_accessed_at": last_accessed,
            "days_since_access": round(days_since, 1) if days_since else None,
            "category": entry.get("category"),
            "team_id": entry.get("team_id"),
            "recommended_action": action,
            "alert_message": self._format_alert_message(entry, status, days_since),
        }

    def _recommend_action(self, entry: Dict[str, Any], status: str) -> str:
        """Recommend an action based on entry health and status."""
        importance = entry.get("importance_score", 0.5)

        if status == "forgotten":
            if importance > 0.7:
                return "re_verify"
            else:
                return "archive"
        elif status == "stale":
            if importance > 0.7:
                return "re_verify"
            elif importance > 0.4:
                return "review"
            else:
                return "monitor"
        elif status == "aging":
            if importance > 0.8:
                return "review"
            else:
                return "monitor"
        else:
            return "none"

    def _format_alert_message(
        self,
        entry: Dict[str, Any],
        status: str,
        days_since: Optional[float],
    ) -> str:
        """Format a human-readable alert message."""
        importance = entry.get("importance_score", 0.5)
        access_count = entry.get("access_count", 0)

        if status == "forgotten":
            days_str = f" ({days_since:.0f} days)" if days_since else ""
            return (
                f"⚠️ Knowledge forgotten{days_str}: "
                f"importance={importance:.2f}, "
                f"accessed {access_count} times total. "
                f"Consider re-verifying or archiving."
            )
        elif status == "stale":
            days_str = f" ({days_since:.0f} days)" if days_since else ""
            return (
                f"🟡 Knowledge stale{days_str}: "
                f"importance={importance:.2f}, "
                f"accessed {access_count} times total. "
                f"May need review."
            )
        elif status == "aging":
            return (
                f"🔵 Knowledge aging: "
                f"importance={importance:.2f}. "
                f"Will become stale soon if not accessed."
            )
        else:
            return f"✅ Knowledge fresh (importance={importance:.2f})"
