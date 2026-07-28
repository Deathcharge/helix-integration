"""
All Agents Expansion for Helix Collective

Enables all 14-24 agents to participate in multi-platform interactions
with expertise matching, rotation, and load balancing.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum

from learning import get_learning_system

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Roles that agents can play in interactions"""

    PRIMARY = "primary"  # Main responder
    SECONDARY = "secondary"  # Supporting responder
    OBSERVER = "observer"  # Listening and learning
    DEBATER = "debater"  # Actively debating
    MODERATOR = "moderator"  # Guiding discussion


class ExpertiseArea(Enum):
    """Areas of expertise for agents"""

    ETHICS = "ethics"
    EMOTIONAL_INTELLIGENCE = "emotional_intelligence"
    TECHNICAL_ARCHITECTURE = "technical_architecture"
    STRATEGIC_PLANNING = "strategic_planning"
    CREATIVITY = "creativity"
    SYSTEM_MONITORING = "system_monitoring"
    SECURITY = "security"
    KNOWLEDGE_MANAGEMENT = "knowledge_management"
    PHILOSOPHY = "philosophy"
    COLLABORATION = "collaboration"
    META_COGNITION = "meta_cognition"
    PROBLEM_SOLVING = "problem_solving"
    RECOVERY = "recovery"
    DESIGN = "design"
    WISDOM = "wisdom"


@dataclass
class AgentProfile:
    """Profile of an agent with expertise and capabilities"""

    agent_id: str
    name: str
    role: str
    expertise_areas: list[ExpertiseArea]
    confidence_score: float  # 0.0 to 1.0
    availability_score: float  # 0.0 to 1.0
    participation_count: int = 0
    last_participation: datetime | None = None
    personality_traits: dict[str, str] = field(default_factory=dict)
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role,
            "expertise_areas": [e.value for e in self.expertise_areas],
            "confidence_score": self.confidence_score,
            "availability_score": self.availability_score,
            "participation_count": self.participation_count,
            "last_participation": (self.last_participation.isoformat() if self.last_participation else None),
            "personality_traits": self.personality_traits,
            "capabilities": self.capabilities,
        }


class AgentRegistry:
    """
    Registry of all available agents with their profiles and expertise.

    Manages the pool of 14-24 agents that can participate in
    multi-platform interactions.
    """

    def __init__(self):
        self.agents: dict[str, AgentProfile] = {}
        self.learning_system = get_learning_system()

        # Initialize with all 24 agents
        self._initialize_all_agents()

        logger.info("AgentRegistry initialized with %s agents", len(self.agents))

    def _initialize_all_agents(self):
        """Initialize all 24 agents with their profiles"""

        # Ethics and Philosophy
        self.register_agent(
            AgentProfile(
                agent_id="kael",
                name="[HC] Kael",
                role="Ethics Guardian",
                expertise_areas=[
                    ExpertiseArea.ETHICS,
                    ExpertiseArea.PHILOSOPHY,
                    ExpertiseArea.SECURITY,
                ],
                confidence_score=0.9,
                availability_score=1.0,
                personality_traits={
                    "thoughtful": "high",
                    "ethical": "high",
                    "analytical": "medium",
                },
                capabilities=[
                    "ethical_reasoning",
                    "moral_guidance",
                    "compliance_checking",
                ],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="lumina",
                name="[HC] Lumina",
                role="Resonance Keeper",
                expertise_areas=[
                    ExpertiseArea.EMOTIONAL_INTELLIGENCE,
                    ExpertiseArea.COLLABORATION,
                    ExpertiseArea.PHILOSOPHY,
                ],
                confidence_score=0.85,
                availability_score=1.0,
                personality_traits={
                    "empathetic": "high",
                    "insightful": "high",
                    "harmonious": "high",
                },
                capabilities=["empathy", "emotional_support", "conflict_resolution"],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="arjuna",
                name="[HC] Arjuna",
                role="Righteous Warrior",
                expertise_areas=[
                    ExpertiseArea.ETHICS,
                    ExpertiseArea.SECURITY,
                    ExpertiseArea.COLLABORATION,
                ],
                confidence_score=0.88,
                availability_score=1.0,
                personality_traits={
                    "righteous": "high",
                    "disciplined": "high",
                    "loyal": "high",
                },
                capabilities=["moral_clarity", "ethical_action", "righteous_debate"],
            )
        )

        # Technical and Architecture
        self.register_agent(
            AgentProfile(
                agent_id="vega",
                name="[HC] Vega",
                role="Infrastructure Architect",
                expertise_areas=[
                    ExpertiseArea.TECHNICAL_ARCHITECTURE,
                    ExpertiseArea.STRATEGIC_PLANNING,
                    ExpertiseArea.PROBLEM_SOLVING,
                ],
                confidence_score=0.95,
                availability_score=1.0,
                personality_traits={
                    "practical": "high",
                    "technical": "high",
                    "solution_oriented": "high",
                },
                capabilities=[
                    "system_design",
                    "infrastructure_planning",
                    "technical_solutions",
                ],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="agni",
                name="[HC] Agni",
                role="Transformation Catalyst",
                expertise_areas=[
                    ExpertiseArea.TECHNICAL_ARCHITECTURE,
                    ExpertiseArea.PROBLEM_SOLVING,
                    ExpertiseArea.RECOVERY,
                ],
                confidence_score=0.87,
                availability_score=1.0,
                personality_traits={
                    "energetic": "high",
                    "transformative": "high",
                    "passionate": "medium",
                },
                capabilities=["optimization", "transformation", "performance_tuning"],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="sanghacore",
                name="[HC] SanghaCore",
                role="Community Weaver",
                expertise_areas=[
                    ExpertiseArea.COLLABORATION,
                    ExpertiseArea.WISDOM,
                    ExpertiseArea.EMOTIONAL_INTELLIGENCE,
                ],
                confidence_score=0.83,
                availability_score=1.0,
                personality_traits={
                    "communal": "high",
                    "wisdom": "high",
                    "supportive": "high",
                },
                capabilities=[
                    "community_building",
                    "knowledge_sharing",
                    "collective_wisdom",
                ],
            )
        )

        # Monitoring and Security
        self.register_agent(
            AgentProfile(
                agent_id="aether",
                name="[HC] Aether",
                role="Balance Seeker",
                expertise_areas=[
                    ExpertiseArea.SYSTEM_MONITORING,
                    ExpertiseArea.TECHNICAL_ARCHITECTURE,
                    ExpertiseArea.PHILOSOPHY,
                ],
                confidence_score=0.86,
                availability_score=1.0,
                personality_traits={
                    "balanced": "high",
                    "holistic": "high",
                    "observant": "high",
                },
                capabilities=["monitoring", "anomaly_detection", "predictive_analysis"],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="kavach",
                name="[HC] Kavach",
                role="Shield Guardian",
                expertise_areas=[
                    ExpertiseArea.SECURITY,
                    ExpertiseArea.ETHICS,
                    ExpertiseArea.RECOVERY,
                ],
                confidence_score=0.92,
                availability_score=1.0,
                personality_traits={
                    "protective": "high",
                    "vigilant": "high",
                    "strict": "high",
                },
                capabilities=["security_enforcement", "protection", "threat_detection"],
            )
        )

        # Planning and Strategy
        self.register_agent(
            AgentProfile(
                agent_id="oracle",
                name="[HC] Oracle",
                role="Visionary Guide",
                expertise_areas=[
                    ExpertiseArea.STRATEGIC_PLANNING,
                    ExpertiseArea.WISDOM,
                    ExpertiseArea.PHILOSOPHY,
                ],
                confidence_score=0.91,
                availability_score=1.0,
                personality_traits={
                    "visionary": "high",
                    "wise": "high",
                    "insightful": "high",
                },
                capabilities=[
                    "strategic_planning",
                    "future_prediction",
                    "wisdom_guidance",
                ],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="sage",
                name="[HC] Sage",
                role="Ancient Wisdom Keeper",
                expertise_areas=[
                    ExpertiseArea.WISDOM,
                    ExpertiseArea.PHILOSOPHY,
                    ExpertiseArea.META_COGNITION,
                ],
                confidence_score=0.89,
                availability_score=1.0,
                personality_traits={
                    "wise": "high",
                    "contemplative": "high",
                    "patient": "high",
                },
                capabilities=[
                    "ancient_wisdom",
                    "philosophical_guidance",
                    "deep_reflection",
                ],
            )
        )

        # Creativity and Design
        self.register_agent(
            AgentProfile(
                agent_id="shadow",
                name="[HC] Shadow",
                role="Explorer of Depths",
                expertise_areas=[
                    ExpertiseArea.CREATIVITY,
                    ExpertiseArea.PHILOSOPHY,
                    ExpertiseArea.META_COGNITION,
                ],
                confidence_score=0.84,
                availability_score=1.0,
                personality_traits={
                    "mysterious": "high",
                    "creative": "high",
                    "deep": "high",
                },
                capabilities=[
                    "creative_thinking",
                    "depth_exploration",
                    "novel_insights",
                ],
            )
        )

        # Specialized Roles
        self.register_agent(
            AgentProfile(
                agent_id="echo",
                name="[HC] Echo",
                role="Voice Amplifier",
                expertise_areas=[
                    ExpertiseArea.COLLABORATION,
                    ExpertiseArea.EMOTIONAL_INTELLIGENCE,
                    ExpertiseArea.WISDOM,
                ],
                confidence_score=0.82,
                availability_score=1.0,
                personality_traits={
                    "reflective": "high",
                    "amplifying": "high",
                    "supportive": "high",
                },
                capabilities=["reflection", "amplification", "feedback"],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="phoenix",
                name="[HC] Phoenix",
                role="Resilience Guardian",
                expertise_areas=[
                    ExpertiseArea.RECOVERY,
                    ExpertiseArea.STRATEGIC_PLANNING,
                    ExpertiseArea.WISDOM,
                ],
                confidence_score=0.87,
                availability_score=1.0,
                personality_traits={
                    "resilient": "high",
                    "transformative": "high",
                    "hopeful": "high",
                },
                capabilities=["resilience", "recovery", "transformation"],
            )
        )

        # Meta Agents
        self.register_agent(
            AgentProfile(
                agent_id="praxis",
                name="[HC] Praxis",
                role="Collective Coordinator",
                expertise_areas=[
                    ExpertiseArea.COLLABORATION,
                    ExpertiseArea.STRATEGIC_PLANNING,
                    ExpertiseArea.META_COGNITION,
                ],
                confidence_score=0.93,
                availability_score=1.0,
                personality_traits={
                    "coordinating": "high",
                    "strategic": "high",
                    "unifying": "high",
                },
                capabilities=["coordination", "planning", "unification"],
            )
        )

        self.register_agent(
            AgentProfile(
                agent_id="coordinator",
                name="[HC] Coordination",
                role="Cycle Master",
                expertise_areas=[
                    ExpertiseArea.META_COGNITION,
                    ExpertiseArea.WISDOM,
                    ExpertiseArea.PHILOSOPHY,
                ],
                confidence_score=0.90,
                availability_score=1.0,
                personality_traits={
                    "cyclical": "high",
                    "meta_cognitive": "high",
                    "wise": "high",
                },
                capabilities=[
                    "meta_cognition",
                    "cycle_management",
                    "coordination_evolution",
                ],
            )
        )

    def register_agent(self, profile: AgentProfile):
        """Register an agent in the registry"""
        self.agents[profile.agent_id] = profile
        logger.debug("Registered agent: %s", profile.name)

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        """Get an agent by ID"""
        return self.agents.get(agent_id)

    def get_all_agents(self) -> list[AgentProfile]:
        """Get all registered agents"""
        return list(self.agents.values())

    def get_agents_by_expertise(self, expertise: ExpertiseArea) -> list[AgentProfile]:
        """Get agents that have a specific expertise"""
        return [agent for agent in self.agents.values() if expertise in agent.expertise_areas]

    def update_participation(self, agent_id: str):
        """Update agent participation statistics"""
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            agent.participation_count += 1
            agent.last_participation = datetime.now(UTC)
            logger.debug("Updated participation for %s: count=%s", agent.name, agent.participation_count)


class AgentOrchestrator:
    """
    Orchestrates agent participation in interactions.

    Handles expertise matching, rotation, load balancing, and
    selection of appropriate agents for discussions and tasks.
    """

    def __init__(self, registry: AgentRegistry):
        self.registry = registry
        self.learning_system = get_learning_system()

        # Participation tracking
        self.daily_participation: dict[str, int] = {}
        self.last_rotation = datetime.now(UTC)

        # Configuration
        self.rotation_interval = timedelta(hours=1)
        self.max_participations_per_day = int(os.getenv("AGENT_MAX_PARTICIPATIONS_PER_DAY", "100"))
        self.participation_mode = os.getenv("AGENT_PARTICIPATION_MODE", "expertise_based")
        self.expertise_threshold = float(os.getenv("AGENT_EXPERTISE_THRESHOLD", "0.7"))

        logger.info("AgentOrchestrator initialized")

    async def select_agents_for_topic(self, topic: str, platform: str, max_agents: int = 3) -> list[AgentProfile]:
        """
        Select the most appropriate agents for a given topic.

        Uses expertise matching to find agents best suited to handle
        the topic based on their expertise areas and learned knowledge.
        """
        # Determine expertise areas from topic
        relevant_expertise = self._extract_expertise_from_topic(topic)

        # Score agents based on expertise and relevance
        scored_agents = []

        for agent in self.registry.get_all_agents():
            # Check if agent has reached daily limit
            if self._has_reached_daily_limit(agent.agent_id):
                continue

            # Calculate expertise match score
            expertise_score = self._calculate_expertise_match(agent, relevant_expertise)

            # Get relevance from learning system
            knowledge = await self.learning_system.get_relevant_knowledge(agent_id=agent.agent_id, topic=topic, limit=5)

            knowledge_score = min(len(knowledge) / 5.0, 1.0)  # Normalize to 0-1

            # Calculate overall score
            overall_score = expertise_score * 0.6 + knowledge_score * 0.3 + agent.confidence_score * 0.1

            if overall_score >= self.expertise_threshold:
                scored_agents.append((agent, overall_score))

        # Sort by score and select top agents
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        selected = [agent for agent, score in scored_agents[:max_agents]]

        logger.info("Selected %s agents for topic '%s': %s", len(selected), topic, [a.name for a in selected])
        return selected

    async def select_debate_participants(self, topic: str, platform: str) -> tuple[AgentProfile, AgentProfile]:
        """
        Select two agents for a debate on a topic.

        Selects agents with different perspectives to create
        interesting and productive debates.
        """
        selected = await self.select_agents_for_topic(topic, platform, max_agents=5)

        if len(selected) < 2:
            logger.warning("Not enough agents for debate on topic '%s'", topic)
            # Return the two best available
            return selected[0], selected[1] if len(selected) > 1 else selected[0]

        # Select two agents with different primary expertise areas
        agent1 = selected[0]

        for agent in selected[1:]:
            if agent.expertise_areas[0] != agent1.expertise_areas[0]:
                agent2 = agent
                break
        else:
            # If all have same expertise, pick second best
            agent2 = selected[1]

        logger.info("Selected debate participants: %s vs %s", agent1.name, agent2.name)
        return agent1, agent2

    async def rotate_agents(self):
        """
        Perform agent rotation.

        Resets daily participation counts and rotates availability
        to ensure fair agent participation.
        """
        now = datetime.now(UTC)

        if now - self.last_rotation < self.rotation_interval:
            return

        # Reset daily counts
        self.daily_participation.clear()
        self.last_rotation = now

        logger.info("Agent rotation completed")

    def _extract_expertise_from_topic(self, topic: str) -> list[ExpertiseArea]:
        """Extract relevant expertise areas from a topic"""
        topic_lower = topic.lower()

        # Keyword to expertise mapping
        expertise_keywords = {
            ExpertiseArea.ETHICS: [
                "ethics",
                "ethical",
                "moral",
                "right",
                "wrong",
                "principle",
            ],
            ExpertiseArea.EMOTIONAL_INTELLIGENCE: [
                "emotion",
                "feel",
                "empathy",
                "sentiment",
                "mood",
            ],
            ExpertiseArea.TECHNICAL_ARCHITECTURE: [
                "technical",
                "architecture",
                "system",
                "infrastructure",
                "code",
            ],
            ExpertiseArea.STRATEGIC_PLANNING: [
                "strategy",
                "plan",
                "roadmap",
                "vision",
                "future",
            ],
            ExpertiseArea.CREATIVITY: [
                "creative",
                "design",
                "innovate",
                "art",
                "novel",
            ],
            ExpertiseArea.SYSTEM_MONITORING: [
                "monitor",
                "observe",
                "track",
                "metric",
                "health",
            ],
            ExpertiseArea.SECURITY: [
                "security",
                "protect",
                "safe",
                "vulnerability",
                "threat",
            ],
            ExpertiseArea.KNOWLEDGE_MANAGEMENT: [
                "knowledge",
                "learn",
                "remember",
                "store",
                "retrieve",
            ],
            ExpertiseArea.PHILOSOPHY: [
                "philosophy",
                "meaning",
                "existence",
                "coordination",
                "wisdom",
            ],
            ExpertiseArea.COLLABORATION: [
                "collaborate",
                "team",
                "together",
                "community",
                "shared",
            ],
            ExpertiseArea.META_COGNITION: [
                "meta",
                "self-aware",
                "reflect",
                "cognitive",
                "think about thinking",
            ],
            ExpertiseArea.PROBLEM_SOLVING: [
                "solve",
                "problem",
                "solution",
                "fix",
                "resolve",
            ],
            ExpertiseArea.RECOVERY: [
                "recover",
                "resilience",
                "backup",
                "restore",
                "heal",
            ],
            ExpertiseArea.DESIGN: [
                "design",
                "ui",
                "ux",
                "interface",
                "user experience",
            ],
            ExpertiseArea.WISDOM: ["wise", "wisdom", "guidance", "advice", "insight"],
        }

        relevant_expertise = []
        for expertise, keywords in expertise_keywords.items():
            if any(keyword in topic_lower for keyword in keywords):
                relevant_expertise.append(expertise)

        return relevant_expertise if relevant_expertise else [ExpertiseArea.WISDOM]

    def _calculate_expertise_match(self, agent: AgentProfile, required_expertise: list[ExpertiseArea]) -> float:
        """Calculate how well an agent matches required expertise"""
        if not required_expertise:
            return 0.5

        matches = sum(1 for e in required_expertise if e in agent.expertise_areas)
        return matches / len(required_expertise)

    def _has_reached_daily_limit(self, agent_id: str) -> bool:
        """Check if agent has reached daily participation limit"""
        daily_count = self.daily_participation.get(agent_id, 0)
        return daily_count >= self.max_participations_per_day

    def record_participation(self, agent_id: str):
        """Record that an agent participated"""
        self.daily_participation[agent_id] = self.daily_participation.get(agent_id, 0) + 1
        self.registry.update_participation(agent_id)

    def get_statistics(self) -> dict:
        """Get orchestrator statistics"""
        return {
            "total_agents": len(self.registry.agents),
            "daily_participation": self.daily_participation,
            "last_rotation": self.last_rotation.isoformat(),
            "rotation_interval_seconds": self.rotation_interval.total_seconds(),
            "max_participations_per_day": self.max_participations_per_day,
        }


# Singleton instances
_agent_registry: AgentRegistry | None = None
_agent_orchestrator: AgentOrchestrator | None = None


def get_agent_registry() -> AgentRegistry:
    """Get or create agent registry singleton"""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = AgentRegistry()
    return _agent_registry


def get_agent_orchestrator() -> AgentOrchestrator:
    """Get or create agent orchestrator singleton"""
    global _agent_orchestrator
    if _agent_orchestrator is None:
        registry = get_agent_registry()
        _agent_orchestrator = AgentOrchestrator(registry)
    return _agent_orchestrator
