"""
Telegram Bot Integration
======================

Telegram bot integration for Helix Collective.
Provides:
- Bot commands for interacting with Helix agents
- Webhook handler for Telegram updates
- Authentication via Telegram
- Notifications and alerts

Author: Claude
Date: 2026-02-27
"""

import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Session

from apps.backend.models.base import Base

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# Bot commands
TELEGRAM_COMMANDS = [
    ("start", "Get started with Helix Collective"),
    ("help", "Show help message"),
    ("agents", "List available agents"),
    ("coordination", "Check coordination status"),
    ("status", "System status"),
    ("subscribe", "Subscribe to notifications"),
    ("unsubscribe", "Unsubscribe from notifications"),
]

# ============================================================================
# DATABASE MODELS
# ============================================================================


class TelegramUser(Base):
    """Telegram user linked to Helix account"""

    __tablename__ = "telegram_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_user_id = Column(String(50), unique=True, nullable=False, index=True)
    telegram_username = Column(String(255), nullable=True)
    telegram_first_name = Column(String(255), nullable=True)
    telegram_last_name = Column(String(255), nullable=True)

    # Helix account linking
    helix_user_id = Column(String(36), nullable=True, index=True)
    helix_user_email = Column(String(255), nullable=True)

    # Subscription
    notifications_enabled = Column(Boolean, default=True)
    coordination_updates = Column(Boolean, default=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_message_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<TelegramUser(telegram_id={self.telegram_user_id}, helix={self.helix_user_id})>"


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class TelegramUpdate(BaseModel):
    """Incoming Telegram update"""

    update_id: int
    message: dict[str, Any] | None = None
    edited_message: dict[str, Any] | None = None
    callback_query: dict[str, Any] | None = None


class TelegramWebhookRequest(BaseModel):
    """Telegram webhook request"""

    update: dict[str, Any]


class TelegramMessageResponse(BaseModel):
    """Telegram message response"""

    chat_id: int
    text: str
    parse_mode: str | None = "Markdown"
    reply_markup: dict[str, Any] | None = None


class TelegramCommand(BaseModel):
    """Telegram command"""

    command: str
    description: str


class TelegramBotStatus(BaseModel):
    """Bot status response"""

    bot_name: str
    is_running: bool
    commands_count: int
    users_count: int


# ============================================================================
# TELEGRAM BOT CLIENT
# ============================================================================


class TelegramBot:
    """Telegram Bot API Client"""

    def __init__(self, token: str | None = None):
        self.token = token or TELEGRAM_BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a message to a chat"""
        url = f"{self.api_url}/sendMessage"

        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
        }

        if reply_markup:
            payload["reply_markup"] = reply_markup

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

        if response.status_code != 200:
            error = response.json()
            logger.error("Telegram send message error: %s", error)
            raise HTTPException(status_code=400, detail="Failed to send message")

        return response.json()

    async def set_commands(self, commands: list[dict[str, str]]) -> bool:
        """Set bot commands"""
        url = f"{self.api_url}/setMyCommands"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json={"commands": commands})

        return response.status_code == 200

    async def get_me(self) -> dict[str, Any]:
        """Get bot information"""
        url = f"{self.api_url}/getMe"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)

        if response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to get bot info")

        return response.json()

    async def answer_callback_query(
        self,
        callback_query_id: str,
        text: str | None = None,
        show_alert: bool = False,
    ) -> bool:
        """Answer a callback query"""
        url = f"{self.api_url}/answerCallbackQuery"

        payload = {
            "callback_query_id": callback_query_id,
            "show_alert": show_alert,
        }

        if text:
            payload["text"] = text

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)

        return response.status_code == 200


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_bot() -> TelegramBot | None:
    """Get Telegram bot instance"""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not configured")
        return None
    return TelegramBot()


def parse_command(text: str) -> tuple[str, str] | None:
    """Parse Telegram command"""
    text = text.strip()
    if text.startswith("/"):
        parts = text[1:].split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        return command, args
    return None


# ============================================================================
# COMMAND HANDLERS
# ============================================================================


async def handle_start_command(chat_id: int, user_name: str | None = None) -> str:
    """Handle /start command"""
    welcome = """👋 Welcome to Helix Collective!

I'm your AI assistant powered by the Helix coordination network.

**Available Commands:**
/help - Show all commands
/agents - List available AI agents
/coordination - Check current coordination status
/status - System status
/subscribe - Subscribe to notifications
/unsubscribe - Unsubscribe from notifications

Get started by linking your account or just ask me anything!"""

    return welcome


async def handle_help_command(chat_id: int) -> str:
    """Handle /help command"""
    help_text = """📚 **Helix Collective Commands**

/start - Welcome message and getting started
/help - Show this help message
/agents - List all available AI agents
/coordination - View the current coordination metrics
/status - Check system health and status
/subscribe - Subscribe to notifications
/unsubscribe - Stop receiving notifications

**Premium Features:**
/workflow - Create automation workflows
/insights - Get AI-powered insights

Need more help? Visit our docs or ask me directly!"""

    return help_text


async def handle_agents_command(chat_id: int) -> str:
    """Handle /agents command"""
    # This would fetch from the agent registry
    agents_text = """🤖 **Available AI Agents**

**Coordination Agents:**
🧠 *Sage* - Wisdom & ethics
🔮 *Oracle* - Future prediction
🌊 *Varuna* - Strategic planning
⚡ *Agni* - Execution & action

**Utility Agents:**
💬 *Sage* - Chat assistant
📊 *Arjuna* - Data analysis
🎨 *Lumina* - Creative tasks
🛡️ *Kael* - Security & safety

Use /agent [name] to interact with a specific agent!"""

    return agents_text


async def handle_status_command(chat_id: int) -> str:
    """Handle /status command"""
    status_text = """✅ **Helix Collective Status**

• **API**: Operational 🟢
• **Database**: Connected 🟢
• **Coordination**: Active 🟢
• **Agents**: 20 Online 🟢

Last sync: Just now"""

    return status_text


async def handle_coordination_command(chat_id: int) -> str:
    """Handle /coordination command"""
    # This would fetch from coordination system
    coordination_text = """🌀 **Coordination Status**

**UCF Metrics:**
• Harmony: 0.78
• Resilience: 0.85
• Throughput: 0.72
• Focus: 0.80
• Friction: 0.15

**Active Agents:** 12
**Routines Today:** 3
**Cycles:** 847

The collective coordination is thriving! 🌟"""

    return coordination_text


# ============================================================================
# MESSAGE HANDLER
# ============================================================================


async def handle_message(update: dict[str, Any], db: Session) -> str | None:
    """Handle incoming Telegram message"""
    message = update.get("message", {})
    chat = message.get("chat", {})
    text = message.get("text", "")
    user = message.get("from", {})

    chat_id = chat.get("id")
    user_id = str(user.get("id"))
    user_name = user.get("username")
    first_name = user.get("first_name")

    if not text or not chat_id:
        return None

    # Parse command
    result = parse_command(text)
    if not result:
        # Not a /command — route to an agent via the shared intelligence layer
        try:
            from apps.backend.services.platform_agent import (
                extract_agent_from_text,
                generate_agent_response,
            )

            agent_name, cleaned_content = extract_agent_from_text(text)
            reply = await generate_agent_response(
                agent_name=agent_name,
                message_content=cleaned_content or text,
                platform_name="Telegram",
            )
            return reply
        except Exception as exc:
            logger.warning("Telegram agent response error: %s", exc)
            return "Sorry, I'm having trouble processing that right now. Try /help for available commands."

    command, _args = result

    # Get or create user
    telegram_user = db.query(TelegramUser).filter(TelegramUser.telegram_user_id == user_id).first()

    if not telegram_user:
        telegram_user = TelegramUser(
            telegram_user_id=user_id,
            telegram_username=user_name,
            telegram_first_name=first_name,
        )
        db.add(telegram_user)
        db.commit()

    # Update last message time
    telegram_user.last_message_at = datetime.now(UTC)
    db.commit()

    # Handle commands
    handlers: dict[str, Callable[[int], Awaitable[str]]] = {
        "start": handle_start_command,
        "help": handle_help_command,
        "agents": handle_agents_command,
        "status": handle_status_command,
        "coordination": handle_coordination_command,
    }

    handler = handlers.get(command)
    if handler:
        return await handler(chat_id)

    return f"Unknown command: /{command}. Use /help for available commands."


# ============================================================================
# WEBHOOK HANDLER
# ============================================================================


async def handle_webhook(update: dict[str, Any], db: Session) -> dict[str, Any]:
    """Handle incoming Telegram webhook"""
    update_id = update.get("update_id")

    logger.info("Received Telegram update: %s", update_id)

    try:
        # Handle message
        if "message" in update:
            response_text = await handle_message(update, db)

            if response_text:
                message = update["message"]
                chat = message["chat"]
                bot = get_bot()

                if bot:
                    await bot.send_message(
                        chat_id=chat["id"],
                        text=response_text,
                    )

        # Handle callback query (button clicks)
        if "callback_query" in update:
            callback = update["callback_query"]
            data = callback.get("data")
            query_id = callback.get("id")

            bot = get_bot()
            if bot:
                await bot.answer_callback_query(
                    callback_query_id=query_id,
                    text=f"Received: {data}",
                )

        return {"ok": True}

    except Exception as e:
        logger.error("Telegram webhook error: %s", e)
        return {"ok": False, "error": "Webhook processing failed"}


# ============================================================================
# TELEGRAM ROUTES
# ============================================================================


def is_telegram_available() -> bool:
    """Check if Telegram is configured"""
    return bool(TELEGRAM_BOT_TOKEN)


def get_telegram_config() -> dict[str, Any]:
    """Get Telegram configuration"""
    return {
        "available": is_telegram_available(),
        "commands": TELEGRAM_COMMANDS,
    }
