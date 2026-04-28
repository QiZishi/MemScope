"""
MemOS Local Viewer package.

Provides a built-in web dashboard for browsing memories, tasks,
skills, timeline, tool logs, and shared memories.
"""

from .server import ViewerServer

__all__ = ["ViewerServer"]
