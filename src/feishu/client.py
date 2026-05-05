"""Feishu Open API Client — real API calls for message send/receive and card push."""
import json
import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    requests = None  # Graceful degradation if requests not installed


class FeishuClient:
    """Feishu (Lark) Open API client for tenant-level operations.

    Uses app_id + app_secret to obtain tenant_access_token.
    Supports: send messages, send interactive cards, list chat messages.
    """

    BASE_URL = "https://open.feishu.cn/open-apis"

    def __init__(self, app_id: str, app_secret: str):
        if not requests:
            raise ImportError("requests library required: pip install requests")
        self.app_id = app_id
        self.app_secret = app_secret
        self._token: Optional[str] = None
        self._token_expires: float = 0

    def _get_tenant_token(self) -> str:
        """Obtain or refresh tenant_access_token."""
        if self._token and time.time() < self._token_expires:
            return self._token
        resp = requests.post(
            f"{self.BASE_URL}/auth/v3/tenant_access_token/internal",
            json={"app_id": self.app_id, "app_secret": self.app_secret},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 0:
            raise RuntimeError(f"Feishu auth failed: {data}")
        self._token = data["tenant_access_token"]
        self._token_expires = time.time() + data.get("expire", 7200) - 60
        return self._token

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._get_tenant_token()}",
            "Content-Type": "application/json; charset=utf-8",
        }

    # ── Messages ──────────────────────────────────────────────

    def send_message(
        self,
        receive_id: str,
        msg_type: str,
        content: str,
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """Send a message to a chat or user.

        Args:
            receive_id: chat_id / open_id / user_id / union_id / email
            msg_type: text / post / interactive / image / ...
            content: JSON string of message content
            receive_id_type: type of receive_id
        """
        resp = requests.post(
            f"{self.BASE_URL}/im/v1/messages",
            params={"receive_id_type": receive_id_type},
            headers=self._headers(),
            json={
                "receive_id": receive_id,
                "msg_type": msg_type,
                "content": content,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def send_text(
        self, receive_id: str, text: str, receive_id_type: str = "chat_id"
    ) -> Dict[str, Any]:
        """Send a plain text message."""
        content = json.dumps({"text": text})
        return self.send_message(receive_id, "text", content, receive_id_type)

    def send_card(
        self,
        receive_id: str,
        card: Dict[str, Any],
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """Send an interactive card message."""
        return self.send_message(
            receive_id, "interactive", json.dumps(card), receive_id_type
        )

    def reply_message(
        self, message_id: str, msg_type: str, content: str
    ) -> Dict[str, Any]:
        """Reply to a specific message."""
        resp = requests.post(
            f"{self.BASE_URL}/im/v1/messages/{message_id}/reply",
            headers=self._headers(),
            json={"msg_type": msg_type, "content": content},
        )
        resp.raise_for_status()
        return resp.json()

    # ── Chat Messages ─────────────────────────────────────────

    def get_chat_messages(
        self,
        container_id: str,
        page_size: int = 50,
        page_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """List messages in a chat.

        Args:
            container_id: chat_id
            page_size: max 50
            page_token: pagination token
        """
        params = {
            "container_id_type": "chat",
            "container_id": container_id,
            "page_size": min(page_size, 50),
        }
        if page_token:
            params["page_token"] = page_token
        resp = requests.get(
            f"{self.BASE_URL}/im/v1/messages",
            params=params,
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Chat Info ─────────────────────────────────────────────

    def get_chat_info(self, chat_id: str) -> Dict[str, Any]:
        """Get chat metadata (name, description, members count)."""
        resp = requests.get(
            f"{self.BASE_URL}/im/v1/chats/{chat_id}",
            headers=self._headers(),
        )
        resp.raise_for_status()
        return resp.json()

    # ── Decision Card Builder ─────────────────────────────────

    @staticmethod
    def build_decision_card(
        title: str,
        decision: str,
        rationale: str,
        alternatives: Optional[List[str]] = None,
        participants: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Build a Feishu interactive card for a decision record."""
        elements = [
            {
                "tag": "markdown",
                "content": f"**Decision:** {decision}\n\n**Rationale:** {rationale}",
            }
        ]
        if alternatives:
            alt_text = "\n".join(f"- {a}" for a in alternatives)
            elements.append({"tag": "markdown", "content": f"**Alternatives:**\n{alt_text}"})
        if participants:
            elements.append(
                {"tag": "markdown", "content": f"**Participants:** {', '.join(participants)}"}
            )
        return {
            "config": {"wide_screen_mode": True},
            "header": {"title": {"tag": "plain_text", "content": title}},
            "elements": elements,
        }
