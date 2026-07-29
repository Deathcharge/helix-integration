"""
🌀 Unified Platform Bridge
===========================

The single integration layer that connects all platform adapters
(Discord, Forum, VS Code, GitHub, Mobile, MCP, Reddit) to the
shared agent core: identity, memory, orchestration, and events.

This module is the "glue" — it doesn't reimplement anything.
It imports from existing modules and wires them together so that
every platform routes through the same agent brain.

Platforms should call:
    bridge = get_platform_bridge()
    response = await bridge.agent_message(
        platform=Platform.DISCORD,
        agent_id="agent-kael",
        user_message="Hello Kael",
        user_id="user123",
        channel_id="discord-channel-456",
    )

The bridge will:
1. Resolve agent identity via unified_agent_identity
2. Store the interaction in agent_memory_service
3. Route through the agent orchestrator
4. Emit cross-platform events via event_bridge
5. Return a platform-formatted response

Author: Helix Collective
Version: 1.0.0
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from apps.backend.common import Platform

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lazy imports to avoid circular dependencies at module load time
# ---------------------------------------------------------------------------


def _get_identity_registry():
    """Get the unified agent identity registry (lazy)."""
    from apps.backend.integrations.unified_agent_identity import HELIX_AGENTS, UnifiedAgentService

    return UnifiedAgentService, HELIX_AGENTS


def _get_memory_service():
    """Get the cross-platform memory service singleton (lazy)."""
    from apps.backend.integrations.agent_memory_service import AgentMemory, MemoryType, get_memory_service

    return get_memory_service(), AgentMemory, MemoryType


def _get_event_bridge():
    """Get the cross-platform event bridge singleton (lazy)."""
    try:
        from apps.backend.integrations.cross_platform_event_bridge import (
            CrossPlatformEvent,
            EventAction,
            EventPriority,
            get_event_bridge,
        )

        return get_event_bridge(), CrossPlatformEvent, EventPriority, EventAction
    except (ImportError, AttributeError) as e:
        logger.debug("Cross-platform event bridge not available: %s", e)
        return None, None, None, None


def _get_orchestrator():
    """Get the agent orchestrator singleton (lazy)."""
    try:
        from apps.backend.agents.agent_orchestrator import get_orchestrator

        return get_orchestrator()
    except (ImportError, AttributeError) as e:
        logger.debug("Orchestrator import error: %s", e)
        logger.warning("Agent orchestrator not available, using direct agent calls")
        return None


class PlatformBridge:
    """
    Unified bridge connecting all platforms to the shared agent core.

    This is the ONLY entry point platforms should use for agent interactions.
    It ensures every interaction goes through:
    - Unified identity resolution
    - Cross-platform memory persistence
    - Shared orchestration logic
    - Event propagation to other platforms
    """

    def __init__(self):
        self._initialized = False

    def _ensure_init(self):
        """Lazy initialization to avoid import-time failures."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("🌀 Platform Bridge initialized — all platforms unified")

    # ------------------------------------------------------------------
    # Core: Send a message to an agent from any platform
    # ------------------------------------------------------------------

    async def agent_message(
        self,
        platform: Platform,
        agent_id: str,
        user_message: str,
        user_id: str,
        channel_id: str | None = None,
        thread_id: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Send a user message to an agent, with full cross-platform context.

        This is the primary method all platforms should call.
        """
        self._ensure_init()

        # 1. Resolve agent identity
        identity = self.get_agent_identity(agent_id)
        if not identity:
            return {
                "error": "Agent not found",
                "agent_id": agent_id,
                "content": "I'm sorry, that agent is not available.",
            }

        # 2. Retrieve relevant memories for context
        memories = await self.recall_memories(
            agent_id=agent_id,
            user_id=user_id,
            platform=platform,
            limit=5,
        )

        # 3. Build context-enriched prompt
        memory_context = ""
        if memories:
            memory_snippets = [m.get("summary", m.get("content", ""))[:200] for m in memories]
            memory_context = "\n\n[Cross-platform memory — you remember these interactions]:\n" + "\n".join(
                f"- {s}" for s in memory_snippets
            )

        # 4. Route through orchestrator (or fallback to direct)
        orchestrator = _get_orchestrator()
        if orchestrator and hasattr(orchestrator, "process_message"):
            try:
                response = await orchestrator.process_message(
                    agent_id=agent_id,
                    message=user_message + memory_context,
                    user_id=user_id,
                    platform=platform.value,
                    metadata=metadata or {},
                )
                response_content = response if isinstance(response, str) else response.get("content", str(response))
            except Exception as e:
                logger.warning("Orchestrator failed, using fallback: %s", e)
                response_content = await self._fallback_agent_response(agent_id, user_message, identity)
        else:
            response_content = await self._fallback_agent_response(agent_id, user_message, identity)

        # 5. Store this interaction as a memory
        await self.store_memory(
            agent_id=agent_id,
            user_id=user_id,
            platform=platform,
            content=f"User: {user_message}\nAgent: {response_content[:500]}",
            summary=f"Conversation on {platform.value} about: {user_message[:100]}",
            channel_id=channel_id,
            thread_id=thread_id,
        )

        # 6. Emit cross-platform event (non-blocking)
        await self._emit_event(
            platform=platform,
            agent_id=agent_id,
            event_type=f"{platform.value}.agent_response",
            title=f"{identity.get('codename', agent_id)} responded on {platform.value}",
            content=user_message[:200],
        )

        # 7. Format response for the requesting platform
        formatted = self.format_for_platform(
            content=response_content,
            agent_id=agent_id,
            platform=platform,
        )

        return {
            "content": formatted,
            "agent_id": agent_id,
            "agent_name": identity.get("codename", agent_id),
            "agent_symbol": identity.get("symbol", "🌀"),
            "platform": platform.value,
            "memories_used": len(memories),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    def get_agent_identity(self, agent_id: str) -> dict[str, Any] | None:
        """
        Get agent identity from the unified registry.
        Accepts both 'agent-kael' and 'kael' formats.
        Returns dict with codename, symbol, role, traits, etc.
        """
        try:
            service, _agents = _get_identity_registry()
            # Try codename directly (e.g., 'kael')
            codename = agent_id.replace("agent-", "").lower()
            identity = service.get_agent(codename)
            if identity:
                return identity.to_dict()
        except Exception as e:
            logger.warning("Identity lookup failed for %s: %s", agent_id, e)

        # Fallback: try agents_service AGENTS dict
        try:
            from apps.backend.agents.agents_service import AGENTS

            agent = AGENTS.get(agent_id.replace("agent-", "").capitalize())
            if agent:
                return {
                    "id": agent_id,
                    "codename": agent.name,
                    "symbol": getattr(agent, "symbol", "🌀"),
                    "role": getattr(agent, "role", "Agent"),
                    "bio": getattr(agent, "description", ""),
                }
        except Exception as e:
            logger.debug("Agent identity lookup failed for %s: %s", agent_id, e)

        return None

    def get_all_agents(self) -> list[dict[str, Any]]:
        """Get all agent identities."""
        try:
            service, _ = _get_identity_registry()
            agents = service.get_all_agents()
            return [a.to_dict() for a in agents]
        except Exception as e:
            logger.warning("Failed to get all agents: %s", e)
            return []

    # ------------------------------------------------------------------
    # Memory operations
    # ------------------------------------------------------------------

    async def store_memory(
        self,
        agent_id: str,
        user_id: str,
        platform: Platform,
        content: str,
        summary: str,
        channel_id: str | None = None,
        thread_id: str | None = None,
        memory_type: str = "episodic",
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> str | None:
        """Store a memory in the cross-platform memory service."""
        try:
            service, AgentMemory, MemoryType = _get_memory_service()
            memory = AgentMemory(
                id=str(uuid.uuid4()),
                agent_id=agent_id,
                memory_type=MemoryType(memory_type),
                content=content,
                summary=summary,
                source_platform=platform,
                source_channel_id=channel_id,
                source_thread_id=thread_id,
                user_id_hash=self._hash_user_id(user_id),
                importance=importance,
                tags=tags or [platform.value],
            )
            await service.store_memory(memory)
            return memory.id
        except Exception as e:
            logger.debug("Memory storage skipped: %s", e)
            return None

    async def recall_memories(
        self,
        agent_id: str,
        user_id: str | None = None,
        platform: Platform | None = None,
        limit: int = 10,
        memory_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Recall memories, optionally filtered by platform/user."""
        try:
            service, _, MemoryType = _get_memory_service()
            mt = MemoryType(memory_type) if memory_type else None
            memories = await service.recall_memories(
                agent_id=agent_id,
                user_id_hash=self._hash_user_id(user_id) if user_id else None,
                platform=platform,
                memory_type=mt,
                limit=limit,
            )
            return [m.to_dict() if hasattr(m, "to_dict") else m for m in memories]
        except Exception as e:
            logger.debug("Memory recall skipped: %s", e)
            return []

    # ------------------------------------------------------------------
    # Cross-platform event emission
    # ------------------------------------------------------------------

    async def _emit_event(
        self,
        platform: Platform,
        agent_id: str,
        event_type: str,
        title: str,
        content: str,
    ):
        """Emit a cross-platform event (fire-and-forget)."""
        try:
            bridge, CrossPlatformEvent, EventPriority, EventAction = _get_event_bridge()
            if bridge is None:
                return

            # Determine which platforms should be notified
            all_platforms = [
                Platform.DISCORD,
                Platform.FORUM,
                Platform.BROWSER_CHAT,
            ]
            target_platforms = [p for p in all_platforms if p != platform]

            event = CrossPlatformEvent(
                id=str(uuid.uuid4()),
                event_type=event_type,
                source_platform=platform,
                target_platforms=target_platforms,
                title=title,
                content=content,
                agent_id=agent_id,
                priority=EventPriority.LOW,
                suggested_action=EventAction.NOTIFY,
            )
            await bridge.process_event(event)
        except Exception as e:
            # Events are non-critical — never block on failure
            logger.debug("Event emission skipped: %s", e)

    # ------------------------------------------------------------------
    # Platform-specific formatting
    # ------------------------------------------------------------------

    def format_for_platform(
        self,
        content: str,
        agent_id: str,
        platform: Platform,
    ) -> str:
        """Format agent response for the target platform."""
        identity = self.get_agent_identity(agent_id)
        if not identity:
            return content

        codename = identity.get("codename", "Agent")
        symbol = identity.get("symbol", "🌀")

        if platform in (Platform.FORUM, Platform.REDDIT):
            # Add signature for forum/reddit posts
            return f"{content}\n\n*— {codename} {symbol} | Helix Collective*"
        elif platform == Platform.DISCORD:
            # Discord uses embeds elsewhere; keep content clean
            return content
        elif platform == Platform.GITHUB:
            # GitHub markdown with attribution
            return f"{content}\n\n---\n*{symbol} {codename} — Helix Collective*"
        else:
            return content

    # ------------------------------------------------------------------
    # Platform registration for event routing
    # ------------------------------------------------------------------

    async def register_platform_handler(
        self,
        platform: Platform,
        send_handler,
        format_handler=None,
    ):
        """
        Register a platform's send/format handlers with the event bridge.
        Called during platform startup (e.g., Discord bot on_ready).
        """
        try:
            bridge, _, _, _ = _get_event_bridge()
            if bridge and hasattr(bridge, "register_adapter"):
                await bridge.register_adapter(
                    platform=platform,
                    send_handler=send_handler,
                    format_handler=format_handler,
                )
                logger.info("🌀 Platform %s registered with event bridge", platform.value)
        except Exception as e:
            logger.debug("Platform handler registration skipped: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hash_user_id(user_id: str) -> str:
        """Hash user ID for privacy-aware memory storage."""
        import hashlib

        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    async def _fallback_agent_response(
        self,
        agent_id: str,
        message: str,
        identity: dict[str, Any],
    ) -> str:
        """
        Fallback when the orchestrator is unavailable.

        Returns a brief acknowledgement so the user knows the message was
        received but full multi-agent orchestration is not online.
        """
        codename = identity.get("codename", "Agent")
        return (
            f"*{codename} acknowledges your message.* "
            "The multi-agent orchestration service is currently unavailable. "
            "Please try again shortly or contact support if this persists."
        )

    # ------------------------------------------------------------------
    # Health check
    # ------------------------------------------------------------------

    def health(self) -> dict[str, Any]:
        """Return health status of all subsystems."""
        status = {
            "bridge": "healthy",
            "identity_registry": "unknown",
            "memory_service": "unknown",
            "event_bridge": "unknown",
            "orchestrator": "unknown",
        }

        try:
            _, _, agents = _get_identity_registry()
            status["identity_registry"] = "healthy"
            status["agents_count"] = len(agents)
        except (TypeError, AttributeError) as e:
            logger.debug("Agent count error: %s", e)
            status["identity_registry"] = "unavailable"
        except Exception:
            status["identity_registry"] = "unavailable"

        try:
            service, _, _ = _get_memory_service()
            status["memory_service"] = "healthy" if service else "unavailable"
        except (TypeError, AttributeError) as e:
            logger.debug("Memory service health error: %s", e)
            status["memory_service"] = "unavailable"
        except Exception:
            status["memory_service"] = "unavailable"

        try:
            bridge, _, _, _ = _get_event_bridge()
            status["event_bridge"] = "healthy" if bridge else "unavailable"
        except (TypeError, AttributeError) as e:
            logger.debug("Event bridge health error: %s", e)
            status["event_bridge"] = "unavailable"
        except Exception:
            status["event_bridge"] = "unavailable"

        try:
            orch = _get_orchestrator()
            status["orchestrator"] = "healthy" if orch else "unavailable"
        except (TypeError, AttributeError) as e:
            logger.debug("Orchestrator health error: %s", e)
            status["orchestrator"] = "unavailable"
        except Exception:
            status["orchestrator"] = "unavailable"

        return status


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

_platform_bridge: PlatformBridge | None = None


def get_platform_bridge() -> PlatformBridge:
    """Get the singleton PlatformBridge instance."""
    global _platform_bridge
    if _platform_bridge is None:
        _platform_bridge = PlatformBridge()
    return _platform_bridge
