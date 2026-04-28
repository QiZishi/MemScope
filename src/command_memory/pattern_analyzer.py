"""
Direction A: CLI Command Memory - Pattern analysis extracted from CommandRecommender.

Provides detailed analysis of command usage patterns including time distribution
and project-level command grouping.
"""

import logging
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Analyzes command usage patterns with time and project breakdowns."""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: Data store instance with get_command_patterns and get_command_history.
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
            time_distribution = self.analyze_time_distribution(history)

            # Project commands
            project_commands = self.analyze_project_commands(patterns)

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
                "time_distribution": time_distribution,
                "project_commands": project_commands,
                "total_commands": total_commands,
                "unique_commands": unique_commands,
                "avg_success_rate": round(avg_success_rate, 3),
            }
        except Exception as e:
            logger.error(f"PatternAnalyzer.analyze_patterns failed: {e}")
            return {
                "top_commands": [],
                "time_distribution": {},
                "project_commands": {},
                "total_commands": 0,
                "unique_commands": 0,
                "avg_success_rate": 0.0,
            }

    def analyze_time_distribution(self, history: List[Dict[str, Any]]) -> Dict[int, int]:
        """
        Analyze hour-of-day usage distribution from command history.

        Args:
            history: List of command history entries with 'createdAt' timestamps.

        Returns:
            Dict mapping hour (0-23) to number of commands executed in that hour.
        """
        hour_counts: Dict[int, int] = {}
        for entry in history:
            ts = entry.get("createdAt", 0)
            if ts > 0:
                # Convert ms timestamp to hour of day
                hour = int((ts / 1000) % 86400) // 3600
                hour_counts[hour] = hour_counts.get(hour, 0) + 1
        return hour_counts

    def analyze_project_commands(
        self, patterns: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group commands by project and sort by frequency.

        Args:
            patterns: List of command pattern dicts with 'project_path',
                      'command', and 'frequency' keys.

        Returns:
            Dict mapping project path to sorted list of command dicts
            (each with 'command' and 'frequency' keys). Entries with no
            project_path are grouped under '__global__'.
        """
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

        return dict(project_commands)
