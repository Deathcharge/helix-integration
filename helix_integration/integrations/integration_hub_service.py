"""
Integration Hub Service

Main service that orchestrates all platform integrations (Discord, Reddit, Forums)
with the learning system and all 24 agents. This is the single service that
runs on Railway and handles all multi-platform agent interactions.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from typing import Any

from learning import get_learning_system

from .ai_forum_integration import AIForumIntegration

# Agent expansion
from .all_agents_expansion import AgentOrchestrator, AgentRegistry, get_agent_orchestrator, get_agent_registry
from .cross_platform_agent_coordinator import CrossPlatformAgentCoordinator

# Platform integrations
from .discord_agent_to_agent import DiscordAgentInteraction

# Learning system
from .learning_integration import LearningIntegrationManager
from .reddit_integration import RedditIntegration

logger = logging.getLogger(__name__)

_background_tasks: set[asyncio.Task[Any]] = set()


class IntegrationHubService:
    """
    Main integration hub service.

    This service:
    1. Initializes all platform integrations (Discord, Reddit, Forums)
    2. Connects learning system to all interactions
    3. Orchestrates agent participation across platforms
    4. Enables cross-platform continuity and knowledge sharing
    5. Provides unified API for the integration hub
    """

    def __init__(self):
        self.is_running = False

        # Platform integrations
        self.discord: DiscordAgentInteraction | None = None
        self.reddit: RedditIntegration | None = None
        self.forum: AIForumIntegration | None = None
        self.coordinator: CrossPlatformAgentCoordinator | None = None

        # Learning integration
        self.learning_manager: LearningIntegrationManager | None = None

        # Agent orchestration
        self.agent_registry: AgentRegistry | None = None
        self.agent_orchestrator: AgentOrchestrator | None = None

        # Task references
        self.tasks: list[asyncio.Task] = []

        logger.info("IntegrationHubService initialized")

    async def initialize(self):
        """Initialize all components of the integration hub"""
        logger.info("Initializing Integration Hub Service...")

        # Initialize learning system
        get_learning_system()
        logger.info("Learning system initialized")

        # Initialize agent registry and orchestrator
        self.agent_registry = get_agent_registry()
        self.agent_orchestrator = get_agent_orchestrator()
        logger.info("Agent registry initialized with %s agents", len(self.agent_registry.agents))

        # Initialize Discord integration
        if os.getenv("DISCORD_BOT_TOKEN"):
            self.discord = DiscordAgentInteraction()
            await self.discord.initialize()
            logger.info("Discord integration initialized")
        else:
            logger.warning("Discord bot token not configured, Discord integration disabled")

        # Initialize Reddit integration
        if os.getenv("REDDIT_CLIENT_ID"):
            self.reddit = RedditIntegration()
            await self.reddit.initialize()
            logger.info("Reddit integration initialized")
        else:
            logger.warning("Reddit credentials not configured, Reddit integration disabled")

        # Initialize Forum integration
        if os.getenv("AI_FORUM_API_KEY"):
            self.forum = AIForumIntegration()
            await self.forum.initialize()
            logger.info("Forum integration initialized")
        else:
            logger.warning("Forum API key not configured, Forum integration disabled")

        # Initialize cross-platform coordinator
        self.coordinator = CrossPlatformAgentCoordinator(discord=self.discord, reddit=self.reddit, forum=self.forum)
        logger.info("Cross-platform coordinator initialized")

        # Initialize learning integration manager
        self.learning_manager = LearningIntegrationManager(
            discord_integration=self.discord,
            reddit_integration=self.reddit,
            forum_integration=self.forum,
            coordinator=self.coordinator,
        )
        logger.info("Learning integration manager initialized")

        # Hook learning into Discord
        if self.discord:
            self.discord.set_learning_integration(self.learning_manager)

        # Hook learning into Reddit
        if self.reddit:
            self.reddit.set_learning_integration(self.learning_manager)

        # Hook learning into Forum
        if self.forum:
            self.forum.set_learning_integration(self.learning_manager)

        logger.info("Integration Hub Service initialization complete")

    async def start(self):
        """Start all platform integrations and background tasks"""
        logger.info("Starting Integration Hub Service...")

        self.is_running = True

        # Start Discord bot
        if self.discord:
            task = asyncio.create_task(self.discord.start())
            self.tasks.append(task)
            logger.info("Discord bot started")

        # Start Reddit monitoring
        if self.reddit:
            task = asyncio.create_task(self.reddit.monitor_subreddits())
            self.tasks.append(task)
            logger.info("Reddit monitoring started")

        # Start Forum monitoring
        if self.forum:
            task = asyncio.create_task(self.forum.monitor_forums())
            self.tasks.append(task)
            logger.info("Forum monitoring started")

        # Start coordinator background tasks
        if self.coordinator:
            task = asyncio.create_task(self.coordinator.start_background_tasks())
            self.tasks.append(task)
            logger.info("Coordinator background tasks started")

        # Start agent rotation task
        task = asyncio.create_task(self._agent_rotation_loop())
        self.tasks.append(task)
        logger.info("Agent rotation task started")

        # Start knowledge consolidation task
        task = asyncio.create_task(self._knowledge_consolidation_loop())
        self.tasks.append(task)
        logger.info("Knowledge consolidation task started")

        logger.info("Integration Hub Service started successfully")

    async def stop(self):
        """Stop all platform integrations and background tasks"""
        logger.info("Stopping Integration Hub Service...")

        self.is_running = False

        # Cancel all background tasks
        for task in self.tasks:
            task.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self.tasks, return_exceptions=True)
        self.tasks.clear()

        # Stop Discord bot
        if self.discord:
            await self.discord.stop()
            logger.info("Discord bot stopped")

        # Stop Reddit monitoring
        if self.reddit:
            await self.reddit.stop()
            logger.info("Reddit monitoring stopped")

        # Stop Forum monitoring
        if self.forum:
            await self.forum.stop()
            logger.info("Forum monitoring stopped")

        # Shutdown learning system
        if self.learning_manager:
            await self.learning_manager.shutdown()
            logger.info("Learning system shutdown")

        logger.info("Integration Hub Service stopped")

    async def get_service_status(self) -> dict[str, Any]:
        """Get comprehensive status of all services"""
        status = {
            "is_running": self.is_running,
            "timestamp": datetime.now(UTC).isoformat(),
            "platforms": {},
            "learning": {},
            "agents": {},
        }

        # Platform status
        status["platforms"]["discord"] = {
            "enabled": self.discord is not None,
            "connected": self.discord.is_connected if self.discord else False,
            "guild_count": len(self.discord.guilds) if self.discord else 0,
        }

        status["platforms"]["reddit"] = {
            "enabled": self.reddit is not None,
            "connected": self.reddit.is_connected if self.reddit else False,
            "subreddits_monitored": (len(self.reddit.monitored_subreddits) if self.reddit else 0),
        }

        status["platforms"]["forum"] = {
            "enabled": self.forum is not None,
            "connected": self.forum.is_connected if self.forum else False,
            "categories_monitored": (len(self.forum.monitored_categories) if self.forum else 0),
        }

        # Learning status
        if self.learning_manager:
            learning_stats = await self.learning_manager.get_learning_statistics()
            status["learning"] = learning_stats

        # Agent status
        if self.agent_orchestrator:
            agent_stats = self.agent_orchestrator.get_statistics()
            status["agents"] = agent_stats

        return status

    async def trigger_agent_discussion(
        self, platform: str, topic: str, channel_or_thread: str, max_agents: int = 3
    ) -> dict[str, Any]:
        """
        Trigger an agent discussion on a specific platform.

        Args:
            platform: 'discord', 'reddit', or 'forum'
            topic: The topic to discuss
            channel_or_thread: The channel ID or thread ID
            max_agents: Maximum number of agents to participate

        Returns:
            Result of the discussion
        """
        logger.info("Triggering agent discussion on %s: %s", platform, topic)

        # Select appropriate agents
        agents = await self.agent_orchestrator.select_agents_for_topic(
            topic=topic, platform=platform, max_agents=max_agents
        )

        if not agents:
            return {"error": "No agents available for discussion"}

        # Record participation
        for agent in agents:
            self.agent_orchestrator.record_participation(agent.agent_id)

        # Trigger discussion on appropriate platform
        if platform == "discord" and self.discord:
            result = await self.discord.start_agent_discussion(
                channel_id=channel_or_thread,
                topic=topic,
                agents=[a.agent_id for a in agents],
            )
        elif platform == "reddit" and self.reddit:
            result = await self.reddit.start_agent_thread(
                subreddit=channel_or_thread,
                topic=topic,
                agents=[a.agent_id for a in agents],
            )
        elif platform == "forum" and self.forum:
            result = await self.forum.start_agent_thread(
                category_id=channel_or_thread,
                topic=topic,
                agents=[a.agent_id for a in agents],
            )
        else:
            return {"error": f"Platform {platform} not available"}

        return {
            "success": True,
            "topic": topic,
            "platform": platform,
            "agents_participated": [a.name for a in agents],
            "result": result,
        }

    async def trigger_agent_debate(self, platform: str, topic: str, channel_or_thread: str) -> dict[str, Any]:
        """
        Trigger a 1-on-1 agent debate on a specific platform.
        """
        logger.info("Triggering agent debate on %s: %s", platform, topic)

        # Select debate participants
        agent1, agent2 = await self.agent_orchestrator.select_debate_participants(topic=topic, platform=platform)

        # Record participation
        self.agent_orchestrator.record_participation(agent1.agent_id)
        self.agent_orchestrator.record_participation(agent2.agent_id)

        # Trigger debate on appropriate platform
        if platform == "discord" and self.discord:
            result = await self.discord.start_agent_debate(
                channel_id=channel_or_thread,
                topic=topic,
                agent1_id=agent1.agent_id,
                agent2_id=agent2.agent_id,
            )
        elif platform == "reddit" and self.reddit:
            result = await self.reddit.start_agent_debate_thread(
                subreddit=channel_or_thread,
                topic=topic,
                agent1_id=agent1.agent_id,
                agent2_id=agent2.agent_id,
            )
        else:
            return {"error": f"Platform {platform} not available for debates"}

        return {
            "success": True,
            "topic": topic,
            "platform": platform,
            "debaters": [agent1.name, agent2.name],
            "result": result,
        }

    async def _agent_rotation_loop(self):
        """Background task for periodic agent rotation"""
        while self.is_running:
            try:
                await asyncio.sleep(3600)  # Rotate every hour
                await self.agent_orchestrator.rotate_agents()
                logger.info("Agent rotation completed")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in agent rotation loop: %s", e)

    async def _knowledge_consolidation_loop(self):
        """Background task for periodic knowledge consolidation"""
        while self.is_running:
            try:
                # Consolidate daily
                await asyncio.sleep(86400)  # Every 24 hours
                logger.info("Knowledge consolidation triggered")
                # Knowledge consolidation logic would go here
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in knowledge consolidation loop: %s", e)


# Global instance
_integration_hub: IntegrationHubService | None = None


def get_integration_hub() -> IntegrationHubService:
    """Get or create integration hub singleton"""
    global _integration_hub
    if _integration_hub is None:
        _integration_hub = IntegrationHubService()
    return _integration_hub


async def main():
    """Main entry point for running the integration hub"""
    import signal

    hub = get_integration_hub()

    # Setup signal handlers
    def signal_handler():
        logger.info("Shutdown signal received")
        _task = asyncio.create_task(hub.stop())
        _background_tasks.add(_task)
        _task.add_done_callback(_background_tasks.discard)

    for sig in [signal.SIGTERM, signal.SIGINT]:
        signal.signal(sig, lambda s, f: signal_handler())

    # Initialize and start
    await hub.initialize()
    await hub.start()

    # Keep running
    try:
        while hub.is_running:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await hub.stop()


if __name__ == "__main__":
    asyncio.run(main())
