"""
Enterprise Memory — Preference Module (Direction C)

Provides personal habit inference and preference management for
the enterprise-memory plugin.
"""

from .habit_inference import HabitInference
from .preference_manager import PreferenceManager

__all__ = ["HabitInference", "PreferenceManager"]
