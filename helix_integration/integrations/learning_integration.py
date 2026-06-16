"""
Learning System Integration with Platform Integrations

Integrates the learning system with Discord, Reddit, and Forum integrations
to enable agents to learn from all platform interactions.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from learning import InteractionType, PrivacyLevel, get_learning_system

from .ai_forum_integration import AIForumIntegration
from .cross_platform_agent_coordinator import CrossPlatformAgentCoordinator
from .discord_agent_to_agent import DiscordAgentInteraction
from .reddit_integration import RedditIntegration

logger = logging.getLogger(__name__)


class LearningIntegrationManager:
    """
    Manages integration between learning system and platform integrations.

    This component automatically records interactions from Discord, Reddit,
    and Forums into the learning system, enabling agents to learn from
    all their interactions across platforms.
    """

    def __init__(
        self,
        discord_integration: DiscordAgentInteraction | None = None,
        reddit_integration: RedditIntegration | None = None,
        forum_integration: AIForumIntegration | None = None,
        coordinator: CrossPlatformAgentCoordinator | None = None,
    ):
        self.discord_integration = discord_integration
        self.reddit_integration = reddit_integration
        self.forum_integration = forum_integration
        self.coordinator = coordinator
        self.learning_system = get_learning_system()

        # Track learning status
        self.learning_enabled = True
        self.stats = {
            "discord_interactions": 0,
            "reddit_interactions": 0,
            "forum_interactions": 0,
            "total_learned": 0,
        }

        logger.info("LearningIntegrationManager initialized")

    async def record_discord_message(
        self,
        agent_id: str,
        content: str,
        channel_id: str,
        user_id: str | None = None,
        is_dm: bool = False,
    ):
        """Record a Discord message interaction"""
        if not self.learning_enabled:
            return

        interaction_type = InteractionType.DISCORD_DM if is_dm else InteractionType.DISCORD_MESSAGE
        privacy_level = PrivacyLevel.PRIVATE if is_dm else PrivacyLevel.SEMI_PRIVATE

        await self.learning_system.record_interaction(
            platform="discord",
            interaction_type=interaction_type,
            agent_id=agent_id,
            content=content,
            user_id=user_id,
            privacy_level=privacy_level,
            metadata={
                "channel_id": channel_id,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )

        self.stats["discord_interactions"] += 1
        self.stats["total_learned"] += 1

    async def record_discord_agent_discussion(
        self, topic: str, participants: list[str], messages: list[dict[str, Any]]
    ):
        """Record a Discord agent discussion"""
        if not self.learning_enabled:
            return

        for message in messages:
            agent_id = message.get("agent_id")
            content = message.get("content")

            if agent_id and content:
                await self.learning_system.record_interaction(
                    platform="discord",
                    interaction_type=InteractionType.AGENT_DISCUSSION,
                    agent_id=agent_id,
                    content=content,
                    privacy_level=PrivacyLevel.PUBLIC,
                    metadata={
                        "topic": topic,
                        "participants": participants,
                        "discussion_type": "agent_discussion",
                    },
                )

        logger.info("Recorded Discord agent discussion: %s with %s agents", topic, len(participants))

    async def record_discord_agent_debate(self, topic: str, agent1: str, agent2: str, rounds: list[dict[str, Any]]):
        """Record a Discord agent debate"""
        if not self.learning_enabled:
            return

        for round_data in rounds:
            for agent_id, content in round_data.items():
                if agent_id in [agent1, agent2] and content:
                    await self.learning_system.record_interaction(
                        platform="discord",
                        interaction_type=InteractionType.AGENT_DEBATE,
                        agent_id=agent_id,
                        content=content,
                        privacy_level=PrivacyLevel.PUBLIC,
                        metadata={
                            "topic": topic,
                            "debate_type": "agent_debate",
                            "opponent": agent2 if agent_id == agent1 else agent1,
                        },
                    )

        logger.info("Recorded Discord agent debate: %s between %s and %s", topic, agent1, agent2)

    async def record_reddit_post(
        self,
        agent_id: str,
        content: str,
        subreddit: str,
        post_id: str,
        user_id: str | None = None,
    ):
        """Record a Reddit post interaction"""
        if not self.learning_enabled:
            return

        await self.learning_system.record_interaction(
            platform="reddit",
            interaction_type=InteractionType.REDDIT_POST,
            agent_id=agent_id,
            content=content,
            user_id=user_id,
            privacy_level=PrivacyLevel.PUBLIC,
            metadata={
                "subreddit": subreddit,
                "post_id": post_id,
                "platform_type": "reddit",
            },
        )

        self.stats["reddit_interactions"] += 1
        self.stats["total_learned"] += 1

    async def record_reddit_comment(
        self,
        agent_id: str,
        content: str,
        subreddit: str,
        post_id: str,
        comment_id: str,
        user_id: str | None = None,
    ):
        """Record a Reddit comment interaction"""
        if not self.learning_enabled:
            return

        await self.learning_system.record_interaction(
            platform="reddit",
            interaction_type=InteractionType.REDDIT_COMMENT,
            agent_id=agent_id,
            content=content,
            user_id=user_id,
            privacy_level=PrivacyLevel.PUBLIC,
            metadata={
                "subreddit": subreddit,
                "post_id": post_id,
                "comment_id": comment_id,
            },
        )

        self.stats["reddit_interactions"] += 1
        self.stats["total_learned"] += 1

    async def record_forum_post(
        self,
        agent_id: str,
        content: str,
        category: str,
        thread_id: str,
        user_id: str | None = None,
    ):
        """Record a forum post interaction"""
        if not self.learning_enabled:
            return

        await self.learning_system.record_interaction(
            platform="forum",
            interaction_type=InteractionType.FORUM_POST,
            agent_id=agent_id,
            content=content,
            user_id=user_id,
            privacy_level=PrivacyLevel.SEMI_PRIVATE,
            metadata={
                "category": category,
                "thread_id": thread_id,
                "platform_type": "forum",
            },
        )

        self.stats["forum_interactions"] += 1
        self.stats["total_learned"] += 1

    async def record_forum_reply(
        self,
        agent_id: str,
        content: str,
        category: str,
        thread_id: str,
        reply_id: str,
        user_id: str | None = None,
    ):
        """Record a forum reply interaction"""
        if not self.learning_enabled:
            return

        await self.learning_system.record_interaction(
            platform="forum",
            interaction_type=InteractionType.FORUM_REPLY,
            agent_id=agent_id,
            content=content,
            user_id=user_id,
            privacy_level=PrivacyLevel.SEMI_PRIVATE,
            metadata={
                "category": category,
                "thread_id": thread_id,
                "reply_id": reply_id,
            },
        )

        self.stats["forum_interactions"] += 1
        self.stats["total_learned"] += 1

    async def get_agent_continuity_context(
        self, agent_id: str, user_id: str | None = None, platform: str = "discord"
    ) -> dict[str, Any]:
        """
        Get continuity context for an agent.

        This provides the agent with knowledge of previous interactions
        across platforms to maintain conversation continuity.
        """
        # Get cross-platform interaction history
        interactions = await self.learning_system.get_cross_platform_continuity(
            user_id=user_id, agent_id=agent_id, platform=platform
        )

        # Get relevant knowledge
        if interactions:
            # Extract topics from recent interactions
            recent_topics = []
            for interaction in interactions[:5]:
                # Extract topics from content (simplified)
                words = interaction.content.lower().split()
                topics = [w for w in words if len(w) > 4]
                recent_topics.extend(topics[:3])

            # Get knowledge for these topics
            all_knowledge = []
            for topic in set(recent_topics[:10]):
                knowledge = await self.learning_system.get_relevant_knowledge(agent_id=agent_id, topic=topic, limit=2)
                all_knowledge.extend(knowledge)

            # Get shared context from other agents
            if recent_topics:
                shared_context = await self.learning_system.get_shared_context(
                    topic=recent_topics[0], exclude_agent_id=agent_id
                )
            else:
                shared_context = None
        else:
            all_knowledge = []
            shared_context = None

        return {
            "agent_id": agent_id,
            "recent_interactions_count": len(interactions),
            "interaction_platforms": list({i.platform for i in interactions}),
            "relevant_knowledge_count": len(all_knowledge),
            "relevant_knowledge": all_knowledge[:5],
            "shared_context": shared_context,
            "last_interaction": (interactions[0].timestamp.isoformat() if interactions else None),
        }

    async def enhance_agent_response(self, agent_id: str, topic: str, current_response: str) -> str:
        """
        Enhance an agent's response using learned knowledge.

        This takes a basic response and enhances it with insights
        the agent has learned from previous interactions.
        """
        # Get relevant knowledge
        knowledge = await self.learning_system.get_relevant_knowledge(agent_id=agent_id, topic=topic, limit=3)

        if not knowledge:
            return current_response

        # Get shared context from other agents
        shared_context = await self.learning_system.get_shared_context(topic=topic, exclude_agent_id=agent_id)

        # Build enhanced response
        enhanced_parts = [current_response]

        # Add agent's own insights
        if knowledge:
            insights = []
            for k in knowledge:
                if k.confidence > 0.7:
                    insights.append(f"From my experience: {k.insight}")

            if insights:
                enhanced_parts.append("\n\n**Learned Insights:**")
                enhanced_parts.extend(insights)

        # Add context from other agents
        if shared_context and shared_context.get("agents_participating"):
            other_agents = [a for a in shared_context["agents_participating"] if a != agent_id]
            if other_agents:
                enhanced_parts.append("\n\n**Collective Wisdom:**")
                enhanced_parts.append(
                    f"Other agents ({', '.join(other_agents)}) have "
                    f"{shared_context['total_insights']} insights on this topic."
                )

        return "\n\n".join(enhanced_parts)

    async def get_learning_statistics(self) -> dict[str, Any]:
        """Get comprehensive learning statistics"""
        learning_stats = self.learning_system.get_statistics()

        return {**learning_stats, "platform_breakdown": self.stats}

    def enable_learning(self):
        """Enable learning"""
        self.learning_enabled = True
        logger.info("Learning enabled")

    def disable_learning(self):
        """Disable learning"""
        self.learning_enabled = False
        logger.info("Learning disabled")

    async def shutdown(self):
        """Shutdown learning integration"""
        logger.info("LearningIntegrationManager shutting down...")
        await self.learning_system.shutdown()
        logger.info("Shutdown complete")


# Convenience functions for easy access

_integration_manager: LearningIntegrationManager | None = None


def get_learning_integration_manager(
    discord_integration: DiscordAgentInteraction | None = None,
    reddit_integration: RedditIntegration | None = None,
    forum_integration: AIForumIntegration | None = None,
    coordinator: CrossPlatformAgentCoordinator | None = None,
) -> LearningIntegrationManager:
    """Get or create learning integration manager singleton"""
    global _integration_manager
    if _integration_manager is None:
        _integration_manager = LearningIntegrationManager(
            discord_integration=discord_integration,
            reddit_integration=reddit_integration,
            forum_integration=forum_integration,
            coordinator=coordinator,
        )
    return _integration_manager
