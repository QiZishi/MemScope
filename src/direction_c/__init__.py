"""
Direction C: Personal Work Habits & Preference Memory

Modules:
  - PreferenceExtractor: Rule-based preference extraction from conversations
  - PreferenceManager: Preference lifecycle management with conflict resolution
  - HabitInference: Behavior pattern inference from historical data
"""

from .preference_extractor import PreferenceExtractor
from .preference_manager import PreferenceManager
from .habit_inference import HabitInference

__all__ = ["PreferenceExtractor", "PreferenceManager", "HabitInference"]
