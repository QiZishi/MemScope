"""
Command Memory: CLI command tracking and context-aware recommendations

Modules:
  - CommandTracker: CLI command pattern tracking and logging
  - CommandRecommender: Context-aware command recommendations
"""

from .command_tracker import CommandTracker
from .recommender import CommandRecommender

__all__ = ["CommandTracker", "CommandRecommender"]

# Backward compatibility aliases (formerly Direction A)
DirectionATracker = CommandTracker
DirectionARecommender = CommandRecommender
