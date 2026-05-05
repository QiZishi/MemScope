"""Feishu Memory Pipeline — processes Feishu chat messages into MemScope memories.

Integrates:
- Decision extraction from chat messages
- Preference inference from conversations
- Knowledge health monitoring
- Memory storage via SqliteStore
"""
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class FeishuMemoryPipeline:
    """Process Feishu messages into structured memories.

    Takes raw Feishu chat messages and routes them through:
    1. Decision extraction (Direction B)
    2. Preference inference (Direction C)
    3. Knowledge registration (Direction D)
    4. Memory storage
    """

    def __init__(self, store: Any, owner: str = "feishu"):
        self.store = store
        self.owner = owner
        self._extractors = {}

    def _get_decision_extractor(self):
        if "decision" not in self._extractors:
            try:
                from decision_memory.decision_extractor import DecisionExtractor
                self._extractors["decision"] = DecisionExtractor(self.store)
            except ImportError:
                logger.warning("DecisionExtractor not available")
                self._extractors["decision"] = None
        return self._extractors["decision"]

    def _get_preference_extractor(self):
        if "preference" not in self._extractors:
            try:
                from preference_memory.preference_extractor import PreferenceExtractor
                self._extractors["preference"] = PreferenceExtractor(self.store)
            except ImportError:
                logger.warning("PreferenceExtractor not available")
                self._extractors["preference"] = None
        return self._extractors["preference"]

    def _get_preference_manager(self):
        if "pref_manager" not in self._extractors:
            try:
                from preference_memory.preference_manager import PreferenceManager
                self._extractors["pref_manager"] = PreferenceManager(self.store)
            except ImportError:
                logger.warning("PreferenceManager not available")
                self._extractors["pref_manager"] = None
        return self._extractors["pref_manager"]

    def process_message(
        self,
        content: str,
        sender: str,
        chat_id: str,
        message_id: Optional[str] = None,
        timestamp: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Process a single Feishu chat message.

        Returns:
            Dict with keys: decisions, preferences, stored_chunk_id
        """
        ts = timestamp or int(time.time() * 1000)
        result = {"decisions": [], "preferences": [], "chunk_id": None}

        # Store the raw message as a memory chunk
        chunk_id = self.store.insert_chunk({
            "sessionKey": f"feishu-{chat_id}",
            "turnId": str(ts),
            "seq": 0,
            "role": "user",
            "content": content,
            "owner": self.owner,
            "createdAt": ts,
            "updatedAt": ts,
        })
        result["chunk_id"] = chunk_id

        # Direction B: Decision extraction
        extractor = self._get_decision_extractor()
        if extractor:
            try:
                decisions = extractor.extract_from_message(content, sender)
                if decisions:
                    extractor.save_decisions(decisions, owner=self.owner)
                    result["decisions"] = decisions
            except Exception as e:
                logger.warning(f"Decision extraction failed: {e}")

        # Direction C: Preference inference
        pref_extractor = self._get_preference_extractor()
        pref_manager = self._get_preference_manager()
        if pref_extractor and pref_manager:
            try:
                prefs = pref_extractor.extract_from_conversation(content, "", self.owner)
                for pref in prefs:
                    pref_manager.set_preference(
                        owner=pref.get("owner", self.owner),
                        category=pref.get("category", "general"),
                        key=pref.get("key", ""),
                        value=pref.get("value", ""),
                        source="feishu",
                        confidence=pref.get("confidence", 0.5),
                    )
                result["preferences"] = prefs
            except Exception as e:
                logger.warning(f"Preference extraction failed: {e}")

        return result

    def process_chat_history(
        self,
        messages: List[Dict[str, Any]],
        chat_id: str,
    ) -> Dict[str, Any]:
        """Process a batch of Feishu chat messages.

        Args:
            messages: List of Feishu message dicts with fields:
                - content: str
                - sender: str (sender name or id)
                - message_id: Optional[str]
                - timestamp: Optional[int]
            chat_id: The Feishu chat ID
        """
        results = {"total": len(messages), "decisions": 0, "preferences": 0, "errors": 0}
        for msg in messages:
            try:
                r = self.process_message(
                    content=msg.get("content", ""),
                    sender=msg.get("sender", "unknown"),
                    chat_id=chat_id,
                    message_id=msg.get("message_id"),
                    timestamp=msg.get("timestamp"),
                )
                results["decisions"] += len(r.get("decisions", []))
                results["preferences"] += len(r.get("preferences", []))
            except Exception as e:
                results["errors"] += 1
                logger.warning(f"Failed to process message: {e}")
        return results

    def get_decision_cards(
        self, keyword: str, chat_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Search for decision cards relevant to a keyword."""
        extractor = self._get_decision_extractor()
        if not extractor:
            return []
        try:
            return extractor.search_decisions(keyword, owner=self.owner)
        except Exception as e:
            logger.warning(f"Decision search failed: {e}")
            return []

    def get_user_preferences(self, user: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all preferences for a user."""
        manager = self._get_preference_manager()
        if not manager:
            return []
        try:
            return manager.list_preferences(user or self.owner)
        except Exception as e:
            logger.warning(f"Preference list failed: {e}")
            return []
