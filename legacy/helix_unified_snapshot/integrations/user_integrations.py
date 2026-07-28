"""
User Integration Manager
======================

Allows users to connect their own external accounts:
- Discord servers (guilds)
- Telegram bots/groups
- Microsoft Teams channels
- Slack workspaces
- Custom webhooks

Each user can have multiple connections, and each connection
can have its own configuration.

Author: Claude
Date: 2026-02-27
"""

import ipaddress
import logging
import secrets
import socket
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Session

from apps.backend.db_models import Subscription, SubscriptionTier, TierLimits
from apps.backend.models.base import Base

logger = logging.getLogger(__name__)

# ============================================================================
# INTEGRATION TYPES
# ============================================================================


class IntegrationType(StrEnum):
    """Types of user integrations"""

    DISCORD = "discord"
    TELEGRAM = "telegram"
    TEAMS = "teams"
    SLACK = "slack"
    WEBHOOK = "webhook"
    EMAIL = "email"
    NOTION = "notion"
    GOOGLE_CALENDAR = "google_calendar"


class IntegrationStatus(StrEnum):
    """Integration connection status"""

    PENDING = "pending"
    ACTIVE = "active"
    ERROR = "error"
    DISABLED = "disabled"


# ============================================================================
# DATABASE MODELS
# ============================================================================


class UserIntegration(Base):
    """User's external service connection"""

    __tablename__ = "user_integrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = Column(String(36), nullable=False, index=True)

    # Integration type and external ID
    integration_type = Column(String(50), nullable=False, index=True)
    external_id = Column(String(255), nullable=True, index=True)  # Server/channel/workspace ID
    external_name = Column(String(255), nullable=True)

    # Connection details (encrypted in production)
    bot_token = Column(Text, nullable=True)  # Bot token for the user's server
    access_token = Column(Text, nullable=True)  # OAuth access token
    refresh_token = Column(Text, nullable=True)  # OAuth refresh token
    token_expires_at = Column(DateTime, nullable=True)

    # Webhook URL (for custom webhooks)
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)

    # Configuration
    config = Column(JSONB, default={})  # Per-integration settings

    # Status
    status = Column(String(20), default=IntegrationStatus.PENDING.value, nullable=False)

    # Notification settings
    notify_on_agent_mentions = Column(Boolean, default=True)
    notify_on_coordination_updates = Column(Boolean, default=False)
    notify_on_cycles = Column(Boolean, default=False)
    notify_on_errors = Column(Boolean, default=True)

    # Filters
    filter_keywords = Column(JSONB, default=[])  # Keywords to filter
    filter_agent_ids = Column(JSONB, default=[])  # Specific agents to follow

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC))
    last_sync_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<UserIntegration(user={self.user_id}, type={self.integration_type}, name={self.external_name})>"


class UserIntegrationInvite(Base):
    """Invite codes for users to connect integrations"""

    __tablename__ = "user_integration_invites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    code = Column(String(50), unique=True, nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)

    # What type of integration this invite is for
    integration_type = Column(String(50), nullable=False)

    # Optional: limit to specific external ID
    target_external_id = Column(String(255), nullable=True)

    # Usage
    max_uses = Column(DateTime, nullable=True)
    uses_count = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))


# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class CreateIntegrationRequest(BaseModel):
    """Request to create a new integration connection"""

    integration_type: IntegrationType
    external_id: str | None = None
    external_name: str | None = None
    webhook_url: str | None = None

    # For Discord/Telegram/Teams bot tokens
    bot_token: str | None = None

    # Notification settings
    notify_on_agent_mentions: bool = True
    notify_on_coordination_updates: bool = False
    notify_on_cycles: bool = False
    notify_on_errors: bool = True

    # Filters
    filter_keywords: list[str] = []
    filter_agent_ids: list[str] = []


class UpdateIntegrationRequest(BaseModel):
    """Request to update integration settings"""

    # Status
    status: IntegrationStatus | None = None

    # Notification settings
    notify_on_agent_mentions: bool | None = None
    notify_on_coordination_updates: bool | None = None
    notify_on_cycles: bool | None = None
    notify_on_errors: bool | None = None

    # Filters
    filter_keywords: list[str] | None = None
    filter_agent_ids: list[str] | None = None


class IntegrationResponse(BaseModel):
    """Integration connection response"""

    id: str
    integration_type: str
    external_id: str | None
    external_name: str | None
    status: str

    # Notification settings (no tokens exposed)
    notify_on_agent_mentions: bool
    notify_on_coordination_updates: bool
    notify_on_cycles: bool
    notify_on_errors: bool

    # Metadata
    created_at: str
    updated_at: str
    last_sync_at: str | None = None
    last_error: str | None = None


class IntegrationInviteResponse(BaseModel):
    """Invite for connecting an integration"""

    code: str
    integration_type: str
    invite_url: str
    expires_at: str | None


class TestIntegrationRequest(BaseModel):
    """Request to test an integration"""

    message: str = "Test message from Helix Collective"


# ============================================================================
# USER INTEGRATION MANAGER
# ============================================================================


async def _is_safe_webhook_url(url: str) -> bool:
    """Validate that a webhook URL does not target private/internal networks (SSRF prevention).

    Async to avoid blocking the event loop during DNS resolution.
    """
    import asyncio

    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        loop = asyncio.get_event_loop()
        results = await loop.getaddrinfo(hostname, parsed.port or 443, proto=socket.IPPROTO_TCP)
        for info in results:
            addr = info[4][0]
            ip = ipaddress.ip_address(addr)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        return True
    except (socket.gaierror, ValueError):
        return False


class UserIntegrationManager:
    """Manages user's external service connections"""

    def __init__(self, db: Session):
        self.db = db

    def get_user_integrations(
        self,
        user_id: str,
        integration_type: IntegrationType | None = None,
        status: IntegrationStatus | None = None,
    ) -> list[UserIntegration]:
        """Get all integrations for a user"""
        query = self.db.query(UserIntegration).filter(UserIntegration.user_id == user_id)

        if integration_type:
            query = query.filter(UserIntegration.integration_type == integration_type.value)

        if status:
            query = query.filter(UserIntegration.status == status.value)

        return query.order_by(UserIntegration.created_at.desc()).limit(200).all()

    def get_integration(self, integration_id: str, user_id: str) -> UserIntegration | None:
        """Get a specific integration"""
        return (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.id == integration_id,
                UserIntegration.user_id == user_id,
            )
            .first()
        )

    async def create_integration(
        self,
        user_id: str,
        request: CreateIntegrationRequest,
    ) -> UserIntegration:
        """Create a new integration connection"""

        # Check subscription tier limits
        await self._check_tier_limits(user_id, request.integration_type)

        # Check if integration already exists
        existing = (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.integration_type == request.integration_type.value,
                UserIntegration.external_id == request.external_id,
            )
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=400,
                detail="This integration is already connected",
            )

        # Create new integration
        integration = UserIntegration(
            user_id=user_id,
            integration_type=request.integration_type.value,
            external_id=request.external_id,
            external_name=request.external_name,
            webhook_url=request.webhook_url,
            bot_token=request.bot_token,
            status=IntegrationStatus.PENDING.value,
            notify_on_agent_mentions=request.notify_on_agent_mentions,
            notify_on_coordination_updates=request.notify_on_coordination_updates,
            notify_on_cycles=request.notify_on_cycles,
            notify_on_errors=request.notify_on_errors,
            filter_keywords=request.filter_keywords,
            filter_agent_ids=request.filter_agent_ids,
        )

        self.db.add(integration)
        self.db.commit()
        self.db.refresh(integration)

        # Verify the connection
        await self._verify_integration(integration)

        return integration

    async def update_integration(
        self,
        integration_id: str,
        user_id: str,
        request: UpdateIntegrationRequest,
    ) -> UserIntegration:
        """Update integration settings"""
        integration = self.get_integration(integration_id, user_id)

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Update fields
        if request.status:
            integration.status = request.status.value
        if request.notify_on_agent_mentions is not None:
            integration.notify_on_agent_mentions = request.notify_on_agent_mentions
        if request.notify_on_coordination_updates is not None:
            integration.notify_on_coordination_updates = request.notify_on_coordination_updates
        if request.notify_on_cycles is not None:
            integration.notify_on_cycles = request.notify_on_cycles
        if request.notify_on_errors is not None:
            integration.notify_on_errors = request.notify_on_errors
        if request.filter_keywords is not None:
            integration.filter_keywords = request.filter_keywords
        if request.filter_agent_ids is not None:
            integration.filter_agent_ids = request.filter_agent_ids

        integration.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(integration)

        return integration

    async def delete_integration(
        self,
        integration_id: str,
        user_id: str,
    ) -> bool:
        """Delete an integration"""
        integration = self.get_integration(integration_id, user_id)

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        # Clean up tokens
        integration.bot_token = None
        integration.access_token = None
        integration.refresh_token = None
        integration.status = IntegrationStatus.DISABLED.value

        self.db.commit()
        return True

    async def test_integration(
        self,
        integration_id: str,
        user_id: str,
        message: str = "Test",
    ) -> bool:
        """Test an integration by sending a message"""
        integration = self.get_integration(integration_id, user_id)

        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        if integration.status != IntegrationStatus.ACTIVE.value:
            raise HTTPException(status_code=400, detail="Integration is not active")

        # Send test message based on type
        if integration.integration_type == IntegrationType.WEBHOOK.value:
            return await self._test_webhook(integration, message)
        elif integration.integration_type == IntegrationType.DISCORD.value:
            return await self._test_discord(integration, message)
        elif integration.integration_type == IntegrationType.TELEGRAM.value:
            return await self._test_telegram(integration, message)
        elif integration.integration_type == IntegrationType.TEAMS.value:
            return await self._test_teams(integration, message)

        raise HTTPException(status_code=400, detail="Unsupported integration type")

    async def create_invite(
        self,
        user_id: str,
        integration_type: IntegrationType,
        target_external_id: str | None = None,
    ) -> UserIntegrationInvite:
        """Create an invite code for connecting an integration"""
        code = secrets.token_urlsafe(16)

        invite = UserIntegrationInvite(
            code=code,
            user_id=user_id,
            integration_type=integration_type.value,
            target_external_id=target_external_id,
        )

        self.db.add(invite)
        self.db.commit()
        self.db.refresh(invite)

        return invite

    # =========================================================================
    # PRIVATE METHODS
    # =========================================================================

    async def _check_tier_limits(
        self,
        user_id: str,
        integration_type: IntegrationType,
    ) -> None:
        """Check if user has subscription tier to create this integration"""
        try:
            # Get user's subscription
            subscription = (
                self.db.query(Subscription)
                .filter(Subscription.user_id == user_id, Subscription.status == "active")
                .first()
            )

            if not subscription:
                # Default to free tier
                tier = SubscriptionTier.FREE
            else:
                tier = subscription.tier

            # Get current integration count
            current_count = self.db.query(UserIntegration).filter(UserIntegration.user_id == user_id).count()

            # Get limit for this tier
            limit = TierLimits.get_limit(tier, "user_integrations")

            # Check if limit is reached (0 = not allowed, -1 = unlimited)
            if limit == 0:
                raise HTTPException(
                    status_code=403, detail=f"Integrations not available on {tier.value} plan. Upgrade to access."
                )
            elif limit > 0 and current_count >= limit:
                raise HTTPException(
                    status_code=403, detail=f"Integration limit reached ({limit}). Upgrade to add more."
                )

        except HTTPException:
            raise
        except Exception as e:
            logger.error("Error checking tier limits: %s", e)
            # Allow on error to not block users

    async def _verify_integration(self, integration: UserIntegration) -> bool:
        """Verify that an integration is valid"""
        try:
            if integration.integration_type == IntegrationType.WEBHOOK.value:
                # Test webhook URL
                if not integration.webhook_url:
                    integration.status = IntegrationStatus.ERROR.value
                    integration.last_error = "No webhook URL"
                    return False

                if not await _is_safe_webhook_url(integration.webhook_url):
                    integration.status = IntegrationStatus.ERROR.value
                    integration.last_error = "Webhook URL targets blocked address"
                    return False

                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        integration.webhook_url,
                        json={"type": "test", "message": "Helix Collective connection test"},
                        timeout=10,
                    )

                if response.status_code < 400:
                    integration.status = IntegrationStatus.ACTIVE.value
                    return True
                else:
                    integration.status = IntegrationStatus.ERROR.value
                    integration.last_error = f"Webhook returned {response.status_code}"
                    return False

            # Add other integration verifications...
            integration.status = IntegrationStatus.ACTIVE.value
            return True

        except Exception as e:
            integration.status = IntegrationStatus.ERROR.value
            logger.warning("Integration verification failed: %s", e)
            integration.last_error = "Verification failed"
            return False

    async def _test_webhook(self, integration: UserIntegration, message: str) -> bool:
        """Test a webhook integration"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                integration.webhook_url,
                json={
                    "text": message,
                    "source": "helix-collective",
                    "integration_id": str(integration.id),
                },
                timeout=10,
            )
        return response.status_code < 400

    async def _test_discord(self, integration: UserIntegration, message: str) -> bool:
        """Test a Discord integration"""
        # Would send via Discord API
        logger.info("Discord test for %s: %s", integration.external_name, message)
        return True

    async def _test_telegram(self, integration: UserIntegration, message: str) -> bool:
        """Test a Telegram integration"""
        logger.info("Telegram test for %s: %s", integration.external_name, message)
        return True

    async def _test_teams(self, integration: UserIntegration, message: str) -> bool:
        """Test a Teams integration"""
        logger.info("Teams test for %s: %s", integration.external_name, message)
        return True


# ============================================================================
# NOTIFICATION DISPATCHER
# ============================================================================


class IntegrationNotifier:
    """Send notifications to user's integrations"""

    def __init__(self, db: Session):
        self.db = db

    async def notify_agent_mention(
        self,
        user_id: str,
        agent_name: str,
        message: str,
    ):
        """Notify user when an agent mentions them"""
        integrations = (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.status == IntegrationStatus.ACTIVE.value,
                UserIntegration.integration_type == IntegrationType.DISCORD.value,
                UserIntegration.notify_on_agent_mentions.is_(True),
            )
            .limit(100)  # Per-user safeguard
            .all()
        )

        for integration in integrations:
            await self._send_notification(integration, f"Agent {agent_name}: {message}")

    async def notify_coordination_update(
        self,
        user_id: str,
        metrics: dict[str, float],
    ):
        """Notify user of coordination updates"""
        integrations = (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.status == IntegrationStatus.ACTIVE.value,
                UserIntegration.notify_on_coordination_updates.is_(True),
            )
            .limit(100)  # Per-user safeguard
            .all()
        )

        metrics_text = ", ".join([f"{k}: {v:.2f}" for k, v in metrics.items()])
        for integration in integrations:
            await self._send_notification(integration, f"Coordination Update: {metrics_text}")

    async def notify_error(
        self,
        user_id: str,
        error_message: str,
    ):
        """Notify user of errors"""
        integrations = (
            self.db.query(UserIntegration)
            .filter(
                UserIntegration.user_id == user_id,
                UserIntegration.status == IntegrationStatus.ACTIVE.value,
                UserIntegration.notify_on_errors.is_(True),
            )
            .limit(100)  # Per-user safeguard
            .all()
        )

        for integration in integrations:
            await self._send_notification(integration, f"Error: {error_message}")

    async def _send_notification(self, integration: UserIntegration, message: str):
        """Send notification to specific integration"""
        if integration.integration_type == IntegrationType.WEBHOOK.value:
            await self._send_webhook(integration, message)
        # Add other types...

    async def _send_webhook(self, integration: UserIntegration, message: str):
        """Send webhook notification"""
        if not integration.webhook_url:
            return

        if not await _is_safe_webhook_url(integration.webhook_url):
            logger.warning("Blocked webhook to unsafe URL for integration %s", integration.id)
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    integration.webhook_url,
                    json={
                        "text": message,
                        "source": "helix-collective",
                        "integration_id": str(integration.id),
                    },
                )
                if response.status_code >= 400:
                    logger.warning(
                        "Webhook delivery failed for integration %s: HTTP %d",
                        integration.id,
                        response.status_code,
                    )
        except Exception as exc:
            logger.warning("Webhook delivery error for integration %s: %s", integration.id, exc)
