"""
Enterprise Memory Plugin for Hermes Agent.

Extends memos-local-hermes-plugin with:
  - Direction C: Personal work habits / preference memory
  - Direction D: Team knowledge health / forgetting alerts

Provides all original memos tools plus:
  preference_get, preference_set, preference_list, preference_delete,
  habit_patterns, knowledge_health, knowledge_gaps, knowledge_alerts,
  team_knowledge_map
"""

import os
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent.memory_provider import MemoryProvider

logger = logging.getLogger(__name__)

__all__ = ["EnterpriseMemoryProvider", "register"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> int:
    """Current timestamp in milliseconds."""
    return int(time.time() * 1000)


def _json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, default=str)


def _extract_agent_id(session_id: str) -> str:
    """Derive agent_id from session_id."""
    return session_id.split("/")[0] if "/" in session_id else session_id


# ---------------------------------------------------------------------------
# Main provider
# ---------------------------------------------------------------------------

class EnterpriseMemoryProvider(MemoryProvider):
    """Enterprise memory provider for Hermes Agent.

    Wraps the original memos-local storage and adds preference + alert modules.
    """

    def __init__(self):
        self._api_key: str = ""
        self._session_id: str = ""
        self._hermes_home: Optional[Path] = None
        self._initialized: bool = False

        # Core memos subsystems
        self._store: Any = None
        self._embedder: Any = None
        self._recall_engine: Any = None
        self._skill_generation_enabled: bool = False
        self._viewer: Any = None

        # Enterprise subsystems
        self._enterprise_enabled: bool = False
        self._preference_manager: Any = None
        self._habit_inference: Any = None
        self._freshness_monitor: Any = None
        self._gap_detector: Any = None

    # ------------------------------------------------------------------
    # MemoryProvider interface
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "enterprise-memory"

    def is_available(self) -> bool:
        """Check if this provider can activate. NO network calls."""
        embedding_model = os.environ.get("MEMOS_EMBEDDING_MODEL")
        return bool(embedding_model)

    def initialize(self, session_id: str, **kwargs) -> None:
        """Called once at agent startup."""
        from hermes_constants import get_hermes_home

        self._session_id = session_id
        self._hermes_home = get_hermes_home()
        self._skill_generation_enabled = kwargs.get("skill_generation_enabled", False)
        self._enterprise_enabled = kwargs.get("enterprise_features", True)

        db_path = self._hermes_home / "memos" / "memos.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # ---- Storage (with v2 schema) ----
        try:
            from .storage.sqlite import SqliteStore
            self._store = SqliteStore(str(db_path))
            # Apply enterprise schema additions
            from .storage.schema_v2 import apply_v2_schema
            apply_v2_schema(self._store.conn)
            logger.info(f"enterprise-memory: database initialized at {db_path}")
        except Exception as e:
            logger.warning(f"enterprise-memory: failed to initialize storage: {e}")
            return

        # ---- Embedder ----
        try:
            from .embedding import Embedder
            self._embedder = Embedder()
        except Exception as e:
            logger.warning(f"enterprise-memory: failed to initialize embedder: {e}")

        # ---- Recall Engine ----
        try:
            from .recall import RecallEngine
            recall_config = {
                "rrf_k": 60,
                "mmr_lambda": 0.7,
                "recency_half_life_days": 14,
                "max_results_default": 10,
                "max_results_max": 20,
                "min_score_default": 0.45,
            }
            self._recall_engine = RecallEngine(
                self._store,
                self._embedder,
                config=recall_config,
            )
            logger.info("enterprise-memory: recall engine initialized (RRF + MMR + recency)")
        except Exception as e:
            logger.warning(f"enterprise-memory: failed to initialize recall engine: {e}")
            return

        # ---- Skill generation (optional) ----
        if self._skill_generation_enabled:
            try:
                from .ingest import TaskProcessor, Summarizer
                from .skill import SkillGenerator, SkillEvaluator, SkillEvolver, SkillInstaller
                from .shared import LLMCaller
                from .context_engine import ContextEngine

                self._llm_caller = LLMCaller(
                    skill_config=kwargs.get("skill_model"),
                    summarizer_config=kwargs.get("summarizer_model"),
                    default_config=kwargs.get("default_model"),
                )
                self._summarizer = Summarizer(
                    self._llm_caller,
                    config={"max_summary_length": 200},
                )
                self._task_processor = TaskProcessor(
                    self._store,
                    self._summarizer,
                    config={"time_gap_threshold_hours": 2},
                )
                self._skill_generator = SkillGenerator(self._store, self._llm_caller)
                self._skill_evaluator = SkillEvaluator(self._store, self._llm_caller)
                self._skill_evolver = SkillEvolver(
                    self._store, self._skill_generator, self._skill_evaluator,
                )
                self._skill_installer = SkillInstaller(str(self._hermes_home))
                self._context_engine = ContextEngine(
                    self._recall_engine,
                    config={"max_memories": 5, "min_score": 0.45},
                )
                logger.info("enterprise-memory: skill evolution system initialized")
            except Exception as e:
                logger.warning(f"enterprise-memory: failed to initialize skill evolution: {e}")
                self._skill_generation_enabled = False

        # ---- Enterprise modules ----
        if self._enterprise_enabled:
            self._init_enterprise_modules(**kwargs)

        self._initialized = True
        logger.info(f"enterprise-memory: fully initialized for session {session_id}")

    def _init_enterprise_modules(self, **kwargs) -> None:
        """Initialize Direction C (preferences) and Direction D (alerts) modules."""
        # Preference / habit module
        try:
            from .preference import PreferenceManager, HabitInference
            self._preference_manager = PreferenceManager(self._store)
            self._habit_inference = HabitInference(
                self._store, self._preference_manager,
            )
            logger.info("enterprise-memory: preference module initialized")
        except Exception as e:
            logger.warning(f"enterprise-memory: failed to init preference module: {e}")

        # Alert / freshness / gap module
        try:
            from .alert import FreshnessMonitor, GapDetector
            stale_days = kwargs.get("stale_threshold_days", 30)
            forgotten_days = kwargs.get("forgotten_threshold_days", 90)
            self._freshness_monitor = FreshnessMonitor(
                self._store,
                stale_threshold_days=stale_days,
                forgotten_threshold_days=forgotten_days,
            )
            self._gap_detector = GapDetector(self._store)
            logger.info("enterprise-memory: alert modules initialized")
        except Exception as e:
            logger.warning(f"enterprise-memory: failed to init alert modules: {e}")

    # ------------------------------------------------------------------
    # Config schema
    # ------------------------------------------------------------------

    def get_config_schema(self) -> List[Dict[str, Any]]:
        """Declare config fields for `hermes memory setup`."""
        return [
            {
                "key": "agent_id",
                "description": "Unique agent identifier for memory isolation",
                "secret": False,
                "required": False,
                "default": "default",
            },
            {
                "key": "default_scope",
                "description": "Default memory search scope: 'private', 'shared', or 'all'",
                "secret": False,
                "required": False,
                "default": "private",
                "choices": ["private", "shared", "all"],
            },
            {
                "key": "skill_generation_enabled",
                "description": "Enable automatic skill generation from completed tasks",
                "secret": False,
                "required": False,
                "default": False,
                "type": "boolean",
            },
            {
                "key": "db_path",
                "description": "SQLite database path (relative to HERMES_HOME)",
                "secret": False,
                "required": False,
                "default": "memos/memos.db",
            },
            {
                "key": "enterprise_features",
                "description": "Enable enterprise features (preferences, alerts, team analysis)",
                "secret": False,
                "required": False,
                "default": True,
                "type": "boolean",
            },
            {
                "key": "preference_inference_enabled",
                "description": "Enable automatic preference/habit inference from interactions",
                "secret": False,
                "required": False,
                "default": True,
                "type": "boolean",
            },
            {
                "key": "knowledge_health_enabled",
                "description": "Enable team knowledge health monitoring and alerts",
                "secret": False,
                "required": False,
                "default": True,
                "type": "boolean",
            },
            {
                "key": "stale_threshold_days",
                "description": "Days before a knowledge entry is considered stale",
                "secret": False,
                "required": False,
                "default": 30,
                "type": "number",
            },
            {
                "key": "forgotten_threshold_days",
                "description": "Days before a knowledge entry is considered forgotten",
                "secret": False,
                "required": False,
                "default": 90,
                "type": "number",
            },
        ]

    def save_config(self, values: Dict[str, Any], hermes_home: str) -> None:
        """Write non-secret config to native location."""
        import json
        config_path = Path(hermes_home) / "memos" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(values, indent=2))

    # ------------------------------------------------------------------
    # Tool schemas
    # ------------------------------------------------------------------

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return tool schemas for agent tool injection."""
        if not self._initialized:
            return []

        tools = [
            # ========== Original memos tools ==========
            {
                "name": "memory_search",
                "description": (
                    "Search long-term conversation memory for past conversations, "
                    "user preferences, decisions, and experiences. "
                    "Use scope='private' for only your memories, 'shared' for team memories, "
                    "or 'all' for both."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Short natural language search query (2-5 key words)",
                        },
                        "scope": {
                            "type": "string",
                            "description": "Memory scope: 'private', 'shared', 'all'",
                            "enum": ["private", "shared", "all"],
                            "default": "private",
                        },
                        "maxResults": {
                            "type": "number",
                            "description": "Maximum results to return. Default 10, max 20.",
                        },
                        "minScore": {
                            "type": "number",
                            "description": "Minimum score threshold. Default 0.45, floor 0.35.",
                        },
                        "role": {
                            "type": "string",
                            "description": "Optional role filter: 'user', 'assistant', 'tool', or 'system'.",
                            "enum": ["user", "assistant", "tool", "system"],
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "memory_get",
                "description": (
                    "Get the full original text of a memory chunk. "
                    "Use to verify exact details from a search hit."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunkId": {"type": "string", "description": "From search hit ref.chunkId"},
                        "maxChars": {"type": "number", "description": "Max chars (default 2000, max 8000)"},
                    },
                    "required": ["chunkId"],
                },
            },
            {
                "name": "memory_timeline",
                "description": (
                    "Expand context around a memory search hit. "
                    "Pass the chunkId from a search result to read the surrounding conversation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunkId": {"type": "string", "description": "The chunkId from a memory_search hit"},
                        "window": {"type": "number", "description": "Context window ±N (default 2)"},
                    },
                    "required": ["chunkId"],
                },
            },
            {
                "name": "memory_share",
                "description": (
                    "Share a private memory chunk with other agents or make it globally shared. "
                    "Use this to contribute your learnings to the team knowledge base."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunkId": {"type": "string", "description": "The chunkId to share"},
                        "sharedWith": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agent IDs to share with. Empty = globally shared",
                        },
                    },
                    "required": ["chunkId"],
                },
            },
            {
                "name": "memory_unshare",
                "description": "Make a shared memory chunk private again.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunkId": {"type": "string", "description": "The chunkId to make private"},
                    },
                    "required": ["chunkId"],
                },
            },
            {
                "name": "memory_list_shared",
                "description": "List all memory chunks shared with you or globally shared.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "maxResults": {"type": "number", "description": "Maximum results. Default 50."},
                    },
                },
            },
        ]

        # Skill-related tools (conditional)
        if self._skill_generation_enabled:
            tools.extend([
                {
                    "name": "skill_search",
                    "description": "Search for learned skills (experience guides).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query for skill name or content"},
                            "scope": {
                                "type": "string",
                                "enum": ["mix", "self", "public"],
                                "default": "mix",
                                "description": "Search scope",
                            },
                            "maxResults": {"type": "number", "description": "Max results. Default 10."},
                        },
                        "required": ["query"],
                    },
                },
                {
                    "name": "skill_get",
                    "description": "Retrieve a skill by skillId or taskId.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skillId": {"type": "string"},
                            "taskId": {"type": "string"},
                        },
                    },
                },
                {
                    "name": "task_summary",
                    "description": "Get the detailed summary of a completed task.",
                    "parameters": {
                        "type": "object",
                        "properties": {"taskId": {"type": "string"}},
                        "required": ["taskId"],
                    },
                },
                {
                    "name": "task_edit",
                    "description": "Edit a task's title, summary, or status.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "taskId": {"type": "string"},
                            "title": {"type": "string"},
                            "summary": {"type": "string"},
                            "status": {"type": "string", "enum": ["active", "completed", "failed"]},
                        },
                        "required": ["taskId"],
                    },
                },
                {
                    "name": "task_delete",
                    "description": "Delete a task and all associated memory chunks.",
                    "parameters": {
                        "type": "object",
                        "properties": {"taskId": {"type": "string"}},
                        "required": ["taskId"],
                    },
                },
                {
                    "name": "skill_edit",
                    "description": "Edit a skill's name or content.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skillId": {"type": "string"},
                            "name": {"type": "string"},
                            "content": {"type": "string"},
                        },
                        "required": ["skillId"],
                    },
                },
                {
                    "name": "skill_delete",
                    "description": "Delete a skill permanently.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skillId": {"type": "string"}},
                        "required": ["skillId"],
                    },
                },
                {
                    "name": "skill_retry",
                    "description": "Retry skill generation for a completed task.",
                    "parameters": {
                        "type": "object",
                        "properties": {"taskId": {"type": "string"}},
                        "required": ["taskId"],
                    },
                },
                {
                    "name": "skill_publish",
                    "description": "Publish a skill to make it public and discoverable.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skillId": {"type": "string"}},
                        "required": ["skillId"],
                    },
                },
                {
                    "name": "skill_unpublish",
                    "description": "Make a published skill private again.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skillId": {"type": "string"}},
                        "required": ["skillId"],
                    },
                },
                {
                    "name": "skill_install",
                    "description": "Install a skill to the workspace as a SKILL.md file.",
                    "parameters": {
                        "type": "object",
                        "properties": {"skillId": {"type": "string"}},
                        "required": ["skillId"],
                    },
                },
            ])

        # Always-available tools
        tools.append({
            "name": "memory_write_public",
            "description": "Write a public memory that all agents can retrieve.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "summary": {"type": "string"},
                },
                "required": ["content"],
            },
        })
        tools.append({
            "name": "memory_viewer",
            "description": "Get the URL for the memory viewer dashboard.",
            "parameters": {"type": "object", "properties": {}},
        })
        tools.append({
            "name": "memory_import_scan",
            "description": "Scan for OpenClaw native memories that can be imported.",
            "parameters": {"type": "object", "properties": {}},
        })
        tools.append({
            "name": "memory_import_start",
            "description": "Start importing scanned native memories with smart dedup.",
            "parameters": {
                "type": "object",
                "properties": {"batchSize": {"type": "number"}},
            },
        })

        # ========== Enterprise tools ==========
        if self._enterprise_enabled:
            tools.extend(self._get_preference_tool_schemas())
            tools.extend(self._get_alert_tool_schemas())

        return tools

    def _get_preference_tool_schemas(self) -> List[Dict[str, Any]]:
        """Tool schemas for Direction C — personal preferences & habits."""
        return [
            {
                "name": "preference_get",
                "description": (
                    "Get a specific user preference by category and key. "
                    "Returns the stored value, confidence score, and evidence count."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Preference category: 'work_pattern', 'tool_preference', 'schedule', 'style'",
                            "enum": ["work_pattern", "tool_preference", "schedule", "style"],
                        },
                        "key": {
                            "type": "string",
                            "description": "Preference key (e.g. 'editor', 'code_review_time', 'language')",
                        },
                    },
                    "required": ["category", "key"],
                },
            },
            {
                "name": "preference_set",
                "description": (
                    "Explicitly set or update a user preference. "
                    "Explicit preferences have higher confidence than inferred ones."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Preference category",
                            "enum": ["work_pattern", "tool_preference", "schedule", "style"],
                        },
                        "key": {
                            "type": "string",
                            "description": "Preference key",
                        },
                        "value": {
                            "type": "string",
                            "description": "Preference value",
                        },
                    },
                    "required": ["category", "key", "value"],
                },
            },
            {
                "name": "preference_list",
                "description": (
                    "List all preferences for a user, optionally filtered by category. "
                    "Returns preferences sorted by confidence (highest first)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Optional category filter",
                            "enum": ["work_pattern", "tool_preference", "schedule", "style"],
                        },
                        "minConfidence": {
                            "type": "number",
                            "description": "Minimum confidence threshold. Default 0.3.",
                        },
                    },
                },
            },
            {
                "name": "preference_delete",
                "description": "Delete a specific user preference.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Preference category",
                            "enum": ["work_pattern", "tool_preference", "schedule", "style"],
                        },
                        "key": {
                            "type": "string",
                            "description": "Preference key",
                        },
                    },
                    "required": ["category", "key"],
                },
            },
            {
                "name": "habit_patterns",
                "description": (
                    "Retrieve inferred behavior patterns for the current user. "
                    "Patterns include time-of-day habits, tool usage frequency, "
                    "topic clusters, and workflow sequences."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "patternType": {
                            "type": "string",
                            "description": "Optional type filter",
                            "enum": ["time_pattern", "tool_frequency", "topic_cluster", "workflow"],
                        },
                        "maxResults": {
                            "type": "number",
                            "description": "Maximum patterns to return. Default 20.",
                        },
                    },
                },
            },
        ]

    def _get_alert_tool_schemas(self) -> List[Dict[str, Any]]:
        """Tool schemas for Direction D — knowledge health & alerts."""
        return [
            {
                "name": "knowledge_health",
                "description": (
                    "Get freshness and health status for a specific memory chunk "
                    "or overall knowledge base. Shows last access time, access count, "
                    "and freshness status (fresh / aging / stale / forgotten)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chunkId": {
                            "type": "string",
                            "description": "Optional specific chunk to check",
                        },
                        "teamId": {
                            "type": "string",
                            "description": "Optional team filter",
                        },
                        "statusFilter": {
                            "type": "string",
                            "description": "Filter by freshness status",
                            "enum": ["fresh", "aging", "stale", "forgotten"],
                        },
                        "maxResults": {
                            "type": "number",
                            "description": "Max results. Default 20.",
                        },
                    },
                },
            },
            {
                "name": "knowledge_gaps",
                "description": (
                    "Detect knowledge gaps in the team. Identifies domains where "
                    "few team members have relevant knowledge, single-point-of-failure "
                    "knowledge, and areas with no coverage at all."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "teamId": {
                            "type": "string",
                            "description": "Team to analyse (required)",
                        },
                        "domain": {
                            "type": "string",
                            "description": "Optional domain filter",
                        },
                        "minSeverity": {
                            "type": "string",
                            "description": "Minimum severity to report",
                            "enum": ["low", "medium", "high", "critical"],
                        },
                    },
                },
            },
            {
                "name": "knowledge_alerts",
                "description": (
                    "Get current knowledge health alerts — stale memories, "
                    "single-point-of-failure knowledge, and recently degraded entries. "
                    "Use to proactively maintain team knowledge quality."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "teamId": {
                            "type": "string",
                            "description": "Optional team filter",
                        },
                        "alertType": {
                            "type": "string",
                            "description": "Filter by alert type",
                            "enum": ["stale", "forgotten", "single_point", "degraded", "all"],
                            "default": "all",
                        },
                        "maxResults": {
                            "type": "number",
                            "description": "Max alerts. Default 20.",
                        },
                    },
                },
            },
            {
                "name": "team_knowledge_map",
                "description": (
                    "Get or refresh the team knowledge map — a breakdown of knowledge "
                    "domains, coverage per member, and identified gaps. "
                    "Useful for onboarding, auditing, and sprint planning."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "teamId": {
                            "type": "string",
                            "description": "Team ID (required)",
                        },
                        "refresh": {
                            "type": "boolean",
                            "description": "Force a fresh analysis. Default false.",
                            "default": False,
                        },
                    },
                    "required": ["teamId"],
                },
            },
        ]

    # ------------------------------------------------------------------
    # Tool dispatch
    # ------------------------------------------------------------------

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """Handle tool calls from the agent."""
        if not self._initialized:
            return _json_dumps({"error": "Memory provider not initialized"})

        agent_id = _extract_agent_id(self._session_id)

        try:
            # ---- Original memos tools ----
            if name == "memory_search":
                result = self._handle_memory_search(args)
            elif name == "memory_get":
                result = self._handle_memory_get(args)
            elif name == "memory_timeline":
                result = self._handle_memory_timeline(args)
            elif name == "memory_share":
                result = self._handle_memory_share(args)
            elif name == "memory_unshare":
                result = self._handle_memory_unshare(args)
            elif name == "memory_list_shared":
                result = self._handle_memory_list_shared(args)
            elif name == "skill_search" and self._skill_generation_enabled:
                result = self._handle_skill_search(args)
            elif name == "skill_get" and self._skill_generation_enabled:
                result = self._handle_skill_get(args)
            elif name == "task_summary" and self._skill_generation_enabled:
                result = self._handle_task_summary(args)
            elif name == "task_edit" and self._skill_generation_enabled:
                result = self._handle_task_edit(args)
            elif name == "task_delete" and self._skill_generation_enabled:
                result = self._handle_task_delete(args)
            elif name == "skill_edit" and self._skill_generation_enabled:
                result = self._handle_skill_edit(args)
            elif name == "skill_delete" and self._skill_generation_enabled:
                result = self._handle_skill_delete(args)
            elif name == "skill_retry" and self._skill_generation_enabled:
                result = self._handle_skill_retry(args)
            elif name == "skill_publish" and self._skill_generation_enabled:
                result = self._handle_skill_publish(args)
            elif name == "skill_unpublish" and self._skill_generation_enabled:
                result = self._handle_skill_unpublish(args)
            elif name == "skill_install" and self._skill_generation_enabled:
                result = self._handle_skill_install(args)
            elif name == "memory_write_public":
                result = self._handle_memory_write_public(args)
            elif name == "memory_viewer":
                result = self._handle_memory_viewer(args)
            elif name == "memory_import_scan":
                result = self._handle_memory_import_scan(args)
            elif name == "memory_import_start":
                result = self._handle_memory_import_start(args)
            # ---- Enterprise tools ----
            elif name == "preference_get" and self._enterprise_enabled:
                result = self._handle_preference_get(args)
            elif name == "preference_set" and self._enterprise_enabled:
                result = self._handle_preference_set(args)
            elif name == "preference_list" and self._enterprise_enabled:
                result = self._handle_preference_list(args)
            elif name == "preference_delete" and self._enterprise_enabled:
                result = self._handle_preference_delete(args)
            elif name == "habit_patterns" and self._enterprise_enabled:
                result = self._handle_habit_patterns(args)
            elif name == "knowledge_health" and self._enterprise_enabled:
                result = self._handle_knowledge_health(args)
            elif name == "knowledge_gaps" and self._enterprise_enabled:
                result = self._handle_knowledge_gaps(args)
            elif name == "knowledge_alerts" and self._enterprise_enabled:
                result = self._handle_knowledge_alerts(args)
            elif name == "team_knowledge_map" and self._enterprise_enabled:
                result = self._handle_team_knowledge_map(args)
            else:
                result = _json_dumps({"error": f"Unknown tool: {name}"})
        except Exception as e:
            logger.exception(f"enterprise-memory: tool call failed: {name}")
            result = _json_dumps({"error": str(e)})

        # Log tool call
        try:
            self._store.log_tool_call(name, _json_dumps(args)[:500], str(result)[:500], agent_id)
        except Exception:
            pass
        return result

    # ==================================================================
    # Original memos tool handlers (delegated to store / recall engine)
    # ==================================================================

    def _handle_memory_search(self, args: Dict[str, Any]) -> str:
        import json

        query = args.get("query", "")
        scope = args.get("scope", "private")
        max_results = args.get("maxResults", 10)
        min_score = args.get("minScore", 0.45)
        role = args.get("role")

        if not query:
            return json.dumps({"error": "Query is required"})
        if not self._recall_engine:
            return json.dumps({"error": "Recall engine not initialized"})

        agent_id = _extract_agent_id(self._session_id)

        results = self._recall_engine.search(
            query=query,
            max_results=int(max_results),
            min_score=float(min_score),
            role=role,
            scope=scope,
            agent_id=agent_id,
        )

        hits = []
        for hit in results.get("hits", []):
            hits.append({
                "chunkId": hit.get("chunkId", ""),
                "score": hit.get("score", 0),
                "summary": hit.get("summary", ""),
                "role": hit.get("role", ""),
                "original_excerpt": hit.get("original_excerpt", ""),
                "visibility": hit.get("visibility", "private"),
                "owner": hit.get("owner", ""),
                "source": hit.get("source", {}),
            })

        return json.dumps({
            "hits": hits,
            "meta": {
                **results.get("meta", {}),
                "scope": scope,
                "algorithms": ["FTS5", "Vector", "Pattern", "RRF", "MMR", "Recency"],
            },
        })

    def _handle_memory_get(self, args: Dict[str, Any]) -> str:
        import json
        chunk_id = args.get("chunkId", "")
        max_chars = args.get("maxChars", 2000)

        if not chunk_id:
            return json.dumps({"error": "chunkId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        chunk = self._store.get_chunk(chunk_id)
        if not chunk:
            return json.dumps({"error": f"Chunk not found: {chunk_id}"})

        return json.dumps({
            "chunkId": chunk_id,
            "role": chunk.get("role", ""),
            "content": chunk.get("content", "")[:int(max_chars)],
            "sessionKey": chunk.get("sessionKey", ""),
        })

    def _handle_memory_timeline(self, args: Dict[str, Any]) -> str:
        import json
        chunk_id = args.get("chunkId", "")
        window = args.get("window", 2)

        if not chunk_id:
            return json.dumps({"error": "chunkId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        chunk = self._store.get_chunk(chunk_id)
        if not chunk:
            return json.dumps({"error": f"Chunk not found: {chunk_id}"})

        neighbors = self._store.get_neighbor_chunks(
            chunk.get("sessionKey", ""),
            chunk.get("turnId", ""),
            chunk.get("seq", 0),
            int(window),
        )

        entries = []
        for n in neighbors:
            rel = "current" if n.get("id") == chunk_id else (
                "before" if n.get("createdAt", 0) < chunk.get("createdAt", 0) else "after"
            )
            entries.append({
                "relation": rel,
                "role": n.get("role", ""),
                "excerpt": n.get("content", "")[:200],
            })

        return json.dumps({"chunkId": chunk_id, "entries": entries})

    def _handle_memory_list_shared(self, args: Dict[str, Any]) -> str:
        import json
        max_results = args.get("maxResults", 50)
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        agent_id = _extract_agent_id(self._session_id)
        chunks = self._store.get_shared_chunks(agent_id, int(max_results))

        items = []
        for chunk in chunks:
            items.append({
                "chunkId": chunk.get("id", ""),
                "content": chunk.get("content", "")[:200],
                "owner": chunk.get("owner", "unknown"),
                "sharedWith": chunk.get("sharedWith"),
                "createdAt": chunk.get("createdAt", 0),
            })

        return json.dumps({"items": items, "count": len(items)})

    def _handle_memory_share(self, args: Dict[str, Any]) -> str:
        import json
        chunk_id = args.get("chunkId", "")
        shared_with = args.get("sharedWith")

        if not chunk_id:
            return json.dumps({"error": "chunkId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        chunk = self._store.get_chunk(chunk_id)
        if not chunk:
            return json.dumps({"error": f"Chunk not found: {chunk_id}"})

        agent_id = _extract_agent_id(self._session_id)
        if chunk.get("owner") != agent_id:
            return json.dumps({"error": "You can only share your own memories"})

        success = self._store.share_chunk(chunk_id, shared_with)
        if success:
            scope_desc = "globally shared" if not shared_with else f"shared with {len(shared_with)} agents"
            return json.dumps({"success": True, "chunkId": chunk_id, "message": f"Memory {scope_desc}"})
        return json.dumps({"error": "Failed to share memory"})

    def _handle_memory_unshare(self, args: Dict[str, Any]) -> str:
        import json
        chunk_id = args.get("chunkId", "")

        if not chunk_id:
            return json.dumps({"error": "chunkId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        chunk = self._store.get_chunk(chunk_id)
        if not chunk:
            return json.dumps({"error": f"Chunk not found: {chunk_id}"})

        agent_id = _extract_agent_id(self._session_id)
        if chunk.get("owner") != agent_id:
            return json.dumps({"error": "You can only unshare your own memories"})

        success = self._store.make_chunk_private(chunk_id)
        if success:
            return json.dumps({"success": True, "chunkId": chunk_id, "message": "Memory is now private"})
        return json.dumps({"error": "Failed to unshare memory"})

    def _handle_task_summary(self, args: Dict[str, Any]) -> str:
        import json
        task_id = args.get("taskId", "")
        if not task_id:
            return json.dumps({"error": "taskId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})
        task = self._store.get_task(task_id)
        if not task:
            return json.dumps({"error": f"Task not found: {task_id}"})
        return json.dumps({
            "taskId": task_id,
            "title": task.get("title", ""),
            "status": task.get("status", ""),
            "summary": task.get("summary", ""),
        })

    def _handle_task_edit(self, args: Dict[str, Any]) -> str:
        import json
        task_id = args.get("taskId", "")
        if not task_id:
            return json.dumps({"error": "taskId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        updates = {}
        for key in ("title", "summary", "status"):
            if key in args:
                updates[key] = args[key]

        success = self._store.update_task_fields(task_id, updates)
        return json.dumps({"success": success, "taskId": task_id})

    def _handle_task_delete(self, args: Dict[str, Any]) -> str:
        import json
        task_id = args.get("taskId", "")
        if not task_id:
            return json.dumps({"error": "taskId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        success = self._store.delete_task(task_id)
        return json.dumps({"success": success, "taskId": task_id})

    def _handle_skill_search(self, args: Dict[str, Any]) -> str:
        import json
        query = args.get("query", "")
        max_results = args.get("maxResults", 10)
        scope = args.get("scope", "mix")

        if not query:
            return json.dumps({"error": "Query is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        agent_id = _extract_agent_id(self._session_id)
        skills = self._store.search_skills(query, limit=int(max_results), scope=scope, owner=agent_id)

        items = []
        for s in skills:
            items.append({
                "skillId": s.get("id", ""),
                "name": s.get("name", ""),
                "version": s.get("version", ""),
                "status": s.get("status", ""),
                "owner": s.get("owner", ""),
                "excerpt": s.get("content", "")[:200],
            })

        return json.dumps({"items": items, "count": len(items)})

    def _handle_skill_get(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        task_id = args.get("taskId", "")

        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        if skill_id:
            skill = self._store.get_skill(skill_id)
        elif task_id:
            skills = self._store.get_skills_by_task(task_id)
            skill = skills[0] if skills else None
        else:
            return json.dumps({"error": "skillId or taskId is required"})

        if not skill:
            return json.dumps({"error": "Skill not found"})
        return json.dumps(skill)

    def _handle_skill_edit(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        if not skill_id:
            return json.dumps({"error": "skillId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        updates = {}
        for key in ("name", "content"):
            if key in args:
                updates[key] = args[key]

        success = self._store.update_skill_fields(skill_id, updates)
        return json.dumps({"success": success, "skillId": skill_id})

    def _handle_skill_delete(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        if not skill_id:
            return json.dumps({"error": "skillId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        success = self._store.delete_skill(skill_id)
        return json.dumps({"success": success, "skillId": skill_id})

    def _handle_skill_retry(self, args: Dict[str, Any]) -> str:
        import json
        return json.dumps({"error": "skill_retry not implemented in enterprise plugin"})

    def _handle_skill_publish(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        if not skill_id:
            return json.dumps({"error": "skillId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        success = self._store.update_skill_fields(skill_id, {"owner": "public"})
        return json.dumps({"success": success, "skillId": skill_id, "message": "Skill published"})

    def _handle_skill_unpublish(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        agent_id = _extract_agent_id(self._session_id)
        if not skill_id:
            return json.dumps({"error": "skillId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        success = self._store.update_skill_fields(skill_id, {"owner": agent_id})
        return json.dumps({"success": success, "skillId": skill_id, "message": "Skill made private"})

    def _handle_skill_install(self, args: Dict[str, Any]) -> str:
        import json
        skill_id = args.get("skillId", "")
        if not skill_id:
            return json.dumps({"error": "skillId is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        skill = self._store.get_skill(skill_id)
        if not skill:
            return json.dumps({"error": f"Skill not found: {skill_id}"})

        try:
            if self._skill_installer:
                self._skill_installer.install(skill)
                return json.dumps({
                    "success": True,
                    "skillId": skill_id,
                    "message": f"Skill '{skill.get('name', '')}' installed",
                })
        except Exception as e:
            return json.dumps({"error": f"Install failed: {e}"})

        return json.dumps({"error": "Installer not available"})

    def _handle_memory_write_public(self, args: Dict[str, Any]) -> str:
        import json
        content = args.get("content", "")
        summary = args.get("summary", "")
        if not content:
            return json.dumps({"error": "content is required"})
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        agent_id = _extract_agent_id(self._session_id)
        chunk_id = self._store.insert_chunk({
            "content": content,
            "summary": summary or content[:100],
            "role": "assistant",
            "owner": agent_id,
            "visibility": "shared",
            "sessionKey": f"{agent_id}/public",
        })
        return json.dumps({"success": True, "chunkId": chunk_id, "visibility": "shared"})

    def _handle_memory_viewer(self, args: Dict[str, Any]) -> str:
        import json
        hermes_home = str(self._hermes_home) if self._hermes_home else "~/.hermes"
        return json.dumps({
            "url": f"file://{hermes_home}/memos/viewer/index.html",
            "path": f"{hermes_home}/memos/viewer/index.html",
        })

    def _handle_memory_import_scan(self, args: Dict[str, Any]) -> str:
        import json
        if not self._store:
            return json.dumps({"error": "Store not initialized"})

        hermes_home = str(self._hermes_home) if self._hermes_home else "~/.hermes"
        results = self._store.scan_native_memories(hermes_home)
        return json.dumps(results)

    def _handle_memory_import_start(self, args: Dict[str, Any]) -> str:
        import json
        return json.dumps({"error": "Import not implemented in enterprise plugin — use memos-local for importing"})

    # ==================================================================
    # Enterprise tool handlers — Direction C (Preferences)
    # ==================================================================

    def _handle_preference_get(self, args: Dict[str, Any]) -> str:
        import json
        category = args.get("category", "")
        key = args.get("key", "")

        if not category or not key:
            return json.dumps({"error": "category and key are required"})

        agent_id = _extract_agent_id(self._session_id)
        pref = self._store.get_user_preference(agent_id, category, key)

        if pref:
            return json.dumps(pref)
        return json.dumps({"error": "Preference not found"})

    def _handle_preference_set(self, args: Dict[str, Any]) -> str:
        import json
        category = args.get("category", "")
        key = args.get("key", "")
        value = args.get("value", "")

        if not all([category, key, value]):
            return json.dumps({"error": "category, key, and value are required"})

        agent_id = _extract_agent_id(self._session_id)
        pref_id = self._store.upsert_user_preference(
            owner=agent_id,
            category=category,
            key=key,
            value=value,
            confidence=0.95,  # explicit = high confidence
            source="user_explicit",
        )

        return json.dumps({
            "success": True,
            "id": pref_id,
            "category": category,
            "key": key,
            "value": value,
            "message": "Preference saved",
        })

    def _handle_preference_list(self, args: Dict[str, Any]) -> str:
        import json
        category = args.get("category")
        min_confidence = args.get("minConfidence", 0.3)

        agent_id = _extract_agent_id(self._session_id)
        prefs = self._store.list_user_preferences(
            owner=agent_id,
            category=category,
            min_confidence=float(min_confidence),
        )

        return json.dumps({"preferences": prefs, "count": len(prefs)})

    def _handle_preference_delete(self, args: Dict[str, Any]) -> str:
        import json
        category = args.get("category", "")
        key = args.get("key", "")

        if not category or not key:
            return json.dumps({"error": "category and key are required"})

        agent_id = _extract_agent_id(self._session_id)
        success = self._store.delete_user_preference(agent_id, category, key)
        return json.dumps({"success": success, "category": category, "key": key})

    def _handle_habit_patterns(self, args: Dict[str, Any]) -> str:
        import json
        pattern_type = args.get("patternType")
        max_results = args.get("maxResults", 20)

        agent_id = _extract_agent_id(self._session_id)

        # Trigger a fresh inference if the module is available
        if self._habit_inference:
            try:
                self._habit_inference.infer_patterns(agent_id)
            except Exception as e:
                logger.warning(f"enterprise-memory: habit inference failed: {e}")

        patterns = self._store.get_behavior_patterns(
            owner=agent_id,
            pattern_type=pattern_type,
            limit=int(max_results),
        )

        return json.dumps({"patterns": patterns, "count": len(patterns)})

    # ==================================================================
    # Enterprise tool handlers — Direction D (Alerts)
    # ==================================================================

    def _handle_knowledge_health(self, args: Dict[str, Any]) -> str:
        import json
        chunk_id = args.get("chunkId")
        team_id = args.get("teamId")
        status_filter = args.get("statusFilter")
        max_results = args.get("maxResults", 20)

        # Run freshness check
        if self._freshness_monitor:
            try:
                self._freshness_monitor.check_freshness(team_id=team_id)
            except Exception as e:
                logger.warning(f"enterprise-memory: freshness check failed: {e}")

        if chunk_id:
            health = self._store.get_knowledge_health(chunk_id)
            if health:
                return json.dumps(health)
            return json.dumps({"error": f"No health record for chunk: {chunk_id}"})

        records = self._store.list_knowledge_health(
            team_id=team_id,
            status_filter=status_filter,
            limit=int(max_results),
        )

        return json.dumps({"health": records, "count": len(records)})

    def _handle_knowledge_gaps(self, args: Dict[str, Any]) -> str:
        import json
        team_id = args.get("teamId", "")
        domain = args.get("domain")
        min_severity = args.get("minSeverity", "low")

        if not team_id:
            return json.dumps({"error": "teamId is required"})

        # Run gap detection
        if self._gap_detector:
            try:
                self._gap_detector.detect_gaps(team_id, domain_filter=domain)
            except Exception as e:
                logger.warning(f"enterprise-memory: gap detection failed: {e}")

        gaps = self._store.list_knowledge_gaps(
            team_id=team_id,
            domain=domain,
            min_severity=min_severity,
        )

        return json.dumps({"gaps": gaps, "count": len(gaps)})

    def _handle_knowledge_alerts(self, args: Dict[str, Any]) -> str:
        import json
        team_id = args.get("teamId")
        alert_type = args.get("alertType", "all")
        max_results = args.get("maxResults", 20)

        # Run freshness check to populate alerts
        if self._freshness_monitor:
            try:
                self._freshness_monitor.check_freshness(team_id=team_id)
            except Exception as e:
                logger.warning(f"enterprise-memory: freshness check failed: {e}")

        alerts = self._store.get_knowledge_alerts(
            team_id=team_id,
            alert_type=alert_type,
            limit=int(max_results),
        )

        return json.dumps({"alerts": alerts, "count": len(alerts)})

    def _handle_team_knowledge_map(self, args: Dict[str, Any]) -> str:
        import json
        team_id = args.get("teamId", "")
        refresh = args.get("refresh", False)

        if not team_id:
            return json.dumps({"error": "teamId is required"})

        # Run gap detection to refresh the map
        if refresh and self._gap_detector:
            try:
                self._gap_detector.build_team_knowledge_map(team_id)
            except Exception as e:
                logger.warning(f"enterprise-memory: knowledge map build failed: {e}")

        team_map = self._store.get_team_knowledge_map(team_id)
        if team_map:
            return json.dumps(team_map)

        return json.dumps({
            "teamId": team_id,
            "domains": [],
            "message": "No knowledge map available. Pass refresh=true to build one.",
        })


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def register():
    """Register this plugin with the Hermes Agent plugin system."""
    return EnterpriseMemoryProvider()
