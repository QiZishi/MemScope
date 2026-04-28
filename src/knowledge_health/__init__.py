"""
Knowledge Health: Forgetting curve models and team knowledge gap detection

Modules:
  - EbbinghausModel: Ebbinghaus forgetting curve modeling
  - FreshnessMonitor: Knowledge freshness tracking and alerts
  - GapDetector: Team knowledge gap detection and mapping
"""

from .ebbinghaus import EbbinghausModel
from .freshness_monitor import FreshnessMonitor
from .gap_detector import GapDetector
from .knowledge_evaluator import KnowledgeEvaluator

__all__ = ['EbbinghausModel', 'FreshnessMonitor', 'GapDetector', 'KnowledgeEvaluator']

# Backward compatibility aliases (formerly Direction D)
DirectionDModel = EbbinghausModel
DirectionDMonitor = FreshnessMonitor
DirectionDDetector = GapDetector
