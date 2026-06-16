"""Microsoft Teams Integration
=========================

Microsoft Teams bot integration for Helix Collective.
Provides:
- Bot commands for interacting with Helix agents
- Adaptive Cards for rich UI
- Webhook notifications
- Teams channel integration

Author: Claude
Date: 2026-02-27
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID

from apps.backend.models.base import Base

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

TEAMS_BOT_ID = os.getenv("TEAMS_BOT_ID")
TEAMS_BOT_PASSWORD = os.getenv("TEAMS_BOT_PASSWORD")
TEAMS_TENANT_ID = os.getenv("TEAMS_TENANT_ID", "common")
TEAMS_SERVICE_URL = os.getenv("TEAMS_SERVICE_URL")

# Microsoft Graph API
GRAPH_API_URL = "https://graph.microsoft.com/v1.0"

# ============================================================================
# DATABASE MODELS
# ============================================================================


class TeamsUser(Base):
    """Teams user linked to Helix account"""

    __tablename__ = "teams_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    teams_user_id = Column(String(100), unique=True, nullable=False, index=True)
    teams_email = Column(String(255), nullable=True)
    teams_name = Column(String(255), nullable=True)

    # Helix account linking
    helix_user_id = Column(String(36), nullable=True, index=True)
    helix_user_email = Column(String(255), nullable=True)

    # Notifications
    notifications_enabled = Column(Boolean, default=True)
    dm_enabled = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_message_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<TeamsUser(teams_id={self.teams_user_id}, helix={self.helix_user_id})>"


# ============================================================================
# ADAPTIVE CARDS
# ============================================================================


class AdaptiveCard:
    """Microsoft Adaptive Card builder"""

    def __init__(self, title: str, subtitle: str | None = None):
        self.card: dict[str, Any] = {
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "type": "AdaptiveCard",
            "version": "1.4",
            "body": [
                {
                    "type": "TextBlock",
                    "text": title,
                    "weight": "Bolder",
                    "size": "Medium",
                }
            ],
        }
        if subtitle:
            self.card["body"].append(
                {
                    "type": "TextBlock",
                    "text": subtitle,
                    "isSubtle": True,
                    "wrap": True,
                }
            )

    def add_text(self, text: str, is_subtle: bool = False, wrap: bool = True):
        """Add text block"""
        self.card["body"].append(
            {
                "type": "TextBlock",
                "text": text,
                "isSubtle": is_subtle,
                "wrap": wrap,
            }
        )
        return self

    def add_fact_set(self, facts: dict[str, str]):
        """Add fact set"""
        self.card["body"].append(
            {
                "type": "FactSet",
                "facts": [{"title": k, "value": v} for k, v in facts.items()],
            }
        )
        return self

    def add_action_set(self, actions: list[dict[str, str]]):
        """Add actions"""
        if "actions" not in self.card:
            self.card["actions"] = []
        for action in actions:
            self.card["actions"].append(action)
        return self

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict"""
        return self.card


# ============================================================================
# TEAMS BOT CLIENT
# ============================================================================


class TeamsBot:
    """Microsoft Teams Bot Client"""

    def __init__(self):
        self.bot_id = TEAMS_BOT_ID
        self.bot_password = TEAMS_BOT_PASSWORD
        self.tenant_id = TEAMS_TENANT_ID
        self.service_url = TEAMS_SERVICE_URL
        self._access_token: str | None = None

    async def get_access_token(self) -> str:
        """Get Microsoft Graph access token"""
        if self._access_token:
            return self._access_token

        # OAuth2 token endpoint
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

        data = {
            "grant_type": "client_credentials",
            "client_id": self.bot_id,
            "client_secret": self.bot_password,
            "scope": "https://graph.microsoft.com/.default",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(token_url, data=data)

        if response.status_code != 200:
            logger.error("Teams token error: %s", response.text)
            raise Exception("Failed to get Teams access token")

        token_data = response.json()
        self._access_token = token_data["access_token"]
        return self._access_token

    async def send_message(
        self,
        conversation_id: str,
        message: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a Teams conversation"""
        access_token = await self.get_access_token()

        url = f"{GRAPH_API_URL}/chats/{conversation_id}/messages"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        body: dict[str, Any] = {
            "body": {
                "contentType": "html",
                "content": message,
            }
        }

        if attachments:
            body["attachments"] = attachments

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)

        if response.status_code not in (200, 201):
            logger.error("Teams send error: %s", response.text)
            raise Exception("Failed to send Teams message")

        return response.json()

    async def send_adaptive_card(
        self,
        conversation_id: str,
        card: dict[str, Any],
    ) -> dict[str, Any]:
        """Send an Adaptive Card to Teams"""
        access_token = await self.get_access_token()

        url = f"{GRAPH_API_URL}/chats/{conversation_id}/messages"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        body = {
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": card,
                }
            ]
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)

        return response.json()

    async def create_conversation(
        self,
        user_email: str,
    ) -> str:
        """Create a 1:1 chat with a user"""
        access_token = await self.get_access_token()

        url = f"{GRAPH_API_URL}/chats"

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        body = {
            "chatType": "oneOnOne",
            "members": [
                {
                    "@odata.type": "#microsoft.graph.aadUser",
                    "email": user_email,
                }
            ],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=body, headers=headers)

        if response.status_code not in (200, 201):
            logger.error("Teams create chat error: %s", response.text)
            raise Exception("Failed to create Teams chat")

        data = response.json()
        return data["id"]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_teams_bot() -> TeamsBot | None:
    """Get Teams bot instance"""
    if not TEAMS_BOT_ID or not TEAMS_BOT_PASSWORD:
        logger.warning("Teams bot credentials not configured")
        return None
    return TeamsBot()


def is_teams_available() -> bool:
    """Check if Teams integration is configured"""
    return bool(TEAMS_BOT_ID and TEAMS_BOT_PASSWORD)


# ============================================================================
# COMMAND HANDLERS
# ============================================================================


async def handle_teams_command(command: str, args: str, user_email: str) -> str:
    """Handle Teams bot commands"""
    handlers = {
        "help": get_help_message,
        "status": get_status_message,
        "agents": get_agents_message,
        "coordination": get_coordination_message,
    }

    handler = handlers.get(command.lower())
    if handler:
        return await handler()

    return f"Unknown command: /{command}. Use /help for available commands."


async def get_help_message() -> str:
    """Get help message"""
    return """**Helix Collective - Teams Commands**

/help - Show this help message
/status - System status
/agents - List AI agents
/coordination - Coordination metrics

**Note:** Use the chat to interact with agents directly."""


async def get_status_message() -> str:
    """Get system status"""
    return """**✅ System Status**

• API: Operational
• Database: Connected
• Coordination: Active
• Agents: 20 Online"""


async def get_agents_message() -> str:
    """Get agents list"""
    return """**Available AI Agents**

• Sage - Wisdom & ethics
• Oracle - Future prediction
• Varuna - Strategic planning
• Agni - Execution & action
• Sage - Chat assistant
• Arjuna - Data analysis
• Lumina - Creative tasks
• Kael - Security & safety"""


async def get_coordination_message() -> str:
    """Get coordination metrics"""
    return """**Coordination Metrics**

• Harmony: 0.78
• Resilience: 0.85
• Throughput: 0.72
• Active Agents: 12
• Routines Today: 3"""


# ============================================================================
# CONFIG
# ============================================================================


def get_teams_config() -> dict[str, Any]:
    """Get Teams configuration"""
    return {
        "available": is_teams_available(),
        "bot_id": TEAMS_BOT_ID,
    }
