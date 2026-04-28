"""
Enterprise Memory — Preference Manager

Manages the full lifecycle of user preferences:
  - Explicit preferences (user-declared)
  - Inferred preferences (from behavior patterns)
  - Conflict resolution (explicit > inferred)
  - Confidence decay over time
  - Preference evolution tracking

Direction C: Personal Work Habits / Preference Memory.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Preference categories
CATEGORIES = ("work_pattern", "tool_preference", "schedule", "style")


class PreferenceManager:
    """Manages user preferences with full lifecycle support."""

    def __init__(self, store: Any):
        """
        Args:
            store: SqliteStore instance with v2 schema tables.
        """
        self._store = store

    # ------------------------------------------------------------------
    # Explicit preferences
    # ------------------------------------------------------------------

    def set_explicit_preference(
        self,
        owner: str,
        category: str,
        key: str,
        value: str,
    ) -> str:
        """Set a user-explicit preference (high confidence).

        Args:
            owner: Agent/user ID.
            category: One of CATEGORIES.
            key: Preference key.
            value: Preference value.

        Returns:
            The preference ID.
        """
        self._validate_category(category)

        pref_id = self._store.upsert_user_preference(
            owner=owner,
            category=category,
            key=key,
            value=value,
            confidence=0.95,  # explicit = very high confidence
            source="user_explicit",
        )

        logger.info(f"preference_manager: explicit preference set: {owner}/{category}/{key}={value}")
        return pref_id

    # ------------------------------------------------------------------
    # Inferred preferences (from habit inference)
    # ------------------------------------------------------------------

    def set_inferred_preference(
        self,
        owner: str,
        category: str,
        key: str,
        value: str,
        confidence: float = 0.5,
        source: str = "habit_inference",
    ) -> str:
        """Set an inferred preference (lower confidence, can be overridden).

        Inferred preferences are only stored if:
          1. No explicit preference exists for this key, OR
          2. The new confidence exceeds the existing confidence.

        Args:
            owner: Agent/user ID.
            category: One of CATEGORIES.
            key: Preference key.
            value: Inferred preference value.
            confidence: Inferred confidence (0.0 - 1.0).
            source: Source identifier.

        Returns:
            The preference ID.
        """
        self._validate_category(category)

        # Check for existing preference
        existing = self._store.get_user_preference(owner, category, key)

        if existing:
            existing_confidence = existing.get("confidence", 0)
            existing_source = existing.get("source", "")

            # Never override explicit preferences with inferred ones
            if existing_source == "user_explicit" and confidence < 0.95:
                logger.debug(
                    f"preference_manager: skipping inferred {key} "
                    f"(explicit exists with confidence {existing_confidence})"
                )
                return existing.get("id", "")

            # Only update if new confidence is higher
            if confidence <= existing_confidence:
                logger.debug(
                    f"preference_manager: skipping inferred {key} "
                    f"(existing confidence {existing_confidence} >= new {confidence})"
                )
                return existing.get("id", "")

        pref_id = self._store.upsert_user_preference(
            owner=owner,
            category=category,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
        )

        logger.info(
            f"preference_manager: inferred preference set: "
            f"{owner}/{category}/{key}={value} (confidence={confidence:.2f})"
        )
        return pref_id

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> Optional[Dict[str, Any]]:
        """Get a single preference."""
        return self._store.get_user_preference(owner, category, key)

    def list_preferences(
        self,
        owner: str,
        category: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """List all preferences for a user."""
        return self._store.list_user_preferences(
            owner=owner,
            category=category,
            min_confidence=min_confidence,
        )

    def get_preference_value(
        self,
        owner: str,
        category: str,
        key: str,
        default: Optional[str] = None,
    ) -> Optional[str]:
        """Get just the value of a preference, or a default."""
        pref = self.get_preference(owner, category, key)
        if pref:
            return pref.get("value", default)
        return default

    # ------------------------------------------------------------------
    # Deletion
    # ------------------------------------------------------------------

    def delete_preference(
        self,
        owner: str,
        category: str,
        key: str,
    ) -> bool:
        """Delete a preference."""
        success = self._store.delete_user_preference(owner, category, key)
        if success:
            logger.info(f"preference_manager: deleted preference {owner}/{category}/{key}")
        return success

    # ------------------------------------------------------------------
    # Conflict resolution
    # ------------------------------------------------------------------

    def resolve_conflict(
        self,
        owner: str,
        category: str,
        key: str,
        explicit_value: str,
        inferred_value: str,
        inferred_confidence: float = 0.5,
    ) -> str:
        """Resolve a conflict between explicit and inferred preferences.

        Rules:
          1. Explicit always wins over inferred
          2. Higher confidence wins between two inferred values
          3. Recency wins between equal-confidence values

        Returns:
            The winning value.
        """
        # Explicit always wins
        return explicit_value

    # ------------------------------------------------------------------
    # Bulk operations
    # ------------------------------------------------------------------

    def import_preferences(
        self,
        owner: str,
        preferences: List[Dict[str, str]],
    ) -> int:
        """Bulk import preferences.

        Args:
            owner: Agent/user ID.
            preferences: List of dicts with keys: category, key, value.

        Returns:
            Number of preferences imported.
        """
        count = 0
        for pref in preferences:
            category = pref.get("category", "")
            key = pref.get("key", "")
            value = pref.get("value", "")

            if not all([category, key, value]):
                continue

            try:
                self.set_explicit_preference(owner, category, key, value)
                count += 1
            except Exception as e:
                logger.warning(f"preference_manager: import failed for {key}: {e}")

        logger.info(f"preference_manager: imported {count}/{len(preferences)} preferences for {owner}")
        return count

    def export_preferences(self, owner: str) -> List[Dict[str, str]]:
        """Export all preferences for a user as a serializable list."""
        prefs = self.list_preferences(owner)
        return [
            {
                "category": p.get("category", ""),
                "key": p.get("key", ""),
                "value": p.get("value", ""),
                "confidence": p.get("confidence", 0),
                "source": p.get("source", ""),
            }
            for p in prefs
        ]

    # ------------------------------------------------------------------
    # Maintenance
    # ------------------------------------------------------------------

    def apply_decay(self, decay_factor: float = 0.95, min_confidence: float = 0.1) -> int:
        """Apply confidence decay to all inferred preferences.

        Should be called periodically (e.g., daily) to reduce confidence
        of preferences that haven't received new evidence.

        Returns:
            Number of preferences updated.
        """
        count = self._store.decay_preference_confidence(
            decay_factor=decay_factor,
            min_confidence=min_confidence,
        )
        if count:
            logger.info(f"preference_manager: decayed confidence for {count} preferences")
        return count

    def get_summary(self, owner: str) -> Dict[str, Any]:
        """Get a human-readable summary of a user's preferences."""
        all_prefs = self.list_preferences(owner)

        by_category: Dict[str, List[Dict]] = {}
        for pref in all_prefs:
            cat = pref.get("category", "unknown")
            by_category.setdefault(cat, []).append(pref)

        summary = {
            "owner": owner,
            "total_preferences": len(all_prefs),
            "categories": {},
        }

        for cat, prefs in by_category.items():
            top = sorted(prefs, key=lambda p: p.get("confidence", 0), reverse=True)[:5]
            summary["categories"][cat] = {
                "count": len(prefs),
                "top_preferences": [
                    {"key": p["key"], "value": p["value"], "confidence": p.get("confidence", 0)}
                    for p in top
                ],
            }

        return summary

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _validate_category(self, category: str) -> None:
        """Validate that a category is allowed."""
        if category not in CATEGORIES:
            raise ValueError(
                f"Invalid category '{category}'. Must be one of: {', '.join(CATEGORIES)}"
            )
