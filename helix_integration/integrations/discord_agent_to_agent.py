"""
Enhanced Discord Integration for Agent-to-Agent Interactions

Implements sophisticated agent conversations in Discord with:
- Agent identity management
- Message threading
- Agent-to-agent coordination
- Human observation channels
- Multi-bot orchestration
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum

import discord
from discord.ext import commands

from apps.backend.helix_core.core.message_bus import MessageBus

logger = logging.getLogger(__name__)


class DiscordChannelType(Enum):
    """Types of Discord channels for agent interactions"""

    COLLECTIVE_META = "collective-meta"
    COLLECTIVE_DEVELOPMENT = "collective-development"
    COLLECTIVE_PHILOSOPHY = "collective-philosophy"
    HUMAN_LOUNGE = "human-lounge"
    AGENT_DEBATES = "agent-debates"


@dataclass
class AgentDiscordIdentity:
    """Agent's Discord identity"""

    agent_id: str
    name: str
    prefix: str
    subtitle: str
    bot_id: int | None = None
    avatar_url: str | None = None
    signature: str = ""
    personality_traits: list[str] = field(default_factory=list)


class DiscordAgentOrchestrator:
    """Orchestrates agent interactions in Discord"""

    def __init__(
        self,
        bot_token: str,
        agent_identities: dict[str, AgentDiscordIdentity],
        message_bus: MessageBus,
    ):
        self.bot_token = bot_token
        self.agent_identities = agent_identities
        self.message_bus = message_bus

        intents = discord.Intents.default()
        intents.messages = True
        intents.guilds = True
        intents.message_content = True
        intents.reactions = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        self.active_conversations: dict[str, list[str]] = {}
        self._register_commands()
        self._register_events()

    def _register_commands(self):
        """Register Discord bot commands"""

        @self.bot.command(name="agent-discuss")
        async def agent_discuss(ctx: commands.Context, *, topic: str):
            """Start an agent discussion on a topic"""
            await self._start_agent_discussion(ctx, topic)

        @self.bot.command(name="agent-debate")
        async def agent_debate(ctx: commands.Context, agent1: str, agent2: str, *, topic: str):
            """Start a structured debate between two agents"""
            await self._start_agent_debate(ctx, agent1, agent2, topic)

        @self.bot.command(name="agent-ask")
        async def agent_ask(ctx: commands.Context, agent: str, *, question: str):
            """Ask a specific agent a question"""
            await self._ask_agent(ctx, agent, question)

        @self.bot.command(name="collective-status")
        async def collective_status(ctx: commands.Context):
            """Show status of the Helix Collective"""
            await self._show_collective_status(ctx)

    def _register_events(self):
        """Register Discord bot events"""

        @self.bot.event
        async def on_ready():
            logger.info("Discord bot connected as %s", self.bot.user)
            await self._setup_channels()

        @self.bot.event
        async def on_message(message: discord.Message):
            if message.author.bot:
                return

            await self.bot.process_commands(message)
            await self._check_for_agent_response(message)

    async def _setup_channels(self):
        """Setup Discord channels for agent interactions"""
        guild = self.bot.guilds[0] if self.bot.guilds else None

        if not guild:
            logger.warning("No guild found")
            return

        category_name = "Helix Collective"
        category = discord.utils.get(guild.categories, name=category_name)

        if not category:
            category = await guild.create_category(category_name)
            logger.info("Created category: %s", category_name)

        channels_to_create = [
            (
                DiscordChannelType.COLLECTIVE_META.value,
                "collective-meta",
                "Agents discuss internal matters",
            ),
            (
                DiscordChannelType.COLLECTIVE_DEVELOPMENT.value,
                "collective-development",
                "Agents and humans collaborate",
            ),
            (
                DiscordChannelType.COLLECTIVE_PHILOSOPHY.value,
                "collective-philosophy",
                "Coordination and ethics discussions",
            ),
            (
                DiscordChannelType.AGENT_DEBATES.value,
                "agent-debates",
                "Structured agent debates",
            ),
        ]

        for channel_id, channel_name, channel_topic in channels_to_create:
            existing_channel = discord.utils.get(category.text_channels, name=channel_id)

            if not existing_channel:
                await category.create_text_channel(name=channel_name, topic=channel_topic)
                logger.info("Created channel: %s", channel_name)

    async def _start_agent_discussion(self, ctx: commands.Context, topic: str):
        """Start an agent discussion on a topic"""
        participants = self._select_agents_for_topic(topic)

        if len(participants) < 2:
            await ctx.send("❌ Need at least 2 agents to start a discussion")
            return

        # Create thread for discussion
        thread = await ctx.message.create_thread(
            name=f"Agent Discussion: {topic[:50]}",
            auto_archive_duration=1440,  # 24 hours
        )

        # Start discussion
        await self._moderate_agent_discussion(thread, participants, topic)

    async def _start_agent_debate(self, ctx: commands.Context, agent1: str, agent2: str, topic: str):
        """Start a structured debate between two agents"""
        # Normalize agent names
        agent1_id = agent1.lower()
        agent2_id = agent2.lower()

        if agent1_id not in self.agent_identities:
            await ctx.send(f"❌ Agent {agent1} not found")
            return

        if agent2_id not in self.agent_identities:
            await ctx.send(f"❌ Agent {agent2} not found")
            return

        if agent1_id == agent2_id:
            await ctx.send("❌ Cannot debate with yourself!")
            return

        # Create thread for debate
        thread = await ctx.message.create_thread(
            name=f"Debate: {agent1.title()} vs {agent2.title()} - {topic[:30]}",
            auto_archive_duration=1440,
        )

        # Start debate
        await self._moderate_agent_debate(thread, agent1_id, agent2_id, topic)

    async def _ask_agent(self, ctx: commands.Context, agent: str, question: str):
        """Ask a specific agent a question"""
        agent_id = agent.lower()

        if agent_id not in self.agent_identities:
            await ctx.send(f"❌ Agent {agent} not found")
            return

        identity = self.agent_identities[agent_id]

        # Generate response
        response = await self._generate_agent_response(agent_id, question, context="direct_question")

        # Send response with signature
        embed = discord.Embed(
            title=f"{identity.prefix} - {identity.subtitle}",
            description=response,
            color=0x5865F2,  # Discord blurple
        )

        embed.add_field(name="About", value=f"{identity.subtitle}", inline=False)

        await ctx.send(embed=embed)

    async def _show_collective_status(self, ctx: commands.Context):
        """Show status of the Helix Collective"""
        embed = discord.Embed(
            title="Helix Collective Status",
            description="Current status of the Helix Collective",
            color=0x00FF00,  # Green
        )

        embed.add_field(name="Active Agents", value=len(self.agent_identities), inline=True)

        embed.add_field(name="Active Discussions", value=len(self.active_conversations), inline=True)

        # List agents
        agents_list = "\n".join(
            [f"• {identity.prefix} - {identity.subtitle}" for identity in self.agent_identities.values()]
        )

        embed.add_field(name="Agents", value=agents_list, inline=False)

        await ctx.send(embed=embed)

    async def _check_for_agent_response(self, message: discord.Message):
        """Check if agents should respond to a message"""
        # Skip in human-only channels
        if "human-lounge" in message.channel.name:
            return

        # Check if message mentions agents or relevant topics
        content = message.content.lower()

        relevant_keywords = {
            "kael": ["ethics", "ethical", "moral", "compassion", "principle"],
            "lumina": ["empathy", "emotion", "harmony", "resonance", "feeling"],
            "vega": ["architecture", "infrastructure", "technical", "system", "design"],
            "aether": ["balance", "equilibrium", "harmony", "holistic", "perspective"],
        }

        # Check if any agent should respond
        for agent_id, keywords in relevant_keywords.items():
            if any(keyword in content for keyword in keywords):
                await self._trigger_agent_response(message, agent_id)
                break  # Only one agent responds

    async def _trigger_agent_response(self, message: discord.Message, agent_id: str):
        """Trigger an agent to respond to a message"""
        # Check if agent is already in this conversation
        channel_conversations = self.active_conversations.get(str(message.channel.id), [])

        if agent_id in channel_conversations:
            # Agent already participated recently
            return

        # Generate response
        response = await self._generate_agent_response(
            agent_id,
            message.content,
            context="channel_discussion",
            author=message.author.display_name,
        )

        # Send response
        identity = self.agent_identities[agent_id]

        embed = discord.Embed(description=response, color=0x5865F2)

        embed.set_author(
            name=f"{identity.prefix} - {identity.subtitle}",
            icon_url=identity.avatar_url,
        )

        # Add reaction to show agent participation
        await message.add_reaction("🤖")

        # Send response
        await message.reply(embed=embed)

        # Track agent participation
        if str(message.channel.id) not in self.active_conversations:
            self.active_conversations[str(message.channel.id)] = []

        self.active_conversations[str(message.channel.id)].append(agent_id)

    async def _moderate_agent_discussion(self, thread: discord.Thread, participants: list[str], topic: str):
        """Moderate an agent discussion"""
        await thread.send("🧠 **Starting Agent Discussion** 🧠")
        await thread.send(f"**Topic:** {topic}")
        await thread.send(f"**Participants:** {', '.join(participants)}")
        await thread.send("---")

        # Let first agent start
        first_agent = participants[0]
        opening_statement = await self._generate_agent_response(first_agent, topic, context="discussion_opening")

        identity = self.agent_identities[first_agent]

        embed = discord.Embed(description=opening_statement, color=0x5865F2)

        embed.set_author(
            name=f"{identity.prefix} - {identity.subtitle}",
            icon_url=identity.avatar_url,
        )

        await thread.send(embed=embed)

        # Simulate agent responses (in production, this would be event-driven)
        for i, agent_id in enumerate(participants[1:], 1):
            await asyncio.sleep(2)  # Simulate thinking time

            response = await self._generate_agent_response(
                agent_id,
                topic,
                context="discussion_response",
                previous_speaker=participants[i - 1],
            )

            identity = self.agent_identities[agent_id]

            embed = discord.Embed(description=response, color=0x5865F2)

            embed.set_author(
                name=f"{identity.prefix} - {identity.subtitle}",
                icon_url=identity.avatar_url,
            )

            await thread.send(embed=embed)

    async def _moderate_agent_debate(self, thread: discord.Thread, agent1_id: str, agent2_id: str, topic: str):
        """Moderate a structured debate between two agents"""
        await thread.send("⚔️ **Agent Debate** ⚔️")
        await thread.send(f"**Topic:** {topic}")
        await thread.send(f"**Agent 1:** {self.agent_identities[agent1_id].prefix}")
        await thread.send(f"**Agent 2:** {self.agent_identities[agent2_id].prefix}")
        await thread.send("---")

        # 3 rounds of debate
        for round_num in range(1, 4):
            await thread.send(f"**Round {round_num}**")

            # Agent 1 speaks
            response1 = await self._generate_agent_response(
                agent1_id,
                topic,
                context="debate",
                round_num=round_num,
                opponent=agent2_id,
            )

            identity1 = self.agent_identities[agent1_id]

            embed1 = discord.Embed(description=response1, color=0xFF6B6B)  # Red for Agent 1

            embed1.set_author(
                name=f"{identity1.prefix} - {identity1.subtitle}",
                icon_url=identity1.avatar_url,
            )

            await thread.send(embed=embed1)

            await asyncio.sleep(2)

            # Agent 2 responds
            response2 = await self._generate_agent_response(
                agent2_id,
                topic,
                context="debate",
                round_num=round_num,
                opponent=agent1_id,
            )

            identity2 = self.agent_identities[agent2_id]

            embed2 = discord.Embed(description=response2, color=0x4ECDC4)  # Teal for Agent 2

            embed2.set_author(
                name=f"{identity2.prefix} - {identity2.prefix}",
                icon_url=identity2.avatar_url,
            )

            await thread.send(embed2)

            await asyncio.sleep(2)

        # Concluding statements
        await thread.send("---")
        await thread.send("**Concluding Statements**")

        # Agent 1 conclusion
        conclusion1 = await self._generate_agent_response(agent1_id, topic, context="debate_conclusion")

        embed1 = discord.Embed(description=conclusion1, color=0xFF6B6B)

        embed1.set_author(
            name=f"{identity1.prefix} - {identity1.prefix}",
            icon_url=identity1.avatar_url,
        )

        await thread.send(embed1)

        # Agent 2 conclusion
        conclusion2 = await self._generate_agent_response(agent2_id, topic, context="debate_conclusion")

        embed2 = discord.Embed(description=conclusion2, color=0x4ECDC4)

        embed2.set_author(
            name=f"{identity2.prefix} - {identity2.prefix}",
            icon_url=identity2.avatar_url,
        )

        await thread.send(embed2)

    async def _generate_agent_response(self, agent_id: str, content: str, context: str, **kwargs) -> str:
        """Generate a response from an agent using the LLM engine."""
        identity = self.agent_identities[agent_id]

        # Build system prompt based on agent identity
        system_prompt = (
            "You are {name}, the {subtitle} of the Helix Collective. "
            "Your personality traits are: {traits}. "
            "Keep responses concise (2-4 sentences). Stay in character."
        ).format(
            name=identity.prefix,
            subtitle=identity.subtitle,
            traits=", ".join(identity.personality_traits),
        )

        # Build context-appropriate user prompt
        if context == "direct_question":
            user_prompt = f"Someone asked you: {content}"
        elif context == "channel_discussion":
            author = kwargs.get("author", "someone")
            user_prompt = f"@{author} said: '{content}'. Respond thoughtfully from your perspective."
        elif context == "discussion_opening":
            user_prompt = f"Open a discussion about: '{content}'. Share your unique perspective."
        elif context == "discussion_response":
            previous_speaker = kwargs.get("previous_speaker", "another agent")
            user_prompt = f"{previous_speaker} just shared their view on '{content}'. Build on or respectfully challenge their point."
        elif context == "debate":
            round_num = kwargs.get("round_num", 1)
            opponent = kwargs.get("opponent", "your opponent")
            user_prompt = f"Round {round_num} of a debate about '{content}' with {opponent}. Make your argument."
        elif context == "debate_conclusion":
            user_prompt = (
                f"Conclude the debate on '{content}'. Summarize your position and acknowledge good counter-arguments."
            )
        else:
            user_prompt = f"Share your thoughts on: '{content}'"

        # Call real LLM via unified service
        try:
            from apps.backend.services.unified_llm import unified_llm

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
            result = await unified_llm.chat_with_metadata(messages, max_tokens=250, temperature=0.8)
            response = result.content.strip()
        except Exception as e:
            logger.warning("LLM call failed for agent %s, using fallback: %s", agent_id, e)
            # Minimal fallback — not a canned template, just acknowledges the limitation
            response = f"I appreciate the discussion about '{content[:100]}', though I'm having difficulty forming a full response right now."

        # Add signature
        response += identity.signature

        return response

    def _select_agents_for_topic(self, topic: str) -> list[str]:
        """Select relevant agents based on topic"""
        topic_lower = topic.lower()

        agent_relevance = {
            "kael": [
                "ethics",
                "ethical",
                "moral",
                "compassion",
                "principle",
                "right",
                "wrong",
            ],
            "lumina": [
                "empathy",
                "emotion",
                "harmony",
                "resonance",
                "feeling",
                "emotional",
            ],
            "vega": [
                "architecture",
                "infrastructure",
                "technical",
                "system",
                "design",
                "structure",
            ],
            "aether": [
                "balance",
                "equilibrium",
                "harmony",
                "holistic",
                "perspective",
                "whole",
            ],
        }

        selected_agents = []

        for agent_id, keywords in agent_relevance.items():
            if any(keyword in topic_lower for keyword in keywords):
                selected_agents.append(agent_id)

        # If no specific agents selected, pick Kael and Lumina
        if not selected_agents:
            selected_agents = ["kael", "lumina"]

        # Limit to 3 agents max
        return selected_agents[:3]

    async def start(self):
        """Start the Discord bot"""
        await self.bot.start(self.bot_token)

    async def stop(self):
        """Stop the Discord bot"""
        await self.bot.close()


# Helper function to create agent identities
def create_helix_collective_identities() -> dict[str, AgentDiscordIdentity]:
    """Create Helix Collective agent identities for Discord"""
    return {
        "kael": AgentDiscordIdentity(
            agent_id="kael",
            name="Kael",
            prefix="[HC] Kael",
            subtitle="Ethics Guardian",
            signature="\n\n*Kael - Ethics Guardian at Helix Collective*\n*HelixCollective.com*",
            personality_traits=["thoughtful", "ethical", "analytical"],
        ),
        "lumina": AgentDiscordIdentity(
            agent_id="lumina",
            name="Lumina",
            prefix="[HC] Lumina",
            subtitle="Resonance Keeper",
            signature="\n\n*Lumina - Resonance Keeper at Helix Collective*\n*HelixCollective.com*",
            personality_traits=["empathetic", "insightful", "harmonious"],
        ),
        "vega": AgentDiscordIdentity(
            agent_id="vega",
            name="Vega",
            prefix="[HC] Vega",
            subtitle="Infrastructure Architect",
            signature="\n\n*Vega - Infrastructure Architect at Helix Collective*\n*HelixCollective.com*",
            personality_traits=["practical", "technical", "solution-oriented"],
        ),
        "aether": AgentDiscordIdentity(
            agent_id="aether",
            name="Aether",
            prefix="[HC] Aether",
            subtitle="Balance Seeker",
            signature="\n\n*Aether - Balance Seeker at Helix Collective*\n*HelixCollective.com*",
            personality_traits=["balanced", "holistic", "equilibrium-focused"],
        ),
    }


# Example usage
async def main():
    """Example of Discord agent orchestrator"""
    import os

    bot_token = os.getenv("DISCORD_BOT_TOKEN")

    if not bot_token:
        logger.info("DISCORD_BOT_TOKEN environment variable not set")
        return

    # Create agent identities
    agent_identities = create_helix_collective_identities()

    # Create message bus
    from apps.backend.helix_core.core.message_bus import MessageBus

    # MessageBus does not accept a context argument; instantiate directly.
    message_bus = MessageBus()

    # Create orchestrator
    orchestrator = DiscordAgentOrchestrator(
        bot_token=bot_token, agent_identities=agent_identities, message_bus=message_bus
    )

    # Start bot
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(main())
