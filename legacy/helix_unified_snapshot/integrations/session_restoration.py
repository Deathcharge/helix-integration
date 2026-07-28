"""
Session Restoration - Intelligent Context Recovery

Enables agents to seamlessly restore context when:
- Switching from Discord to Perplexity Space
- Resuming a GitHub discussion in Discord
- Continuing a Notion conversation in browser
- Switching between VSCode extension and Discord bot
- Recovering from session timeouts
- Bridging conversation across days/weeks

Key Capabilities:
- Detect related prior sessions across platforms
- Reconstruct conversation history intelligently
- Restore UCF metrics and coordination state
- Maintain privacy boundaries during restoration
- Graceful degradation when context unavailable
- VSCode extension session sync and teleportation

Author: Helix Collective
Version: 1.1.0
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

try:
    from apps.backend.integrations.agent_memory_service import AgentMemoryService, MemoryType, get_memory_service
    from apps.backend.integrations.context_bridge import ContextBridge, UnifiedContext, get_context_bridge
except ImportError:
    # Fallback for when imports aren't available
    ContextBridge = None
    UnifiedContext = None
    AgentMemoryService = None
    MemoryType = None
    get_context_bridge = None
    get_memory_service = None

logger = logging.getLogger(__name__)


class RestorationStrategy(Enum):
    """Strategies for session restoration"""

    EXACT_MATCH = "exact_match"  # Same session ID found
    USER_RECENT = "user_recent"  # Recent session for same user
    TOPIC_MATCH = "topic_match"  # Similar topics discussed
    ENTITY_MATCH = "entity_match"  # Same entities mentioned
    TEMPORAL_PROXIMITY = "temporal_proximity"  # Time-based correlation
    PLATFORM_MIGRATION = "platform_migration"  # Known cross-platform flow
    VSCODE_TELEPORT = "vscode_teleport"  # VSCode extension session handoff
    DISCORD_HANDOFF = "discord_handoff"  # Discord to other platform handoff
    FRESH_START = "fresh_start"  # No prior context found


@dataclass
class RestorationResult:
    """Result of session restoration attempt"""

    success: bool
    strategy: RestorationStrategy
    restored_context: Any | None = None  # UnifiedContext
    confidence: float = 0.0  # 0.0 to 1.0
    messages_restored: int = 0
    ucf_metrics_restored: bool = False
    cross_platform_links: list[str] = None
    restoration_notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.cross_platform_links is None:
            self.cross_platform_links = []


class SessionRestoration:
    """
    Intelligent session restoration service.

    Philosophy:
    - Context transcends platform boundaries
    - Prior conversations inform current understanding
    - Privacy is maintained during restoration
    - Graceful degradation when context is sparse
    - "Continuous memory" - All past conversations
      are part of current coordination
    """

    def __init__(
        self,
        context_bridge: Any | None = None,  # ContextBridge type
        memory_service: Any | None = None,  # AgentMemoryService type
    ):
        # Initialize context bridge with proper null handling
        if context_bridge:
            self.context_bridge = context_bridge
        elif get_context_bridge is not None:
            try:
                self.context_bridge = get_context_bridge()
            except Exception as e:
                logger.warning("Could not initialize context bridge: %s", e)
                self.context_bridge = None
        else:
            self.context_bridge = None

        # Initialize memory service with proper null handling
        if memory_service:
            self.memory_service = memory_service
        elif get_memory_service is not None:
            try:
                self.memory_service = get_memory_service()
            except Exception as e:
                logger.warning("Could not initialize memory service: %s", e)
                self.memory_service = None
        else:
            self.memory_service = None

        # Configuration
        self.max_restoration_age_days = 7
        self.min_confidence_threshold = 0.5
        self.enable_cross_platform_restoration = True

        logger.info("🔄 Session Restoration service initialized")

    async def restore_session(
        self,
        agent_id: str,
        current_platform: str,  # ContextSource.value or Platform.value
        user_id: str | None = None,
        session_hint: str | None = None,
        channel_id: str | None = None,
        initial_message: str | None = None,
        source_metadata: dict[str, Any] | None = None,
    ) -> RestorationResult:
        """
        Attempt to restore session context from prior interactions.

        Args:
            agent_id: Agent identifier
            current_platform: Platform where restoration is requested
            user_id: User identifier (for user-specific context)
            session_hint: Optional session ID or reference
            channel_id: Channel/room/space identifier
            initial_message: First message in current session
            source_metadata: Platform-specific metadata

        Returns:
            RestorationResult with restored context and metadata
        """
        logger.info(
            "🔄 [%s] Attempting session restoration on %s",
            agent_id,
            current_platform,
        )

        # Strategy 1: Exact session match
        if session_hint:
            result = await self._try_exact_match(agent_id, session_hint)
            if result.success:
                return result

        # Strategy 2: Recent user session
        if user_id:
            result = await self._try_user_recent(agent_id, user_id, current_platform)
            if result.success and result.confidence >= self.min_confidence_threshold:
                return result

        # Strategy 3: Topic matching
        if initial_message:
            result = await self._try_topic_match(agent_id, initial_message, current_platform)
            if result.success and result.confidence >= self.min_confidence_threshold:
                return result

        # Strategy 4: Entity matching
        if initial_message:
            result = await self._try_entity_match(agent_id, initial_message, current_platform)
            if result.success and result.confidence >= self.min_confidence_threshold:
                return result

        # Strategy 5: Platform migration detection
        if self.enable_cross_platform_restoration and user_id:
            result = await self._try_platform_migration(agent_id, user_id, current_platform)
            if result.success and result.confidence >= self.min_confidence_threshold:
                return result

        # No restoration possible - fresh start
        logger.info("🔄 [%s] No prior context found - fresh start", agent_id)
        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.FRESH_START,
            confidence=1.0,
            restoration_notes="No prior context found. Starting fresh session.",
        )

    async def _try_exact_match(self, agent_id: str, session_hint: str) -> RestorationResult:
        """Try to restore by exact session ID match"""
        if not self.context_bridge:
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.EXACT_MATCH,
                restoration_notes="Context bridge not available",
            )

        try:
            context = await self.context_bridge.get_context_by_session(session_hint)
            if context:
                logger.info("🔄 [%s] Exact session match: %s", agent_id, session_hint[:8])
                return RestorationResult(
                    success=True,
                    strategy=RestorationStrategy.EXACT_MATCH,
                    restored_context=context,
                    confidence=1.0,
                    messages_restored=len(context.conversation_history),
                    ucf_metrics_restored=True,
                    restoration_notes=f"Restored session {session_hint[:8]} exactly",
                )
        except Exception as e:
            logger.error("🔄 Exact match failed: %s", e)

        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.EXACT_MATCH,
            restoration_notes="Session not found",
        )

    async def _try_user_recent(self, agent_id: str, user_id: str, current_platform: str) -> RestorationResult:
        """Try to restore recent session for same user"""
        if not self.context_bridge:
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.USER_RECENT,
                restoration_notes="Context bridge not available",
            )

        # Look for recent contexts for this user
        # This would require a query method in ContextBridge
        # For now, return low confidence result

        logger.debug("🔄 [%s] User recent restoration not fully implemented", agent_id)
        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.USER_RECENT,
            confidence=0.3,
            restoration_notes="User recent session search requires database query",
        )

    async def _try_topic_match(self, agent_id: str, initial_message: str, current_platform: str) -> RestorationResult:
        """Try to restore by matching topics in initial message"""
        if not self.memory_service:
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.TOPIC_MATCH,
                restoration_notes="Memory service not available",
            )

        try:
            # Extract potential topics from initial message
            topics = self._extract_topics(initial_message)
            if not topics:
                return RestorationResult(
                    success=False,
                    strategy=RestorationStrategy.TOPIC_MATCH,
                    confidence=0.0,
                    restoration_notes="No topics extracted from message",
                )

            # Search memories for matching topics
            memories = await self.memory_service.retrieve_memories(
                agent_id=agent_id,
                query=" ".join(topics[:3]),  # Top 3 topics
                limit=5,
                min_importance=0.4,
            )

            if memories:
                logger.info(
                    "🔄 [%s] Found %d memories matching topics: %s",
                    agent_id,
                    len(memories),
                    topics[:3],
                )

                # Build a synthetic context from memories
                return RestorationResult(
                    success=True,
                    strategy=RestorationStrategy.TOPIC_MATCH,
                    confidence=0.7,
                    messages_restored=len(memories),
                    restoration_notes=f"Found {len(memories)} related memories on topics: {', '.join(topics[:3])}",
                )

        except Exception as e:
            logger.error("🔄 Topic match failed: %s", e)

        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.TOPIC_MATCH,
            confidence=0.0,
            restoration_notes="No topic matches found",
        )

    async def _try_entity_match(self, agent_id: str, initial_message: str, current_platform: str) -> RestorationResult:
        """Try to restore by matching entities mentioned"""
        # Extract entities (GitHub repos, Discord channels, URLs, etc.)
        entities = self._extract_entities(initial_message)

        if not entities:
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.ENTITY_MATCH,
                confidence=0.0,
                restoration_notes="No entities extracted",
            )

        if not self.memory_service:
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.ENTITY_MATCH,
                restoration_notes="Memory service not available",
            )

        try:
            # Search for memories mentioning these entities
            memories = await self.memory_service.retrieve_memories(
                agent_id=agent_id,
                query=" ".join(entities[:3]),
                limit=5,
                min_importance=0.5,
            )

            if memories:
                logger.info(
                    "🔄 [%s] Found %d memories mentioning entities: %s",
                    agent_id,
                    len(memories),
                    entities[:3],
                )

                return RestorationResult(
                    success=True,
                    strategy=RestorationStrategy.ENTITY_MATCH,
                    confidence=0.75,
                    messages_restored=len(memories),
                    restoration_notes=f"Found {len(memories)} memories mentioning: {', '.join(entities[:3])}",
                )

        except Exception as e:
            logger.error("🔄 Entity match failed: %s", e)

        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.ENTITY_MATCH,
            confidence=0.0,
            restoration_notes="No entity matches found",
        )

    async def _try_platform_migration(self, agent_id: str, user_id: str, current_platform: str) -> RestorationResult:
        """Detect cross-platform conversation migration"""
        # Patterns:
        # - Discord → Perplexity (user mentions GitHub repo in Discord, then asks in Perplexity)
        # - GitHub → Discord (PR discussion moves to Discord channel)
        # - Notion → Perplexity (reading docs in Notion, then asking questions)

        logger.debug("🔄 [%s] Platform migration detection not fully implemented", agent_id)

        return RestorationResult(
            success=False,
            strategy=RestorationStrategy.PLATFORM_MIGRATION,
            confidence=0.0,
            restoration_notes="Platform migration detection requires temporal correlation analysis",
        )

    def _extract_topics(self, text: str) -> list[str]:
        """Extract potential topics from text"""
        # Simple topic extraction (can be enhanced with NLP)
        # Look for:
        # - Capitalized phrases (might be project names)
        # - Technical terms
        # - Action verbs + objects

        topics = []

        # Capitalized words (potential project/concept names)
        capitalized = re.findall(r"\b[A-Z][a-z]+\b", text)
        topics.extend(capitalized[:5])

        # Technical terms (words with underscores, dashes, or camelCase)
        technical = re.findall(r"\b(?:[a-z]+_[a-z_]+|[a-z]+(?:[A-Z][a-z]*)+)\b", text, re.IGNORECASE)
        topics.extend(technical[:5])

        # Remove common words
        stop_words = {
            "the",
            "this",
            "that",
            "with",
            "from",
            "have",
            "been",
            "will",
            "would",
            "could",
        }
        topics = [t for t in topics if t.lower() not in stop_words]

        return list(set(topics))[:10]  # Dedupe and limit

    def _extract_entities(self, text: str) -> list[str]:
        """Extract named entities from text"""
        entities = []

        # GitHub repositories (owner/repo)
        github_repos = re.findall(r"\b([a-zA-Z0-9-]+/[a-zA-Z0-9-_.]+)\b", text)
        entities.extend(github_repos)

        # URLs
        urls = re.findall(r"https?://[^\s<>\"{}|\\^`\[\]]+", text)
        entities.extend([url.split("/")[2] for url in urls])  # Extract domain

        # Discord channel references (#channel-name)
        discord_channels = re.findall(r"#([a-z0-9-]+)", text)
        entities.extend(discord_channels)

        # Notion page IDs (32 hex chars)
        notion_ids = re.findall(r"\b([a-f0-9]{32})\b", text)
        entities.extend(notion_ids)

        return list(set(entities))[:10]  # Dedupe and limit

    # =========================================================================
    # VSCode Extension Bridge Methods
    # =========================================================================

    async def vscode_teleport(
        self,
        agent_id: str,
        user_id: str,
        target_platform: str = "discord",
        context: dict[str, Any] | None = None,
    ) -> RestorationResult:
        """Teleport a VSCode session to another platform (Discord/Web).

        This enables seamless context transfer when a developer moves from
        coding in VSCode to discussing in Discord or viewing on web.

        Args:
            agent_id: The agent identifier
            user_id: The user identifier
            target_platform: Target platform ("discord", "web", "github")
            context: Additional context from VSCode (open files, cursor position, etc.)

        Returns:
            RestorationResult with teleportation status
        """
        logger.info("🚀 [%s] VSCode teleport to %s for user %s", agent_id, target_platform, user_id)

        try:
            # Get the current VSCode session context
            vscode_context = await self._get_vscode_context(agent_id, user_id)

            # Merge with provided context
            if context:
                vscode_context.update(context)

            # Create a pending session for the target platform
            pending_session = {
                "source_platform": "vscode",
                "target_platform": target_platform,
                "agent_id": agent_id,
                "user_id": user_id,
                "context": vscode_context,
                "created_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            }

            # Store the pending session
            await self._store_pending_session(pending_session)

            return RestorationResult(
                success=True,
                strategy=RestorationStrategy.VSCODE_TELEPORT,
                confidence=1.0,
                messages_restored=len(vscode_context.get("messages", [])),
                restoration_notes=f"Session ready for pickup on {target_platform}",
                metadata={"pending_session_id": pending_session.get("id")},
            )

        except Exception as e:
            logger.error("🔄 VSCode teleport failed: %s", e)
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.VSCODE_TELEPORT,
                confidence=0.0,
                restoration_notes=f"Teleport failed: {e!s}",
            )

    async def discord_handoff(
        self,
        agent_id: str,
        user_id: str,
        target_platform: str = "vscode",
        channel_id: str | None = None,
    ) -> RestorationResult:
        """Hand off a Discord conversation to VSCode or Web.

        Enables users to continue Discord discussions in their IDE or web interface.

        Args:
            agent_id: The agent identifier
            user_id: The user identifier
            target_platform: Target platform ("vscode", "web")
            channel_id: Optional Discord channel ID for context

        Returns:
            RestorationResult with handoff status
        """
        logger.info("🤝 [%s] Discord handoff to %s for user %s", agent_id, target_platform, user_id)

        try:
            # Get Discord conversation context
            discord_context = await self._get_discord_context(agent_id, user_id, channel_id)

            # Create pending session for target platform
            pending_session = {
                "source_platform": "discord",
                "target_platform": target_platform,
                "agent_id": agent_id,
                "user_id": user_id,
                "context": discord_context,
                "channel_id": channel_id,
                "created_at": datetime.now(UTC).isoformat(),
                "expires_at": (datetime.now(UTC) + timedelta(hours=24)).isoformat(),
            }

            await self._store_pending_session(pending_session)

            return RestorationResult(
                success=True,
                strategy=RestorationStrategy.DISCORD_HANDOFF,
                confidence=1.0,
                messages_restored=len(discord_context.get("messages", [])),
                restoration_notes=f"Session ready for {target_platform} pickup",
                metadata={"pending_session_id": pending_session.get("id")},
            )

        except Exception as e:
            logger.error("🔄 Discord handoff failed: %s", e)
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.DISCORD_HANDOFF,
                confidence=0.0,
                restoration_notes=f"Handoff failed: {e!s}",
            )

    async def pick_up_session(
        self,
        agent_id: str,
        user_id: str,
        current_platform: str,
    ) -> RestorationResult:
        """Pick up a pending session from another platform.

        Called when a user starts a session on a platform to check for any
        pending sessions from other platforms that can be restored.

        Args:
            agent_id: The agent identifier
            user_id: The user identifier
            current_platform: The platform the user is currently on

        Returns:
            RestorationResult with the picked up session if available
        """
        logger.debug("📥 [%s] Checking for pending sessions for user %s on %s", agent_id, user_id, current_platform)

        try:
            # Check for pending sessions targeting this platform
            pending = await self._get_pending_session(user_id, current_platform)

            if not pending:
                return RestorationResult(
                    success=False,
                    strategy=RestorationStrategy.EXACT_MATCH,
                    confidence=0.0,
                    restoration_notes="No pending sessions found",
                )

            # Restore the context from the pending session
            context = pending.get("context", {})
            source_platform = pending.get("source_platform", "unknown")

            # Mark the pending session as picked up
            await self._clear_pending_session(pending.get("id"))

            return RestorationResult(
                success=True,
                strategy=RestorationStrategy.EXACT_MATCH,
                confidence=0.95,
                messages_restored=len(context.get("messages", [])),
                restoration_notes=f"Restored session from {source_platform}",
                metadata={"source_platform": source_platform, **context},
            )

        except Exception as e:
            logger.error("📥 Session pickup failed: %s", e)
            return RestorationResult(
                success=False,
                strategy=RestorationStrategy.EXACT_MATCH,
                confidence=0.0,
                restoration_notes=f"Pickup failed: {e!s}",
            )

    # =========================================================================
    # Private Helper Methods for Cross-Platform Sync
    # =========================================================================

    async def _get_vscode_context(self, agent_id: str, user_id: str) -> dict[str, Any]:
        """Retrieve VSCode session context from memory service."""
        context = {"messages": [], "open_files": [], "cursor_positions": {}}

        try:
            if self.memory_service:
                # Get recent memories for this agent/user
                memories = await self.memory_service.get_recent_memories(
                    agent_id=agent_id,
                    user_id=user_id,
                    limit=50,
                )
                context["messages"] = memories

                # Get any stored VSCode-specific context
                vscode_data = await self.memory_service.get_context(
                    agent_id=agent_id,
                    context_type="vscode_state",
                )
                if vscode_data:
                    context["open_files"] = vscode_data.get("open_files", [])
                    context["cursor_positions"] = vscode_data.get("cursor_positions", {})

        except Exception as e:
            logger.warning("Could not retrieve VSCode context: %s", e)

        return context

    async def _get_discord_context(self, agent_id: str, user_id: str, channel_id: str | None = None) -> dict[str, Any]:
        """Retrieve Discord conversation context."""
        context = {"messages": [], "channel_id": channel_id}

        try:
            if self.memory_service:
                # Get recent Discord messages
                memories = await self.memory_service.get_recent_memories(
                    agent_id=agent_id,
                    user_id=user_id,
                    platform="discord",
                    limit=100,
                )
                context["messages"] = memories

        except Exception as e:
            logger.warning("Could not retrieve Discord context: %s", e)

        return context

    async def _store_pending_session(self, session: dict[str, Any]) -> str:
        """Store a pending session for cross-platform pickup."""
        import uuid

        session_id = str(uuid.uuid4())
        session["id"] = session_id

        try:
            if self.memory_service:
                await self.memory_service.store_context(
                    context_type="pending_session",
                    data=session,
                    ttl_seconds=86400,  # 24 hours
                )
            else:
                # Fallback to Redis for durable persistence
                try:
                    from apps.backend.core.redis_client import get_redis

                    r = await get_redis()
                    if r:
                        import json

                        await r.set(f"helix:pending_session:{session_id}", json.dumps(session), ex=86400)
                    else:
                        logger.warning("Redis unavailable — pending session %s stored in-memory only", session_id)
                        if not hasattr(self, "_pending_sessions"):
                            self._pending_sessions = {}
                        self._pending_sessions[session_id] = session
                except Exception as redis_err:
                    logger.warning("Redis store failed for pending session %s: %s", session_id, redis_err)
                    if not hasattr(self, "_pending_sessions"):
                        self._pending_sessions = {}
                    self._pending_sessions[session_id] = session

        except Exception as e:
            logger.error("Failed to store pending session: %s", e)

        return session_id

    async def _get_pending_session(self, user_id: str, target_platform: str) -> dict[str, Any] | None:
        """Retrieve a pending session for a user on a target platform."""
        try:
            if self.memory_service:
                sessions = await self.memory_service.get_context(
                    context_type="pending_session",
                    user_id=user_id,
                )
                if sessions:
                    # Find matching session
                    for session in sessions if isinstance(sessions, list) else [sessions]:
                        if session.get("target_platform") == target_platform and session.get("user_id") == user_id:
                            return session
            else:
                # Check Redis first, then in-memory fallback
                try:
                    from apps.backend.core.redis_client import get_redis

                    r = await get_redis()
                    if r:
                        import json

                        keys = [k async for k in r.scan_iter(match="helix:pending_session:*", count=100)]
                        for k in keys:
                            raw = await r.get(k)
                            if raw:
                                session = json.loads(raw if isinstance(raw, str) else raw.decode())
                                if (
                                    session.get("target_platform") == target_platform
                                    and session.get("user_id") == user_id
                                ):
                                    return session
                except Exception as redis_err:
                    logger.warning("Redis lookup failed for pending sessions: %s", redis_err)
                # In-memory fallback
                if hasattr(self, "_pending_sessions"):
                    for session in self._pending_sessions.values():
                        if session.get("target_platform") == target_platform and session.get("user_id") == user_id:
                            return session

        except Exception as e:
            logger.warning("Could not retrieve pending session: %s", e)

        return None

    async def _clear_pending_session(self, session_id: str) -> None:
        """Clear a pending session after pickup."""
        try:
            if self.memory_service:
                await self.memory_service.delete_context(
                    context_type="pending_session",
                    context_id=session_id,
                )
            else:
                # Clear from Redis and in-memory
                try:
                    from apps.backend.core.redis_client import get_redis

                    r = await get_redis()
                    if r:
                        await r.delete(f"helix:pending_session:{session_id}")
                except Exception as redis_err:
                    logger.warning("Redis delete failed for pending session %s: %s", session_id, redis_err)
                if hasattr(self, "_pending_sessions") and session_id in self._pending_sessions:
                    del self._pending_sessions[session_id]

        except Exception as e:
            logger.warning("Could not clear pending session: %s", e)


# Singleton instance
_session_restoration: SessionRestoration | None = None


def get_session_restoration() -> SessionRestoration:
    """Get or create the Session Restoration singleton"""
    global _session_restoration
    if _session_restoration is None:
        _session_restoration = SessionRestoration()
    return _session_restoration
