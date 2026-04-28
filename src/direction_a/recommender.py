"""
Direction A: CLI Command Memory - Advanced pattern analysis and context-aware recommendations.
"""

import logging
import json
import time
import re
import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandRecommender:
    """Analyzes command usage patterns and provides context-aware recommendations."""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: SqliteStore instance for persistence.
        """
        self.store = store

    def analyze_patterns(self, owner: str) -> Dict[str, Any]:
        """
        Analyze the user's command usage patterns.

        Returns:
            Dict containing:
                - top_commands: top 10 most frequent commands
                - time_distribution: hour-of-day usage distribution
                - project_commands: commands grouped by project
                - total_commands: total command count
                - unique_commands: number of unique commands
                - avg_success_rate: average success rate across patterns
        """
        try:
            patterns = self.store.get_command_patterns(owner=owner, limit=500)
            history = self.store.get_command_history(owner=owner, limit=1000)

            if not patterns:
                return {
                    "top_commands": [],
                    "time_distribution": {},
                    "project_commands": {},
                    "total_commands": 0,
                    "unique_commands": 0,
                    "avg_success_rate": 0.0,
                }

            # Top 10 commands
            top_commands = sorted(
                patterns, key=lambda x: x.get("frequency", 0), reverse=True
            )[:10]

            # Time distribution (hour of day)
            hour_counts: Dict[int, int] = Counter()
            for entry in history:
                ts = entry.get("createdAt", 0)
                if ts > 0:
                    # Convert ms timestamp to hour of day
                    hour = int((ts / 1000) % 86400) // 3600
                    hour_counts[hour] = hour_counts.get(hour, 0) + 1

            # Project commands
            project_commands: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
            for p in patterns:
                proj = p.get("project_path") or "__global__"
                project_commands[proj].append({
                    "command": p.get("command", ""),
                    "frequency": p.get("frequency", 0),
                })

            # Sort each project's commands by frequency
            for proj in project_commands:
                project_commands[proj].sort(
                    key=lambda x: x.get("frequency", 0), reverse=True
                )

            # Stats
            total_commands = sum(p.get("frequency", 0) for p in patterns)
            unique_commands = len(patterns)
            success_rates = [
                p.get("success_rate", 1.0) for p in patterns
                if p.get("success_rate") is not None
            ]
            avg_success_rate = (
                sum(success_rates) / len(success_rates) if success_rates else 0.0
            )

            return {
                "top_commands": [
                    {
                        "command": p.get("command", ""),
                        "frequency": p.get("frequency", 0),
                        "success_rate": round(p.get("success_rate", 1.0), 3),
                    }
                    for p in top_commands
                ],
                "time_distribution": dict(hour_counts),
                "project_commands": dict(project_commands),
                "total_commands": total_commands,
                "unique_commands": unique_commands,
                "avg_success_rate": round(avg_success_rate, 3),
            }
        except Exception as e:
            logger.error(f"CommandRecommender.analyze_patterns failed: {e}")
            return {
                "top_commands": [],
                "time_distribution": {},
                "project_commands": {},
                "total_commands": 0,
                "unique_commands": 0,
                "avg_success_rate": 0.0,
            }

    def context_recommend(
        self,
        owner: str,
        current_dir: Optional[str] = None,
        recent_commands: Optional[List[str]] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Context-aware command recommendation.

        Uses a scoring system:
            - Base score: frequency-based
            - Project boost: +0.3 if command matches current_dir project
            - Recency boost: +0.2 if command appeared in recent_commands
            - Success boost: +0.1 if success_rate > 0.8

        Args:
            owner: The user/owner identifier.
            current_dir: Current working directory (used for project matching).
            recent_commands: List of recently executed commands (for sequence pattern).
            limit: Max number of recommendations.

        Returns:
            List of recommended command dicts with scores.
        """
        try:
            patterns = self.store.get_command_patterns(owner=owner, limit=200)

            if not patterns:
                return []

            # Normalize recent commands to base commands
            recent_bases: set = set()
            if recent_commands:
                for rc in recent_commands:
                    if rc and rc.strip():
                        recent_bases.add(rc.strip().split()[0])

            # Score each pattern
            scored: List[Dict[str, Any]] = []
            max_freq = max((p.get("frequency", 1) for p in patterns), default=1)

            for p in patterns:
                score = 0.0
                cmd = p.get("command", "")
                freq = p.get("frequency", 0)
                sr = p.get("success_rate", 1.0)
                pat_project = p.get("project_path")

                # Base score: normalized frequency (0.0 - 0.4)
                score += 0.4 * (freq / max_freq) if max_freq > 0 else 0.0

                # Project boost (0.3)
                if current_dir and pat_project:
                    # Check if current_dir starts with or equals the project path
                    if current_dir.startswith(pat_project) or pat_project.startswith(current_dir):
                        score += 0.3
                    elif pat_project in current_dir or current_dir in pat_project:
                        score += 0.15

                # Recency boost (0.2)
                if cmd in recent_bases:
                    score += 0.2

                # Success rate boost (0.1)
                if sr is not None and sr > 0.8:
                    score += 0.1

                entry = dict(p)
                entry["recommendation_score"] = round(score, 4)
                scored.append(entry)

            # Sort by score descending
            scored.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)

            return scored[:limit]
        except Exception as e:
            logger.error(f"CommandRecommender.context_recommend failed: {e}")
            return []
