"""
Enterprise Memory — Habit Inference Engine

Infers personal work habits and behavior patterns from historical interaction
data (tool_logs, chunk timestamps, session patterns).

Direction C: Personal Work Habits / Preference Memory.

Strategy:
  1. Time-of-day pattern mining — analyze when the user is most active
  2. Tool usage frequency — rank tools by usage count per user
  3. Topic clustering — group recent chunks by content similarity
  4. Workflow sequence mining — detect repeated multi-step sequences
"""

import json
import logging
import re
import time
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class HabitInference:
    """Infers behavior patterns from historical interaction data."""

    def __init__(self, store: Any, preference_manager: Any = None):
        """
        Args:
            store: SqliteStore instance (must have v2 schema tables).
            preference_manager: Optional PreferenceManager for writing
                                inferred preferences.
        """
        self._store = store
        self._preference_manager = preference_manager

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def infer_patterns(self, owner: str) -> List[Dict[str, Any]]:
        """Run full pattern inference pipeline for a user.

        Returns:
            List of newly created / updated behavior pattern records.
        """
        patterns: List[Dict[str, Any]] = []

        try:
            time_patterns = self._infer_time_patterns(owner)
            patterns.extend(time_patterns)
        except Exception as e:
            logger.warning(f"habit_inference: time pattern inference failed: {e}")

        try:
            tool_patterns = self._infer_tool_frequency(owner)
            patterns.extend(tool_patterns)
        except Exception as e:
            logger.warning(f"habit_inference: tool frequency inference failed: {e}")

        try:
            topic_patterns = self._infer_topic_clusters(owner)
            patterns.extend(topic_patterns)
        except Exception as e:
            logger.warning(f"habit_inference: topic cluster inference failed: {e}")

        try:
            workflow_patterns = self._infer_workflow_sequences(owner)
            patterns.extend(workflow_patterns)
        except Exception as e:
            logger.warning(f"habit_inference: workflow inference failed: {e}")

        logger.info(f"habit_inference: inferred {len(patterns)} patterns for owner={owner}")
        return patterns

    def _upsert_pattern(
        self,
        owner: str,
        pattern_type: str,
        description: str,
        data: Optional[Dict[str, Any]],
        confidence: float,
        sample_count: int,
    ) -> str:
        """Insert or update a behavior pattern, preventing duplicates.

        Checks for existing patterns of the same type for this owner
        and updates them instead of creating new records.
        """
        existing = self._store.get_behavior_patterns(
            owner=owner, pattern_type=pattern_type, limit=1
        )
        if existing:
            pattern_id = existing[0]["id"]
            self._store.update_behavior_pattern(
                pattern_id,
                description=description,
                data=data,
                confidence=confidence,
                sample_count=sample_count,
            )
            return pattern_id
        else:
            return self._store.insert_behavior_pattern(
                owner=owner,
                pattern_type=pattern_type,
                description=description,
                data=data,
                confidence=confidence,
                sample_count=sample_count,
            )

    # ------------------------------------------------------------------
    # Time-of-day patterns
    # ------------------------------------------------------------------

    def _infer_time_patterns(self, owner: str) -> List[Dict[str, Any]]:
        """Analyze tool_logs timestamps to find when the user is most active."""
        tool_logs = self._store.get_tool_logs(limit=500, owner=owner)
        if len(tool_logs) < 10:
            return []

        # Bucket by hour of day
        hour_counts: Counter = Counter()
        for log in tool_logs:
            ts = log.get("ts", 0)
            if ts > 1e12:
                ts = ts / 1000  # convert ms to seconds
            try:
                dt = datetime.fromtimestamp(ts)
                hour_counts[dt.hour] += 1
            except (OSError, ValueError):
                continue

        if not hour_counts:
            return []

        # Find peak hours (above average)
        total = sum(hour_counts.values())
        avg_per_hour = total / 24
        peak_hours = sorted(
            [(h, c) for h, c in hour_counts.items() if c > avg_per_hour * 1.2],
            key=lambda x: x[1],
            reverse=True,
        )

        patterns: List[Dict[str, Any]] = []

        if peak_hours:
            peak_range = self._format_hour_range([h for h, _ in peak_hours[:5]])
            description = f"Most active during: {peak_range}"
            data = {
                "peak_hours": {str(h): c for h, c in peak_hours[:10]},
                "total_samples": total,
            }
            confidence = min(0.5 + (total / 200) * 0.4, 0.95)

            pattern_id = self._upsert_pattern(
                owner=owner,
                pattern_type="time_pattern",
                description=description,
                data=data,
                confidence=confidence,
                sample_count=total,
            )
            patterns.append({
                "id": pattern_id,
                "pattern_type": "time_pattern",
                "description": description,
                "confidence": confidence,
            })

            # Also store as a user preference
            if self._preference_manager:
                self._preference_manager.set_inferred_preference(
                    owner=owner,
                    category="schedule",
                    key="peak_active_hours",
                    value=peak_range,
                    confidence=confidence,
                    source="habit_inference",
                )

        # Detect day-of-week patterns
        day_counts: Counter = Counter()
        for log in tool_logs:
            ts = log.get("ts", 0)
            if ts > 1e12:
                ts = ts / 1000
            try:
                dt = datetime.fromtimestamp(ts)
                day_counts[dt.strftime("%A")] += 1
            except (OSError, ValueError):
                continue

        if day_counts:
            max_day = day_counts.most_common(1)[0]
            min_day = day_counts.most_common()[-1] if len(day_counts) > 1 else max_day
            if max_day[1] > min_day[1] * 1.5 and max_day[1] > 5:
                description = f"Most active day: {max_day[0]} ({max_day[1]} actions), least: {min_day[0]} ({min_day[1]} actions)"
                data = {
                    "day_distribution": dict(day_counts),
                    "busiest_day": max_day[0],
                    "quietest_day": min_day[0],
                }
                confidence = min(0.4 + (total / 100) * 0.3, 0.85)

                pattern_id = self._upsert_pattern(
                    owner=owner,
                    pattern_type="time_pattern",
                    description=description,
                    data=data,
                    confidence=confidence,
                    sample_count=total,
                )
                patterns.append({
                    "id": pattern_id,
                    "pattern_type": "time_pattern",
                    "description": description,
                    "confidence": confidence,
                })

        return patterns

    # ------------------------------------------------------------------
    # Tool usage frequency
    # ------------------------------------------------------------------

    def _infer_tool_frequency(self, owner: str) -> List[Dict[str, Any]]:
        """Rank tools by usage frequency to find tool preferences."""
        tool_logs = self._store.get_tool_logs(limit=500, owner=owner)
        if len(tool_logs) < 5:
            return []

        tool_counts: Counter = Counter()
        for log in tool_logs:
            tool_name = log.get("tool", "")
            if tool_name:
                tool_counts[tool_name] += 1

        if not tool_counts:
            return []

        total = sum(tool_counts.values())
        ranked = tool_counts.most_common(10)

        # Build description
        top_tools = [f"{name} ({count}×)" for name, count in ranked[:5]]
        description = f"Top tools: {', '.join(top_tools)}"

        data = {
            "tool_ranking": {name: count for name, count in ranked},
            "total_tool_calls": total,
        }

        confidence = min(0.5 + (total / 100) * 0.4, 0.95)

        pattern_id = self._upsert_pattern(
            owner=owner,
            pattern_type="tool_frequency",
            description=description,
            data=data,
            confidence=confidence,
            sample_count=total,
        )

        patterns = [{
            "id": pattern_id,
            "pattern_type": "tool_frequency",
            "description": description,
            "confidence": confidence,
        }]

        # Store top tool as preference
        if ranked and self._preference_manager:
            top_tool = ranked[0][0]
            self._preference_manager.set_inferred_preference(
                owner=owner,
                category="tool_preference",
                key="most_used_tool",
                value=top_tool,
                confidence=confidence,
                source="habit_inference",
            )

        return patterns

    # ------------------------------------------------------------------
    # Topic clustering
    # ------------------------------------------------------------------

    def _infer_topic_clusters(self, owner: str) -> List[Dict[str, Any]]:
        """Group recent memory chunks into topic clusters."""
        chunks = self._store.get_all_chunks(limit=100)
        owner_chunks = [c for c in chunks if c.get("owner") == owner or not c.get("owner")]

        if len(owner_chunks) < 10:
            return []

        # Simple keyword-based clustering
        keyword_groups: Dict[str, List[str]] = defaultdict(list)
        for chunk in owner_chunks:
            content = chunk.get("content", "")
            keywords = self._extract_keywords(content)
            for kw in keywords[:3]:  # top 3 keywords
                keyword_groups[kw].append(chunk.get("id", ""))

        # Find clusters with 3+ chunks
        clusters = {
            kw: chunk_ids
            for kw, chunk_ids in keyword_groups.items()
            if len(chunk_ids) >= 3
        }

        patterns: List[Dict[str, Any]] = []
        sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)

        for keyword, chunk_ids in sorted_clusters[:5]:
            description = f"Frequent topic cluster: '{keyword}' ({len(chunk_ids)} related memories)"
            data = {
                "keyword": keyword,
                "chunk_ids": chunk_ids[:20],
                "cluster_size": len(chunk_ids),
            }
            confidence = min(0.4 + len(chunk_ids) / 20, 0.9)

            pattern_id = self._upsert_pattern(
                owner=owner,
                pattern_type="topic_cluster",
                description=description,
                data=data,
                confidence=confidence,
                sample_count=len(chunk_ids),
            )
            patterns.append({
                "id": pattern_id,
                "pattern_type": "topic_cluster",
                "description": description,
                "confidence": confidence,
            })

        return patterns

    # ------------------------------------------------------------------
    # Workflow sequence mining
    # ------------------------------------------------------------------

    def _infer_workflow_sequences(self, owner: str) -> List[Dict[str, Any]]:
        """Detect repeated tool-call sequences (workflows)."""
        tool_logs = self._store.get_tool_logs(limit=500, owner=owner)
        if len(tool_logs) < 20:
            return []

        # Sort by timestamp
        sorted_logs = sorted(tool_logs, key=lambda x: x.get("ts", 0))

        # Extract tool sequences (window of 3-5 consecutive calls)
        sequences: Counter = Counter()
        for window_size in (3, 4, 5):
            for i in range(len(sorted_logs) - window_size + 1):
                seq = tuple(
                    sorted_logs[j].get("tool", "")
                    for j in range(i, i + window_size)
                )
                if all(t for t in seq):  # skip empty tool names
                    sequences[seq] += 1

        # Find repeated sequences (appearing 3+ times)
        repeated = [
            (seq, count)
            for seq, count in sequences.items()
            if count >= 3
        ]
        repeated.sort(key=lambda x: x[1], reverse=True)

        patterns: List[Dict[str, Any]] = []

        for seq, count in repeated[:5]:
            seq_str = " → ".join(seq)
            description = f"Repeated workflow ({count}×): {seq_str}"
            data = {
                "sequence": list(seq),
                "occurrence_count": count,
                "window_sizes": [len(seq)],
            }
            confidence = min(0.5 + count / 20, 0.95)

            pattern_id = self._upsert_pattern(
                owner=owner,
                pattern_type="workflow",
                description=description,
                data=data,
                confidence=confidence,
                sample_count=count,
            )
            patterns.append({
                "id": pattern_id,
                "pattern_type": "workflow",
                "description": description,
                "confidence": confidence,
            })

        return patterns

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_keywords(self, text: str, top_n: int = 5) -> List[str]:
        """Extract top keywords from text using simple TF approach."""
        if not text:
            return []

        # Tokenize: split on whitespace and non-alphanumeric
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

        # Simple stop words
        stop_words = {
            "the", "and", "for", "are", "but", "not", "you", "all",
            "can", "had", "her", "was", "one", "our", "out", "has",
            "have", "been", "from", "this", "that", "with", "they",
            "will", "each", "make", "like", "into", "than", "then",
            "them", "were", "what", "when", "your", "how", "its",
            "also", "just", "over", "such", "some", "very", "would",
            "could", "should", "about", "other", "which", "their",
        }

        word_counts = Counter(w for w in words if w not in stop_words)
        return [w for w, _ in word_counts.most_common(top_n)]

    def _format_hour_range(self, hours: List[int]) -> str:
        """Format a list of hours into a human-readable range string."""
        if not hours:
            return "unknown"

        sorted_hours = sorted(set(hours))

        if len(sorted_hours) <= 2:
            return ", ".join(f"{h:02d}:00" for h in sorted_hours)

        # Group into contiguous ranges
        ranges = []
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

        parts = []
        for s, e in ranges:
            if s == e:
                parts.append(f"{s:02d}:00")
            else:
                parts.append(f"{s:02d}:00-{e + 1:02d}:00")

        return ", ".join(parts)
