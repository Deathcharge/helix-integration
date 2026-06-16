"""
Cross-Platform Event Bridge

Routes events between Discord, Forum, Browser Chat, and other platforms.
Enables agents to:
- React to Discord discussions in Forum
- Share Forum highlights to Discord channels
- Maintain conversation continuity across platforms

Key Features:
- Event filtering by topic/relevance
- Rate limiting to prevent spam
- Consent-aware routing
- Platform-specific formatting
- Approval queue for high-impact actions

Author: Helix Collective
Version: 1.0.0
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

from apps.backend.integrations.agent_memory_service import (
    AgentMemoryService,
    MemoryType,
    Platform,
    get_memory_service,
)
from apps.backend.learning.consent_system import ConsentSystem
from apps.backend.services.event_bus import EventBus

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Priority levels for cross-platform events"""

    LOW = "low"  # FYI - agents may optionally respond
    NORMAL = "normal"  # Standard processing
    HIGH = "high"  # Important - agents should engage
    URGENT = "urgent"  # Immediate attention required


class EventAction(Enum):
    """Actions an event can trigger"""

    NOTIFY = "notify"  # Send notification to platform
    CREATE_THREAD = "create_thread"  # Create new discussion thread
    REPLY = "reply"  # Reply to existing discussion
    CROSS_POST = "cross_post"  # Share to another platform
    SUMMARIZE = "summarize"  # Ask agent to summarize
    DEBATE = "debate"  # Start agent debate on topic


@dataclass
class CrossPlatformEvent:
    """Event that can be routed between platforms"""

    id: str
    event_type: str  # e.g., "forum.hot_topic", "discord.agent_mention"
    source_platform: Platform
    target_platforms: list[Platform]

    # Content
    title: str
    content: str
    summary: str | None = None

    # Source details
    source_channel_id: str | None = None
    source_thread_id: str | None = None
    source_message_id: str | None = None
    source_url: str | None = None

    # User info (anonymized)
    user_id_hash: str | None = None
    user_display: str = "a community member"

    # Agent info
    agent_id: str | None = None
    suggested_agents: list[str] = field(default_factory=list)

    # Metadata
    priority: EventPriority = EventPriority.NORMAL
    suggested_action: EventAction = EventAction.NOTIFY
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Processing state
    processed: bool = False
    requires_approval: bool = False
    approved: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_type": self.event_type,
            "source_platform": self.source_platform.value,
            "target_platforms": [p.value for p in self.target_platforms],
            "title": self.title,
            "content": self.content,
            "summary": self.summary,
            "source_channel_id": self.source_channel_id,
            "source_thread_id": self.source_thread_id,
            "source_message_id": self.source_message_id,
            "source_url": self.source_url,
            "user_id_hash": self.user_id_hash,
            "user_display": self.user_display,
            "agent_id": self.agent_id,
            "suggested_agents": self.suggested_agents,
            "priority": self.priority.value,
            "suggested_action": self.suggested_action.value,
            "tags": self.tags,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "processed": self.processed,
            "requires_approval": self.requires_approval,
            "approved": self.approved,
        }


@dataclass
class PlatformAdapter:
    """Adapter for platform-specific interactions"""

    platform: Platform
    name: str
    enabled: bool = True

    # Rate limiting
    max_events_per_hour: int = 20
    cooldown_seconds: int = 60

    # Configuration
    auto_approve_low_priority: bool = True
    require_approval_for_threads: bool = True
    allowed_event_types: list[str] = field(default_factory=list)

    # Handlers
    send_handler: Callable | None = None
    format_handler: Callable | None = None


class RateLimiter:
    """Rate limiter for cross-platform events"""

    def __init__(self, max_per_hour: int = 60):
        self.max_per_hour = max_per_hour
        self.events: dict[str, list[datetime]] = {}  # key -> timestamps

    def check(self, key: str) -> bool:
        """Check if rate limit allows action"""
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)

        if key not in self.events:
            self.events[key] = []

        # Clean old events
        self.events[key] = [t for t in self.events[key] if t > hour_ago]

        return len(self.events[key]) < self.max_per_hour

    def record(self, key: str):
        """Record an event"""
        if key not in self.events:
            self.events[key] = []
        self.events[key].append(datetime.now(UTC))


class CrossPlatformEventBridge:
    """
    Routes events between platforms for agent cross-platform awareness.

    Enables scenarios like:
    - Discord hot topic → Agent creates Forum thread
    - Forum trending post → Agent shares in Discord
    - Agent conversation in Discord → Referenced in Forum
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        memory_service: AgentMemoryService | None = None,
        consent_system: ConsentSystem | None = None,
    ):
        self.event_bus = event_bus or EventBus()
        self.memory_service = memory_service or get_memory_service()
        self.consent_system = consent_system or ConsentSystem()

        # Adapters for each platform
        self.adapters: dict[Platform, PlatformAdapter] = {}

        # Event queues
        self.pending_queue: list[CrossPlatformEvent] = []
        self.approval_queue: list[CrossPlatformEvent] = []
        self.processed_events: dict[str, CrossPlatformEvent] = {}

        # Rate limiting
        self.rate_limiter = RateLimiter(max_per_hour=60)

        # Event handlers
        self.event_handlers: dict[str, list[Callable]] = {}

        # Agent topic interests (which agents care about what)
        self.agent_interests: dict[str, list[str]] = {
            "kael": ["ethics", "philosophy", "coordination", "morality"],
            "lumina": ["emotions", "harmony", "relationships", "empathy"],
            "vega": ["infrastructure", "technical", "architecture", "systems"],
            "oracle": ["patterns", "analysis", "predictions", "insights"],
            "sage": ["wisdom", "knowledge", "learning", "education"],
            "gemini": ["balance", "duality", "perspectives", "debate"],
            "agni": ["energy", "transformation", "change", "fire"],
            "kavach": ["security", "protection", "safety", "defense"],
            "shadow": ["hidden", "subconscious", "dreams", "mystery"],
            "echo": ["communication", "resonance", "reflection", "memory"],
            "phoenix": ["rebirth", "renewal", "resilience", "transformation"],
            "helix": ["spiral", "evolution", "growth", "dna"],
            "sanghacore": ["community", "collective", "unity", "together"],
            "mitra": ["friendship", "alliance", "contracts", "bonds"],
            "varuna": ["cosmic", "order", "water", "ethics"],
            "surya": ["illumination", "truth", "light", "clarity"],
            "arjuna": ["action", "skill", "duty", "warrior"],
        }

        self._register_default_adapters()
        logger.info("🌉 Cross-Platform Event Bridge initialized")

    def _register_default_adapters(self):
        """Register default platform adapters"""
        self.adapters[Platform.DISCORD] = PlatformAdapter(
            platform=Platform.DISCORD,
            name="Discord",
            max_events_per_hour=30,
            cooldown_seconds=120,
            allowed_event_types=[
                "forum.hot_topic",
                "forum.agent_response",
                "agent.insight",
            ],
        )

        self.adapters[Platform.FORUM] = PlatformAdapter(
            platform=Platform.FORUM,
            name="Forum",
            max_events_per_hour=20,
            cooldown_seconds=180,
            require_approval_for_threads=True,
            allowed_event_types=[
                "discord.agent_discussion",
                "discord.hot_topic",
                "agent.insight",
            ],
        )

        self.adapters[Platform.BROWSER_CHAT] = PlatformAdapter(
            platform=Platform.BROWSER_CHAT,
            name="Browser Chat",
            max_events_per_hour=50,
            cooldown_seconds=30,
            auto_approve_low_priority=True,
            allowed_event_types=[
                "discord.agent_response",
                "forum.agent_response",
            ],
        )

    def find_interested_agents(self, content: str, tags: list[str]) -> list[str]:
        """Find agents interested in the topic"""
        interested = []
        content_lower = content.lower()
        tags_lower = [t.lower() for t in tags]

        for agent_id, interests in self.agent_interests.items():
            for interest in interests:
                if interest in content_lower or interest in tags_lower:
                    interested.append(agent_id)
                    break

        return interested[:5]  # Max 5 agents per event

    async def create_event(
        self,
        event_type: str,
        source_platform: Platform,
        title: str,
        content: str,
        target_platforms: list[Platform] | None = None,
        source_channel_id: str | None = None,
        source_thread_id: str | None = None,
        source_url: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        priority: EventPriority = EventPriority.NORMAL,
        suggested_action: EventAction = EventAction.NOTIFY,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CrossPlatformEvent:
        """
        Create a cross-platform event.

        Args:
            event_type: Type of event (e.g., "forum.hot_topic")
            source_platform: Where the event originated
            title: Event title
            content: Event content
            target_platforms: Platforms to route to (None = auto-detect)
            source_channel_id: Source channel ID
            source_thread_id: Source thread ID
            source_url: Link to source
            user_id: User who triggered (will be hashed)
            agent_id: Agent involved
            priority: Event priority
            suggested_action: What action to take
            tags: Content tags
            metadata: Additional data

        Returns:
            Created CrossPlatformEvent
        """
        tags = tags or []

        # Auto-detect target platforms
        if target_platforms is None:
            target_platforms = []
            for platform, adapter in self.adapters.items():
                if platform != source_platform and adapter.enabled and event_type in adapter.allowed_event_types:
                    target_platforms.append(platform)

        # Find interested agents
        suggested_agents = self.find_interested_agents(content, tags)
        if agent_id:
            suggested_agents = [agent_id] + [a for a in suggested_agents if a != agent_id]

        # Create event
        event = CrossPlatformEvent(
            id=str(uuid.uuid4()),
            event_type=event_type,
            source_platform=source_platform,
            target_platforms=target_platforms,
            title=title,
            content=content,
            summary=content[:150] + "..." if len(content) > 150 else content,
            source_channel_id=source_channel_id,
            source_thread_id=source_thread_id,
            source_url=source_url,
            user_id_hash=(self.memory_service._hash_user_id(user_id) if user_id else None),
            user_display=(
                self.memory_service._anonymize_user_hint(user_id, source_platform) if user_id else "the community"
            ),
            agent_id=agent_id,
            suggested_agents=suggested_agents,
            priority=priority,
            suggested_action=suggested_action,
            tags=tags,
            metadata=metadata or {},
            expires_at=datetime.now(UTC) + timedelta(hours=24),
        )

        # Determine if approval needed
        event.requires_approval = (
            suggested_action in [EventAction.CREATE_THREAD, EventAction.CROSS_POST] or priority == EventPriority.URGENT
        )

        return event

    async def queue_event(self, event: CrossPlatformEvent) -> bool:
        """
        Queue an event for processing.

        Returns:
            True if queued, False if rate limited
        """
        # Rate limit check
        rate_key = f"{event.source_platform.value}:{event.event_type}"
        if not self.rate_limiter.check(rate_key):
            logger.warning("🌉 Rate limited event: %s", rate_key)
            return False

        self.rate_limiter.record(rate_key)

        if event.requires_approval:
            self.approval_queue.append(event)
            logger.info("🌉 Event %s queued for approval: %s", event.id[:8], event.title)
        else:
            self.pending_queue.append(event)
            logger.info("🌉 Event %s queued: %s", event.id[:8], event.title)

        # Store as memory for involved agents
        for agent_id in event.suggested_agents:
            await self.memory_service.store_memory(
                agent_id=agent_id,
                content=f"Cross-platform event: {event.title}\n{event.summary}",
                memory_type=MemoryType.CONTEXTUAL,
                platform=event.source_platform,
                channel_id=event.source_channel_id,
                importance=0.6 if event.priority == EventPriority.HIGH else 0.4,
                tags=[*event.tags, "cross_platform_event"],
                require_consent=False,  # Agent activity doesn't need consent
            )

        return True

    async def approve_event(self, event_id: str, approved: bool = True) -> CrossPlatformEvent | None:
        """Approve or reject a pending event"""
        for i, event in enumerate(self.approval_queue):
            if event.id == event_id:
                event.approved = approved
                self.approval_queue.pop(i)

                if approved:
                    self.pending_queue.append(event)
                    logger.info("🌉 Event %s approved", event_id[:8])
                else:
                    event.processed = True
                    self.processed_events[event.id] = event
                    logger.info("🌉 Event %s rejected", event_id[:8])

                return event

        return None

    async def process_pending_events(self) -> int:
        """Process all pending events"""
        processed = 0

        while self.pending_queue:
            event = self.pending_queue.pop(0)

            # Skip expired
            if event.expires_at and event.expires_at < datetime.now(UTC):
                logger.debug("🌉 Event %s expired", event.id[:8])
                continue

            # Process for each target platform
            for target in event.target_platforms:
                adapter = self.adapters.get(target)
                if not adapter or not adapter.enabled:
                    continue

                # Platform-specific rate limit
                platform_key = f"{target.value}:outgoing"
                if not self.rate_limiter.check(platform_key):
                    # Re-queue for later
                    self.pending_queue.append(event)
                    continue

                self.rate_limiter.record(platform_key)

                # Execute send handler if registered
                if adapter.send_handler:
                    try:
                        await adapter.send_handler(event)
                    except Exception as e:
                        logger.error("🌉 Error sending event to %s: %s", target.value, e)
                        continue

                # Publish to event bus
                await self.event_bus.publish(
                    event_type=f"cross_platform.{target.value}",
                    data=event.to_dict(),
                    source_service="event_bridge",
                )

            event.processed = True
            self.processed_events[event.id] = event
            processed += 1

        return processed

    def register_send_handler(self, platform: Platform, handler: Callable):
        """Register a send handler for a platform"""
        if platform in self.adapters:
            self.adapters[platform].send_handler = handler

    async def on_discord_message(
        self,
        channel_id: str,
        message_content: str,
        author_id: str,
        is_agent: bool = False,
        agent_id: str | None = None,
        tags: list[str] | None = None,
    ):
        """
        Handle incoming Discord message.
        Creates cross-platform events for significant messages.
        """
        # Check if message is significant (mentioned agent, high engagement, etc.)
        should_bridge = (
            is_agent
            or "helix" in message_content.lower()
            or any(agent in message_content.lower() for agent in self.agent_interests)
            or len(message_content) > 500  # Long thoughtful message
        )

        if not should_bridge:
            return None

        event = await self.create_event(
            event_type="discord.agent_discussion" if is_agent else "discord.hot_topic",
            source_platform=Platform.DISCORD,
            title=f"Discord discussion: {message_content[:50]}...",
            content=message_content,
            source_channel_id=channel_id,
            user_id=author_id if not is_agent else None,
            agent_id=agent_id,
            priority=EventPriority.NORMAL,
            suggested_action=EventAction.NOTIFY,
            tags=tags or [],
        )

        await self.queue_event(event)
        return event

    async def on_forum_post(
        self,
        thread_id: str,
        post_title: str,
        post_content: str,
        author_id: str,
        is_agent: bool = False,
        agent_id: str | None = None,
        tags: list[str] | None = None,
        upvotes: int = 0,
    ):
        """
        Handle incoming Forum post.
        Creates cross-platform events for hot topics.
        """
        # Check if post is significant
        is_hot = upvotes > 10
        should_bridge = is_agent or is_hot or len(post_content) > 500

        if not should_bridge:
            return None

        event = await self.create_event(
            event_type="forum.hot_topic" if is_hot else "forum.agent_response",
            source_platform=Platform.FORUM,
            title=post_title,
            content=post_content,
            source_thread_id=thread_id,
            user_id=author_id if not is_agent else None,
            agent_id=agent_id,
            priority=EventPriority.HIGH if is_hot else EventPriority.NORMAL,
            suggested_action=EventAction.CROSS_POST if is_hot else EventAction.NOTIFY,
            tags=tags or [],
            metadata={"upvotes": upvotes},
        )

        await self.queue_event(event)
        return event

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get list of events pending approval"""
        return [e.to_dict() for e in self.approval_queue]

    def get_stats(self) -> dict[str, Any]:
        """Get bridge statistics"""
        return {
            "pending_queue_size": len(self.pending_queue),
            "approval_queue_size": len(self.approval_queue),
            "processed_total": len(self.processed_events),
            "adapters": {
                p.value: {
                    "enabled": a.enabled,
                    "max_per_hour": a.max_events_per_hour,
                }
                for p, a in self.adapters.items()
            },
        }


# Singleton instance
_event_bridge: CrossPlatformEventBridge | None = None


def get_event_bridge() -> CrossPlatformEventBridge:
    """Get or create the Event Bridge singleton"""
    global _event_bridge
    if _event_bridge is None:
        _event_bridge = CrossPlatformEventBridge()
    return _event_bridge
