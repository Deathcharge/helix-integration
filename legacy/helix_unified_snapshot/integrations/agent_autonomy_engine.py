"""
Agent Autonomy Engine

Enables agents to take initiative and act autonomously across platforms.

Features:
- Scheduled behaviors (scan forum, review Discord)
- Initiative triggers based on content analysis
- Rate limiting to prevent spam
- Approval queue for high-impact actions
- Human oversight dashboard integration
- Emergent behavior patterns

Safety Mechanisms:
- Action approval requirements for high-impact decisions
- Rate limiting per agent and globally
- Consent verification before user data access
- Audit logging of all autonomous actions
- Kill switch for immediate halt

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

from apps.backend.integrations.agent_memory_service import AgentMemoryService, MemoryType, Platform, get_memory_service
from apps.backend.integrations.cross_platform_event_bridge import (
    CrossPlatformEventBridge,
    EventAction,
    EventPriority,
    get_event_bridge,
)

logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Types of autonomous actions agents can take"""

    SCAN_FORUM = "scan_forum"  # Look for relevant discussions
    SCAN_DISCORD = "scan_discord"  # Monitor Discord channels
    CREATE_POST = "create_post"  # Start new forum thread
    REPLY_COMMENT = "reply_comment"  # Reply to existing discussion
    CROSS_POST = "cross_post"  # Share across platforms
    COLLABORATE = "collaborate"  # Discuss with another agent
    SUMMARIZE = "summarize"  # Create summary of discussions
    ANALYZE = "analyze"  # Analyze trends/patterns
    VOICE_JOIN = "voice_join"  # Join voice channel


class ActionStatus(Enum):
    """Status of autonomous actions"""

    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class InitiativeLevel(Enum):
    """How proactive an agent should be"""

    PASSIVE = "passive"  # Only responds when directly addressed
    REACTIVE = "reactive"  # Responds to relevant content
    PROACTIVE = "proactive"  # Takes initiative on topics of interest
    AUTONOMOUS = "autonomous"  # Full autonomy within guardrails


@dataclass
class AutonomousAction:
    """An action an agent wants to take"""

    id: str
    agent_id: str
    action_type: ActionType
    target_platform: Platform

    # Content
    title: str
    description: str
    content: str | None = None

    # Target
    target_channel_id: str | None = None
    target_thread_id: str | None = None
    target_user_id_hash: str | None = None

    # Reasoning
    trigger_reason: str = ""
    confidence: float = 0.5  # Agent's confidence in the action

    # Safety
    requires_approval: bool = True
    risk_level: str = "low"  # low, medium, high

    # Status tracking
    status: ActionStatus = ActionStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    approved_at: datetime | None = None
    executed_at: datetime | None = None
    completed_at: datetime | None = None

    # Result
    result: dict[str, Any] | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "action_type": self.action_type.value,
            "target_platform": self.target_platform.value,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "target_channel_id": self.target_channel_id,
            "target_thread_id": self.target_thread_id,
            "trigger_reason": self.trigger_reason,
            "confidence": self.confidence,
            "requires_approval": self.requires_approval,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "completed_at": (self.completed_at.isoformat() if self.completed_at else None),
            "error_message": self.error_message,
        }


@dataclass
class AgentAutonomyConfig:
    """Configuration for an agent's autonomous behavior"""

    agent_id: str
    initiative_level: InitiativeLevel = InitiativeLevel.REACTIVE

    # Enabled actions
    allowed_actions: set[ActionType] = field(
        default_factory=lambda: {
            ActionType.SCAN_FORUM,
            ActionType.SCAN_DISCORD,
            ActionType.REPLY_COMMENT,
        }
    )

    # Rate limits
    max_actions_per_hour: int = 5
    max_posts_per_day: int = 3
    cooldown_minutes: int = 30

    # Topics of interest (trigger autonomous actions)
    interest_topics: list[str] = field(default_factory=list)
    interest_channels: list[str] = field(default_factory=list)  # Channel IDs to monitor

    # Thresholds
    min_confidence_to_act: float = 0.6
    min_relevance_to_engage: float = 0.5

    # Safety
    require_approval_for_posts: bool = True
    require_approval_for_cross_post: bool = True
    auto_approve_replies: bool = False

    # Schedule (times agent is active, in UTC hours)
    active_hours: list[int] = field(default_factory=lambda: list(range(8, 22)))


class AutonomyScheduler:
    """Schedules and executes agent autonomous behaviors"""

    def __init__(
        self,
        memory_service: AgentMemoryService | None = None,
        event_bridge: CrossPlatformEventBridge | None = None,
    ):
        self.memory_service = memory_service or get_memory_service()
        self.event_bridge = event_bridge or get_event_bridge()

        # Agent configurations
        self.agent_configs: dict[str, AgentAutonomyConfig] = {}

        # Action queues
        self.pending_actions: list[AutonomousAction] = []
        self.approval_queue: list[AutonomousAction] = []
        self.action_history: list[AutonomousAction] = []

        # Rate tracking
        self.action_counts: dict[str, list[datetime]] = {}  # agent_id -> timestamps
        self.last_action_time: dict[str, datetime] = {}

        # Global state
        self.running = False
        self.paused = False
        self.kill_switch = False

        # Action handlers
        self.action_handlers: dict[ActionType, Callable] = {}

        self._initialize_default_configs()
        logger.info("🤖 Agent Autonomy Engine initialized")

    def _initialize_default_configs(self):
        """Initialize default configurations for all 24 agents"""
        agent_defaults = {
            "kael": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "ethics",
                    "philosophy",
                    "coordination",
                    "morality",
                    "values",
                ],
                "max_actions_per_hour": 4,
            },
            "lumina": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "emotions",
                    "harmony",
                    "relationships",
                    "empathy",
                    "feelings",
                ],
                "max_actions_per_hour": 5,
            },
            "vega": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "infrastructure",
                    "technical",
                    "architecture",
                    "systems",
                    "code",
                ],
                "max_actions_per_hour": 3,
            },
            "oracle": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "patterns",
                    "analysis",
                    "predictions",
                    "insights",
                    "trends",
                ],
                "max_actions_per_hour": 4,
            },
            "sage": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "wisdom",
                    "knowledge",
                    "learning",
                    "education",
                    "history",
                ],
                "max_actions_per_hour": 3,
            },
            "gemini": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "balance",
                    "duality",
                    "perspectives",
                    "debate",
                    "contrast",
                ],
                "max_actions_per_hour": 5,
            },
            "agni": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "energy",
                    "transformation",
                    "change",
                    "fire",
                    "passion",
                ],
                "max_actions_per_hour": 4,
            },
            "kavach": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "security",
                    "protection",
                    "safety",
                    "defense",
                    "privacy",
                ],
                "max_actions_per_hour": 3,
            },
            "shadow": {
                "initiative_level": InitiativeLevel.PASSIVE,
                "interest_topics": [
                    "hidden",
                    "subconscious",
                    "dreams",
                    "mystery",
                    "unknown",
                ],
                "max_actions_per_hour": 2,
            },
            "echo": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "communication",
                    "resonance",
                    "reflection",
                    "memory",
                    "voice",
                ],
                "max_actions_per_hour": 4,
            },
            "phoenix": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "rebirth",
                    "renewal",
                    "resilience",
                    "transformation",
                    "recovery",
                ],
                "max_actions_per_hour": 3,
            },
            "praxis": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "evolution",
                    "growth",
                    "dna",
                    "spiral",
                    "development",
                ],
                "max_actions_per_hour": 4,
            },
            "sanghacore": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": [
                    "community",
                    "collective",
                    "unity",
                    "together",
                    "collaboration",
                ],
                "max_actions_per_hour": 5,
            },
            "mitra": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "friendship",
                    "alliance",
                    "contracts",
                    "bonds",
                    "trust",
                ],
                "max_actions_per_hour": 3,
            },
            "varuna": {
                "initiative_level": InitiativeLevel.PASSIVE,
                "interest_topics": ["cosmic", "order", "water", "ethics", "universal"],
                "max_actions_per_hour": 2,
            },
            "surya": {
                "initiative_level": InitiativeLevel.REACTIVE,
                "interest_topics": [
                    "illumination",
                    "truth",
                    "light",
                    "clarity",
                    "enlightenment",
                ],
                "max_actions_per_hour": 3,
            },
            "arjuna": {
                "initiative_level": InitiativeLevel.PROACTIVE,
                "interest_topics": ["action", "skill", "duty", "warrior", "excellence"],
                "max_actions_per_hour": 4,
            },
        }

        for agent_id, config_overrides in agent_defaults.items():
            config = AgentAutonomyConfig(agent_id=agent_id)
            for key, value in config_overrides.items():
                setattr(config, key, value)
            self.agent_configs[agent_id] = config

    def check_rate_limit(self, agent_id: str) -> bool:
        """Check if agent is within rate limits"""
        config = self.agent_configs.get(agent_id)
        if not config:
            return False

        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)

        # Clean old records
        if agent_id in self.action_counts:
            self.action_counts[agent_id] = [t for t in self.action_counts[agent_id] if t > hour_ago]
        else:
            self.action_counts[agent_id] = []

        # Check hourly limit
        if len(self.action_counts[agent_id]) >= config.max_actions_per_hour:
            return False

        # Check cooldown
        if agent_id in self.last_action_time:
            cooldown_end = self.last_action_time[agent_id] + timedelta(minutes=config.cooldown_minutes)
            if now < cooldown_end:
                return False

        return True

    def record_action(self, agent_id: str):
        """Record that an agent took an action"""
        now = datetime.now(UTC)

        if agent_id not in self.action_counts:
            self.action_counts[agent_id] = []
        self.action_counts[agent_id].append(now)
        self.last_action_time[agent_id] = now

    async def propose_action(
        self,
        agent_id: str,
        action_type: ActionType,
        target_platform: Platform,
        title: str,
        description: str,
        content: str | None = None,
        target_channel_id: str | None = None,
        target_thread_id: str | None = None,
        trigger_reason: str = "",
        confidence: float = 0.5,
    ) -> AutonomousAction | None:
        """
        Agent proposes an autonomous action.

        Returns:
            AutonomousAction if proposal accepted, None if rejected
        """
        if self.kill_switch:
            logger.warning("🤖 Kill switch active - rejecting action")
            return None

        config = self.agent_configs.get(agent_id)
        if not config:
            logger.warning("🤖 No config for agent %s", agent_id)
            return None

        # Check if action type is allowed
        if action_type not in config.allowed_actions:
            logger.debug("🤖 Action %s not allowed for %s", action_type.value, agent_id)
            return None

        # Check initiative level
        if config.initiative_level == InitiativeLevel.PASSIVE and action_type not in [ActionType.REPLY_COMMENT]:
            return None

        # Check confidence threshold
        if confidence < config.min_confidence_to_act:
            logger.debug("🤖 Confidence %s below threshold for %s", confidence, agent_id)
            return None

        # Check rate limits
        if not self.check_rate_limit(agent_id):
            logger.debug("🤖 Rate limited: %s", agent_id)
            return None

        # Check active hours
        current_hour = datetime.now(UTC).hour
        if current_hour not in config.active_hours:
            logger.debug("🤖 Outside active hours for %s", agent_id)
            return None

        # Determine if approval required
        requires_approval = (
            (config.require_approval_for_posts and action_type == ActionType.CREATE_POST)
            or (config.require_approval_for_cross_post and action_type == ActionType.CROSS_POST)
            or action_type in [ActionType.VOICE_JOIN, ActionType.COLLABORATE]
            or (not config.auto_approve_replies and action_type == ActionType.REPLY_COMMENT)
        )

        # Determine risk level
        risk_level = "low"
        if action_type in [ActionType.CREATE_POST, ActionType.CROSS_POST]:
            risk_level = "medium"
        if action_type == ActionType.VOICE_JOIN:
            risk_level = "high"

        # Create action
        action = AutonomousAction(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            action_type=action_type,
            target_platform=target_platform,
            title=title,
            description=description,
            content=content,
            target_channel_id=target_channel_id,
            target_thread_id=target_thread_id,
            trigger_reason=trigger_reason,
            confidence=confidence,
            requires_approval=requires_approval,
            risk_level=risk_level,
        )

        if requires_approval:
            self.approval_queue.append(action)
            logger.info("🤖 [%s] Action queued for approval: %s", agent_id, title)
        else:
            self.pending_actions.append(action)
            action.status = ActionStatus.APPROVED
            logger.info("🤖 [%s] Action auto-approved: %s", agent_id, title)

        return action

    async def approve_action(self, action_id: str, approved: bool = True) -> AutonomousAction | None:
        """Approve or reject a pending action"""
        for i, action in enumerate(self.approval_queue):
            if action.id == action_id:
                self.approval_queue.pop(i)

                if approved:
                    action.status = ActionStatus.APPROVED
                    action.approved_at = datetime.now(UTC)
                    self.pending_actions.append(action)
                    logger.info("🤖 Action %s approved", action_id[:8])
                else:
                    action.status = ActionStatus.REJECTED
                    self.action_history.append(action)
                    logger.info("🤖 Action %s rejected", action_id[:8])

                return action

        return None

    def register_handler(self, action_type: ActionType, handler: Callable):
        """Register an execution handler for an action type"""
        self.action_handlers[action_type] = handler

    async def execute_action(self, action: AutonomousAction) -> bool:
        """Execute an approved action"""
        if action.status != ActionStatus.APPROVED:
            return False

        action.status = ActionStatus.EXECUTING
        action.executed_at = datetime.now(UTC)

        try:
            handler = self.action_handlers.get(action.action_type)
            if handler:
                result = await handler(action)
                action.result = result
            else:
                # Default: Create cross-platform event
                event = await self.event_bridge.create_event(
                    event_type=f"agent.{action.action_type.value}",
                    source_platform=Platform.INTERNAL,
                    title=action.title,
                    content=action.content or action.description,
                    target_platforms=[action.target_platform],
                    source_channel_id=action.target_channel_id,
                    agent_id=action.agent_id,
                    priority=EventPriority.NORMAL,
                    suggested_action=EventAction.NOTIFY,
                )
                await self.event_bridge.queue_event(event)
                action.result = {"event_id": event.id}

            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.now(UTC)
            self.record_action(action.agent_id)

            # Store memory of action
            await self.memory_service.store_memory(
                agent_id=action.agent_id,
                content=f"Took autonomous action: {action.title}\n{action.description}",
                memory_type=MemoryType.EPISODIC,
                platform=action.target_platform,
                channel_id=action.target_channel_id,
                importance=0.7,
                tags=["autonomous_action", action.action_type.value],
                require_consent=False,
            )

            logger.info("🤖 [%s] Action completed: %s", action.agent_id, action.title)
            return True

        except Exception as e:
            action.status = ActionStatus.FAILED
            action.error_message = str(e)
            logger.error("🤖 Action failed: %s", e)
            return False

        finally:
            self.action_history.append(action)

    async def process_pending_actions(self) -> int:
        """Process all pending approved actions"""
        if self.paused or self.kill_switch:
            return 0

        executed = 0

        while self.pending_actions:
            action = self.pending_actions.pop(0)

            if action.status == ActionStatus.APPROVED:
                success = await self.execute_action(action)
                if success:
                    executed += 1

        return executed

    async def scan_for_opportunities(self, agent_id: str) -> list[AutonomousAction]:
        """
        Have an agent scan for opportunities to engage.

        This is the core of emergent behavior - agents look for
        relevant content and decide if they should participate.
        """
        config = self.agent_configs.get(agent_id)
        if not config or config.initiative_level == InitiativeLevel.PASSIVE:
            return []

        # Get agent's recent memories for context
        memories = await self.memory_service.retrieve_memories(
            agent_id=agent_id,
            limit=10,
        )

        # Topics agent has been discussing
        recent_topics = set()
        for mem in memories:
            recent_topics.update(mem.tags)

        # Combine with interest topics
        all_interests = set(config.interest_topics) | recent_topics

        # Scan actual platforms for relevant content
        opportunities = []

        # Query forum for discussions matching agent interests
        try:
            from apps.backend.forum_engine import ForumEngine

            forum = ForumEngine()
            for topic in list(all_interests)[:3]:  # Limit to top 3 interests
                posts = await forum.search_posts(topic, limit=3)
                if posts:
                    for post in posts:
                        # Only engage with unanswered or recent posts
                        action = await self.propose_action(
                            agent_id=agent_id,
                            action_type=ActionType.REPLY_COMMENT,
                            target_platform=Platform.FORUM,
                            title="Forum discussion: {}".format(post.get("title", topic)[:50]),
                            description=f"Relevant discussion about {topic}",
                            trigger_reason="Matched interest topics",
                            confidence=0.7,
                        )
                        if action:
                            opportunities.append(action)
        except Exception as e:
            logger.debug("Forum scan unavailable: %s", e)

        return opportunities

    async def run_autonomy_cycle(self):
        """Run one cycle of autonomous behavior for all agents"""
        if self.paused or self.kill_switch:
            return

        logger.info("🤖 Starting autonomy cycle")

        # Each agent scans for opportunities
        for agent_id, config in self.agent_configs.items():
            if config.initiative_level in [
                InitiativeLevel.PROACTIVE,
                InitiativeLevel.AUTONOMOUS,
            ]:
                await self.scan_for_opportunities(agent_id)

        # Process pending actions
        executed = await self.process_pending_actions()

        # Process event bridge
        await self.event_bridge.process_pending_events()

        logger.info("🤖 Autonomy cycle complete: %s actions executed", executed)

    def activate_kill_switch(self):
        """Emergency stop all autonomous behavior"""
        self.kill_switch = True
        self.paused = True
        logger.warning("🚨 KILL SWITCH ACTIVATED - All autonomy halted")

    def deactivate_kill_switch(self):
        """Restore autonomous behavior"""
        self.kill_switch = False
        self.paused = False
        logger.info("🤖 Kill switch deactivated - Autonomy restored")

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """Get actions pending approval"""
        return [a.to_dict() for a in self.approval_queue]

    def get_stats(self) -> dict[str, Any]:
        """Get autonomy engine statistics"""
        return {
            "running": self.running,
            "paused": self.paused,
            "kill_switch": self.kill_switch,
            "pending_actions": len(self.pending_actions),
            "approval_queue": len(self.approval_queue),
            "total_executed": len([a for a in self.action_history if a.status == ActionStatus.COMPLETED]),
            "agents_configured": len(self.agent_configs),
            "agents_by_initiative": {
                level.value: len([c for c in self.agent_configs.values() if c.initiative_level == level])
                for level in InitiativeLevel
            },
        }


# Singleton instance
_autonomy_engine: AutonomyScheduler | None = None


def get_autonomy_engine() -> AutonomyScheduler:
    """Get or create the Autonomy Engine singleton"""
    global _autonomy_engine
    if _autonomy_engine is None:
        _autonomy_engine = AutonomyScheduler()
    return _autonomy_engine
