"""
Direction A: CLI Command Memory - Tracks and recommends CLI commands.
"""

import logging
import json
import time
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class CommandTracker:
    """Tracks CLI command usage and provides recommendations."""

    def __init__(self, store: Any) -> None:
        """
        Args:
            store: SqliteStore instance for persistence.
        """
        self.store = store

    def log_command(
        self,
        owner: str,
        command: str,
        args: Optional[str] = None,
        project_path: Optional[str] = None,
        exit_code: Optional[int] = None,
        working_dir: Optional[str] = None,
        session_key: Optional[str] = None,
    ) -> str:
        """
        Record a command to command_history and auto-update command_patterns.

        Returns:
            The command_history row ID, or empty string on failure.
        """
        try:
            # Extract the base command (first token) and base+subcommand
            parts = command.strip().split()
            base_cmd = parts[0] if parts else command
            # Also track base+subcommand (e.g., "git commit", "docker build")
            sub_cmd = f"{parts[0]} {parts[1]}" if len(parts) >= 2 else None

            # Log to command_history
            cmd_id = self.store.log_command(
                owner=owner,
                command=command,
                args=args,
                project_path=project_path,
                exit_code=exit_code,
                working_dir=working_dir,
                session_key=session_key,
            )

            # Auto-update command_patterns with the base command
            self.store.update_command_pattern(
                owner=owner,
                command=base_cmd,
                project_path=project_path,
                exit_code=exit_code,
            )

            # Also track subcommand pattern (e.g., "git commit")
            if sub_cmd and sub_cmd != base_cmd:
                self.store.update_command_pattern(
                    owner=owner,
                    command=sub_cmd,
                    project_path=project_path,
                    exit_code=exit_code,
                )

            return cmd_id
        except Exception as e:
            logger.error(f"CommandTracker.log_command failed: {e}")
            return ""

    def get_frequent_commands(
        self,
        owner: str,
        project_path: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get frequently used commands for an owner.

        Returns:
            List of command pattern dicts sorted by frequency.
        """
        try:
            patterns = self.store.get_command_patterns(
                owner=owner,
                project_path=project_path,
                limit=limit,
            )
            return patterns
        except Exception as e:
            logger.error(f"CommandTracker.get_frequent_commands failed: {e}")
            return []

    def get_project_commands(
        self,
        owner: str,
        project_path: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Get frequently used commands for a specific project.

        Returns:
            List of command pattern dicts for the project.
        """
        try:
            return self.store.get_command_patterns(
                owner=owner,
                project_path=project_path,
                limit=limit,
            )
        except Exception as e:
            logger.error(f"CommandTracker.get_project_commands failed: {e}")
            return []

    def recommend(
        self,
        owner: str,
        prefix: Optional[str] = None,
        project_path: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Recommend commands based on context.

        Strategy:
            1. If prefix is given, match against command patterns by prefix.
            2. If project_path is given, prioritize project-specific commands.
            3. Fall back to global high-frequency commands.

        Returns:
            List of recommended command dicts.
        """
        try:
            # Get all patterns for the owner
            all_patterns = self.store.get_command_patterns(owner=owner, limit=200)

            if not all_patterns:
                return []

            candidates = all_patterns

            # Filter by prefix if provided
            if prefix:
                prefix_lower = prefix.lower()
                prefix_matches = [
                    p for p in candidates
                    if p.get("command", "").lower().startswith(prefix_lower)
                ]
                if prefix_matches:
                    candidates = prefix_matches

            # If project_path given, boost project-specific commands
            if project_path:
                project_cmds = [
                    p for p in candidates
                    if p.get("project_path") == project_path
                ]
                if project_cmds:
                    # Project commands first, then global ones
                    global_cmds = [
                        p for p in candidates
                        if p.get("project_path") != project_path
                    ]
                    candidates = project_cmds + global_cmds

            # Sort by frequency descending
            candidates.sort(key=lambda x: x.get("frequency", 0), reverse=True)

            return candidates[:limit]
        except Exception as e:
            logger.error(f"CommandTracker.recommend failed: {e}")
            return []
