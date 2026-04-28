"""
MemScope — Enterprise Long-term Collaboration Memory System
Main plugin provider integrating memos core + A/B/C/D directions.
"""
import json
import logging
import os
import time
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Core modules from memos
try:
    from .core.store import SqliteStore
    from .core.embedder import RealEmbedder
    from .recall.engine import RecallEngine
    from .ingest.chunker import Chunker
    from .ingest.summarizer import Summarizer
    from .context_engine.index import ContextEngine
except ImportError:
    # Fallback for direct execution
    import sys
    _dir = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, _dir)
    from core.store import SqliteStore
    from core.embedder import RealEmbedder
    from recall.engine import RecallEngine
    from ingest.chunker import Chunker
    from ingest.summarizer import Summarizer
    from context_engine.index import ContextEngine

# Direction modules
try:
    from .direction_a.command_tracker import CommandTracker
    from .direction_a.recommender import CommandRecommender
    from .direction_b.decision_extractor import DecisionExtractor
    from .direction_b.decision_card import DecisionCardManager
    from .direction_c.preference_extractor import PreferenceExtractor
    from .direction_c.preference_manager import PreferenceManager
    from .direction_c.habit_inference import HabitInference
    from .direction_d.ebbinghaus import EbbinghausModel
    from .direction_d.freshness_monitor import FreshnessMonitor
    from .direction_d.gap_detector import GapDetector
except ImportError:
    import sys
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    from direction_a.command_tracker import CommandTracker
    from direction_a.recommender import CommandRecommender
    from direction_b.decision_extractor import DecisionExtractor
    from direction_b.decision_card import DecisionCardManager
    from direction_c.preference_extractor import PreferenceExtractor
    from direction_c.preference_manager import PreferenceManager
    from direction_c.habit_inference import HabitInference
    from direction_d.ebbinghaus import EbbinghausModel
    from direction_d.freshness_monitor import FreshnessMonitor
    from direction_d.gap_detector import GapDetector


class MemScopeProvider:
    """
    MemScope Memory Provider for Hermes Agent.
    
    Integrates:
    - Core memos memory (storage, recall, ingest, context)
    - Direction A: CLI command & workflow memory
    - Direction B: Feishu decision & context memory
    - Direction C: Personal habit & preference memory
    - Direction D: Team knowledge health & forgetting alerts
    """

    def __init__(self):
        self.store: Optional[SqliteStore] = None
        self.embedder: Optional[RealEmbedder] = None
        self.recall_engine: Optional[RecallEngine] = None
        self.context_engine: Optional[ContextEngine] = None
        self.chunker: Optional[Chunker] = None
        self.summarizer: Optional[Summarizer] = None

        # Direction modules
        self.command_tracker: Optional[CommandTracker] = None
        self.command_recommender: Optional[CommandRecommender] = None
        self.decision_extractor: Optional[DecisionExtractor] = None
        self.decision_card_manager: Optional[DecisionCardManager] = None
        self.preference_extractor: Optional[PreferenceExtractor] = None
        self.preference_manager: Optional[PreferenceManager] = None
        self.habit_inference: Optional[HabitInference] = None
        self.freshness_monitor: Optional[FreshnessMonitor] = None
        self.gap_detector: Optional[GapDetector] = None
        self.ebbinghaus: Optional[EbbinghausModel] = None

        self._initialized = False
        self._session_id = ''
        self._owner = 'default'

    def name(self) -> str:
        return 'memscope'

    def is_available(self) -> bool:
        return True

    def initialize(self, session_id: str, **kwargs) -> None:
        """Initialize all MemScope subsystems."""
        if self._initialized:
            return

        try:
            hermes_home = kwargs.get('hermes_home', os.environ.get('HERMES_HOME', os.path.expanduser('~')))
            db_path = os.path.join(hermes_home, 'memos', 'memscope.db')
            os.makedirs(os.path.dirname(db_path), exist_ok=True)

            # Core
            self.store = SqliteStore(db_path)
            self.embedder = RealEmbedder()
            self.recall_engine = RecallEngine(
                store=self.store,
                embedder=self.embedder,
                config={
                    'rrf_k': 60,
                    'mmr_lambda': 0.7,
                    'recency_half_life_days': 14,
                },
            )
            self.context_engine = ContextEngine(recall_engine=self.recall_engine)
            self.chunker = Chunker()
            self.summarizer = None  # Requires llm_caller, optional

            # Direction A
            self.command_tracker = CommandTracker(self.store)
            self.command_recommender = CommandRecommender(self.store)

            # Direction B
            self.decision_extractor = DecisionExtractor(self.store)
            self.decision_card_manager = DecisionCardManager(self.store)

            # Direction C
            self.preference_extractor = PreferenceExtractor(self.store)
            self.preference_manager = PreferenceManager(self.store)
            self.habit_inference = HabitInference(self.store)

            # Direction D
            self.ebbinghaus = EbbinghausModel()
            self.freshness_monitor = FreshnessMonitor(self.store)
            self.gap_detector = GapDetector(self.store)

            self._session_id = session_id
            self._initialized = True
            logger.info(f"MemScope initialized for session {session_id}")

        except Exception as e:
            logger.error(f"MemScope initialization failed: {e}")
            raise

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return all tool schemas for Hermes Agent."""
        return [
            # Core memory tools
            {
                'name': 'memory_search',
                'description': 'Search memories by semantic similarity and keywords',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string', 'description': 'Search query'},
                        'limit': {'type': 'integer', 'default': 10},
                        'scope': {'type': 'string', 'enum': ['private', 'shared', 'all'], 'default': 'private'},
                    },
                    'required': ['query'],
                },
            },
            # Direction A tools
            {
                'name': 'command_log',
                'description': 'Log a CLI command for pattern tracking',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'command': {'type': 'string'},
                        'args': {'type': 'string'},
                        'project_path': {'type': 'string'},
                        'exit_code': {'type': 'integer'},
                        'working_dir': {'type': 'string'},
                    },
                    'required': ['command'],
                },
            },
            {
                'name': 'command_recommend',
                'description': 'Get command recommendations based on context',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'prefix': {'type': 'string'},
                        'project_path': {'type': 'string'},
                        'limit': {'type': 'integer', 'default': 5},
                    },
                },
            },
            # Direction B tools
            {
                'name': 'decision_record',
                'description': 'Record a project decision',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'title': {'type': 'string'},
                        'decision': {'type': 'string'},
                        'rationale': {'type': 'string'},
                        'project_id': {'type': 'string'},
                        'alternatives': {'type': 'array', 'items': {'type': 'string'}},
                        'participants': {'type': 'array', 'items': {'type': 'string'}},
                    },
                    'required': ['title', 'decision'],
                },
            },
            {
                'name': 'decision_search',
                'description': 'Search project decisions',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'query': {'type': 'string'},
                        'project_id': {'type': 'string'},
                        'limit': {'type': 'integer', 'default': 10},
                    },
                    'required': ['query'],
                },
            },
            {
                'name': 'decision_cards',
                'description': 'Get related decision cards for current context',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'message': {'type': 'string'},
                        'project_id': {'type': 'string'},
                    },
                    'required': ['message'],
                },
            },
            # Direction C tools
            {
                'name': 'preference_set',
                'description': 'Set a user preference',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'category': {'type': 'string', 'enum': ['tool', 'schedule', 'style', 'workflow', 'communication']},
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                        'source': {'type': 'string', 'enum': ['explicit', 'inferred', 'observed'], 'default': 'explicit'},
                    },
                    'required': ['category', 'key', 'value'],
                },
            },
            {
                'name': 'preference_get',
                'description': 'Get a specific user preference',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'category': {'type': 'string'},
                        'key': {'type': 'string'},
                    },
                    'required': ['category', 'key'],
                },
            },
            {
                'name': 'preference_list',
                'description': 'List all user preferences',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'category': {'type': 'string'},
                    },
                },
            },
            {
                'name': 'habit_patterns',
                'description': 'Get inferred habit patterns',
                'parameters': {
                    'type': 'object',
                    'properties': {},
                },
            },
            # Direction D tools
            {
                'name': 'knowledge_health',
                'description': 'Check team knowledge health status',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'team_id': {'type': 'string'},
                    },
                    'required': ['team_id'],
                },
            },
            {
                'name': 'knowledge_gaps',
                'description': 'Detect team knowledge gaps',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'team_id': {'type': 'string'},
                        'domain': {'type': 'string'},
                    },
                    'required': ['team_id'],
                },
            },
            {
                'name': 'knowledge_alerts',
                'description': 'Get knowledge review alerts',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'team_id': {'type': 'string'},
                    },
                    'required': ['team_id'],
                },
            },
            {
                'name': 'team_knowledge_map',
                'description': 'Get team knowledge coverage map',
                'parameters': {
                    'type': 'object',
                    'properties': {
                        'team_id': {'type': 'string'},
                    },
                    'required': ['team_id'],
                },
            },
        ]

    def handle_tool_call(self, name: str, args: Dict[str, Any]) -> str:
        """Route tool calls to appropriate handlers."""
        if not self._initialized:
            return json.dumps({'error': 'MemScope not initialized'})

        try:
            handler = {
                'memory_search': self._handle_memory_search,
                'command_log': self._handle_command_log,
                'command_recommend': self._handle_command_recommend,
                'decision_record': self._handle_decision_record,
                'decision_search': self._handle_decision_search,
                'decision_cards': self._handle_decision_cards,
                'preference_set': self._handle_preference_set,
                'preference_get': self._handle_preference_get,
                'preference_list': self._handle_preference_list,
                'habit_patterns': self._handle_habit_patterns,
                'knowledge_health': self._handle_knowledge_health,
                'knowledge_gaps': self._handle_knowledge_gaps,
                'knowledge_alerts': self._handle_knowledge_alerts,
                'team_knowledge_map': self._handle_team_knowledge_map,
            }.get(name)

            if handler:
                return handler(args)
            else:
                return json.dumps({'error': f'Unknown tool: {name}'})

        except Exception as e:
            logger.error(f"Tool call {name} failed: {e}")
            return json.dumps({'error': str(e)})

    # ===== Core Memory =====

    def _handle_memory_search(self, args: Dict[str, Any]) -> str:
        query = args.get('query', '')
        limit = args.get('limit', 10)
        scope = args.get('scope', 'private')
        results = self.recall_engine.search(
            query, max_results=limit, scope=scope, agent_id=self._owner
        )
        return json.dumps({'results': results}, ensure_ascii=False)

    # ===== Direction A =====

    def _handle_command_log(self, args: Dict[str, Any]) -> str:
        cmd_id = self.command_tracker.log_command(
            owner=self._owner,
            command=args.get('command', ''),
            args=args.get('args'),
            project_path=args.get('project_path'),
            exit_code=args.get('exit_code'),
            working_dir=args.get('working_dir'),
        )
        return json.dumps({'id': cmd_id, 'status': 'logged'})

    def _handle_command_recommend(self, args: Dict[str, Any]) -> str:
        recs = self.command_recommender.context_recommend(
            owner=self._owner,
            current_dir=args.get('project_path'),
            limit=args.get('limit', 5),
        )
        return json.dumps({'recommendations': recs}, ensure_ascii=False)

    # ===== Direction B =====

    def _handle_decision_record(self, args: Dict[str, Any]) -> str:
        did = self.decision_card_manager.record_decision(
            title=args.get('title', ''),
            decision=args.get('decision', ''),
            rationale=args.get('rationale', ''),
            project_id=args.get('project_id', ''),
            alternatives=args.get('alternatives', []),
            participants=args.get('participants', []),
            owner=self._owner,
        )
        return json.dumps({'id': did, 'status': 'recorded'})

    def _handle_decision_search(self, args: Dict[str, Any]) -> str:
        results = self.decision_extractor.search_decisions(
            query=args.get('query', ''),
            owner=self._owner,
            project_id=args.get('project_id'),
            limit=args.get('limit', 10),
        )
        return json.dumps({'decisions': results}, ensure_ascii=False)

    def _handle_decision_cards(self, args: Dict[str, Any]) -> str:
        cards = self.decision_card_manager.check_and_push(
            current_message=args.get('message', ''),
            owner=self._owner,
            project_id=args.get('project_id'),
        )
        return json.dumps({'cards': cards}, ensure_ascii=False)

    # ===== Direction C =====

    def _handle_preference_set(self, args: Dict[str, Any]) -> str:
        result = self.preference_manager.set_preference(
            owner=self._owner,
            category=args.get('category', 'general'),
            key=args.get('key', ''),
            value=args.get('value', ''),
            source=args.get('source', 'explicit'),
        )
        return json.dumps({'preference': result}, ensure_ascii=False)

    def _handle_preference_get(self, args: Dict[str, Any]) -> str:
        pref = self.preference_manager.get_preference(
            owner=self._owner,
            category=args.get('category', ''),
            key=args.get('key', ''),
        )
        return json.dumps({'preference': pref}, ensure_ascii=False)

    def _handle_preference_list(self, args: Dict[str, Any]) -> str:
        prefs = self.preference_manager.list_preferences(
            owner=self._owner,
            category=args.get('category'),
        )
        return json.dumps({'preferences': prefs}, ensure_ascii=False)

    def _handle_habit_patterns(self, args: Dict[str, Any]) -> str:
        summary = self.habit_inference.get_habit_summary(self._owner)
        return json.dumps(summary, ensure_ascii=False)

    # ===== Direction D =====

    def _handle_knowledge_health(self, args: Dict[str, Any]) -> str:
        team_id = args.get('team_id', '')
        summary = self.freshness_monitor.get_health_summary(team_id)
        return json.dumps(summary, ensure_ascii=False)

    def _handle_knowledge_gaps(self, args: Dict[str, Any]) -> str:
        team_id = args.get('team_id', '')
        domain = args.get('domain')
        gaps = self.gap_detector.detect_gaps(team_id, domain)
        return json.dumps({'gaps': gaps}, ensure_ascii=False)

    def _handle_knowledge_alerts(self, args: Dict[str, Any]) -> str:
        team_id = args.get('team_id', '')
        due = self.freshness_monitor.get_due_reviews(team_id)
        return json.dumps({'alerts': due}, ensure_ascii=False)

    def _handle_team_knowledge_map(self, args: Dict[str, Any]) -> str:
        team_id = args.get('team_id', '')
        team_map = self.gap_detector.get_team_map(team_id)
        return json.dumps(team_map, ensure_ascii=False)

    # ===== Lifecycle Hooks =====

    def prefetch(self, query: str) -> Optional[str]:
        """Pre-fetch relevant memories before LLM call."""
        if not self._initialized or not query:
            return None
        try:
            # Search core memories
            hits = self.recall_engine.search(query, max_results=5, agent_id=self._owner)

            # Check for related decisions
            decision_cards = self.decision_card_manager.check_and_push(query, self._owner)

            # Get habit suggestions
            habit_suggestion = self.habit_inference.should_suggest(
                self._owner,
                {'query': query, 'time': time.time()}
            )

            # Build context
            parts = []
            if hits:
                parts.append(self.context_engine._build_memory_block(hits))
            if decision_cards:
                parts.append(self.decision_card_manager.format_cards_markdown(decision_cards))
            if habit_suggestion:
                parts.append(f"💡 习惯建议: {json.dumps(habit_suggestion, ensure_ascii=False)}")

            return '\n\n'.join(parts) if parts else None

        except Exception as e:
            logger.error(f"Prefetch failed: {e}")
            return None

    def sync_turn(self, user_content: str, assistant_content: str) -> None:
        """Process a conversation turn after LLM response."""
        if not self._initialized:
            return

        try:
            # Ingest conversation
            chunks = self.chunker.chunk_messages(
                [
                    {'role': 'user', 'content': user_content},
                    {'role': 'assistant', 'content': assistant_content},
                ],
                session_key=self._session_id,
            )

            for chunk in chunks:
                self.store.insert_chunk({
                    'content': chunk.get('content', ''),
                    'summary': chunk.get('summary', ''),
                    'owner': self._owner,
                    'session_key': self._session_id,
                    'type': 'conversation',
                })

            # Extract preferences from conversation
            prefs = self.preference_extractor.extract_from_conversation(
                user_content, assistant_content, self._owner
            )
            for pref in prefs:
                self.preference_manager.set_preference(
                    owner=self._owner,
                    category=pref.get('category', 'general'),
                    key=pref.get('key', ''),
                    value=pref.get('value', ''),
                    source='extracted',
                    confidence=pref.get('confidence', 0.5),
                )

            # Extract decisions from conversation
            decisions = self.decision_extractor.extract_from_message(
                user_content, sender='user'
            )
            if decisions:
                self.decision_extractor.save_decisions(decisions, self._owner)

        except Exception as e:
            logger.error(f"Sync turn failed: {e}")

    def on_session_end(self, messages: List[Any] = None) -> None:
        """Session end hook - run maintenance tasks."""
        if not self._initialized:
            return

        try:
            # Decay preferences
            self.preference_manager.decay_all(self._owner)

            # Update knowledge freshness
            self.freshness_monitor.update_all_freshness()

        except Exception as e:
            logger.error(f"Session end hook failed: {e}")

    def shutdown(self) -> None:
        """Clean shutdown."""
        if self.store:
            self.store.close()
        self._initialized = False


def register(ctx) -> None:
    """Register MemScope with Hermes Agent."""
    try:
        ctx.register_memory_provider(MemScopeProvider())
    except Exception as e:
        logger.error(f"MemScope registration failed: {e}")
