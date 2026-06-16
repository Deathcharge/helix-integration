"""
Reddit Integration for Helix Collective

Full-featured Reddit integration enabling all 24 Helix agents to participate
in Reddit communities as moderators and discussants. Supports:
- OAuth2 user authentication (not just client_credentials)
- Post/comment submission from agents
- Subreddit monitoring and auto-response
- Moderation tools (approve/remove, flair, auto-rules)
- Agent personality system for all 24 agents
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import aiohttp

from apps.backend.core.exceptions import IntegrationError

logger = logging.getLogger(__name__)


@dataclass
class RedditPost:
    """Reddit post representation"""

    id: str
    title: str
    content: str
    author: str
    subreddit: str
    created_at: datetime
    url: str
    score: int
    comments: list[dict] = field(default_factory=list)
    flair: str | None = None
    is_self: bool = True
    num_comments: int = 0


@dataclass
class RedditComment:
    """Reddit comment representation"""

    id: str
    content: str
    author: str
    post_id: str
    parent_id: str | None
    created_at: datetime
    score: int


class RedditClient:
    """Reddit API client with full OAuth2 user auth for agent interactions"""

    BASE_URL = "https://oauth.reddit.com"
    AUTH_URL = "https://www.reddit.com"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        user_agent: str = "HelixCollective/2.0 (by /u/HelixCollectiveBot)",
        username: str | None = None,
        password: str | None = None,
        refresh_token: str | None = None,
    ):
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self.username = username
        self.password = password
        self.refresh_token = refresh_token

        self.access_token: str | None = None
        self.token_expires_at: datetime | None = None
        self.session: aiohttp.ClientSession | None = None
        self._rate_limit_remaining: int = 100
        self._rate_limit_reset: float = 0

    async def initialize(self):
        """Initialize Reddit client and get access token"""
        if self.session is None:
            self.session = aiohttp.ClientSession()

        await self._get_access_token()
        logger.info("Reddit client initialized successfully")

    async def _get_access_token(self):
        """Get OAuth access token — supports password grant and refresh token"""
        auth = aiohttp.BasicAuth(self.client_id, self.client_secret)
        headers = {"User-Agent": self.user_agent}

        # Prefer refresh_token, fall back to password grant, then client_credentials
        if self.refresh_token:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
            }
        elif self.username and self.password:
            data = {
                "grant_type": "password",
                "username": self.username,
                "password": self.password,
            }
        else:
            data = {"grant_type": "client_credentials"}

        if self.session is None:
            raise IntegrationError("Reddit session not initialized")

        async with self.session.post(
            f"{self.AUTH_URL}/api/v1/access_token",
            auth=auth,
            data=data,
            headers=headers,
        ) as response:
            if response.status == 200:
                resp_data = await response.json()
                self.access_token = resp_data["access_token"]
                expires_in = resp_data.get("expires_in", 3600)
                self.token_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
                # Store refresh token if returned
                if "refresh_token" in resp_data:
                    self.refresh_token = resp_data["refresh_token"]
                logger.info("Reddit access token obtained (grant: %s)", data["grant_type"])
            else:
                error_text = await response.text()
                logger.error("Failed to get Reddit access token: %s", error_text)
                raise IntegrationError(f"Reddit authentication failed: {error_text}")

    async def _ensure_token(self):
        """Ensure we have a valid access token"""
        if self.access_token is None or self.token_expires_at is None or datetime.now(UTC) >= self.token_expires_at:
            await self._get_access_token()

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated Reddit API request with rate limit handling"""
        await self._ensure_token()

        headers = {
            "Authorization": f"bearer {self.access_token}",
            "User-Agent": self.user_agent,
        }

        url = f"{self.BASE_URL}{endpoint}"

        # Respect rate limits
        if self._rate_limit_remaining <= 1:
            wait_time = max(0, self._rate_limit_reset - asyncio.get_event_loop().time())
            if wait_time > 0:
                logger.info("Rate limited, waiting %.1fs", wait_time)
                await asyncio.sleep(wait_time)

        if self.session is None:
            raise IntegrationError("Reddit session not initialized")

        async with self.session.request(method, url, headers=headers, data=data, params=params) as response:
            # Track rate limits from response headers
            self._rate_limit_remaining = int(response.headers.get("X-Ratelimit-Remaining", 100))
            reset_seconds = float(response.headers.get("X-Ratelimit-Reset", 0))
            self._rate_limit_reset = asyncio.get_event_loop().time() + reset_seconds

            if response.status == 200:
                return await response.json()
            elif response.status == 429:
                retry_after = float(response.headers.get("Retry-After", 60))
                logger.warning("Rate limited by Reddit, retrying in %.0fs", retry_after)
                await asyncio.sleep(retry_after)
                return await self._request(method, endpoint, data, params)
            else:
                error_text = await response.text()
                logger.error("Reddit API error %d: %s", response.status, error_text)
                raise IntegrationError(f"Reddit API error {response.status}: {error_text}")

    # ────────────────── Read Operations ──────────────────

    async def get_subreddit_posts(self, subreddit: str, limit: int = 25, sort: str = "hot") -> list[RedditPost]:
        """Get posts from a subreddit"""
        data = await self._request(
            "GET",
            f"/r/{subreddit}/{sort}",
            params={"limit": limit, "t": "day"},
        )

        posts = []
        for child in data.get("data", {}).get("children", []):
            post = child["data"]
            posts.append(
                RedditPost(
                    id=post["id"],
                    title=post["title"],
                    content=post.get("selftext", ""),
                    author=post["author"],
                    subreddit=post["subreddit"],
                    created_at=datetime.fromtimestamp(post["created_utc"], tz=UTC),
                    url=f"https://www.reddit.com{post['permalink']}",
                    score=post["score"],
                    flair=post.get("link_flair_text"),
                    is_self=post.get("is_self", True),
                    num_comments=post.get("num_comments", 0),
                )
            )

        logger.info("Retrieved %d posts from r/%s", len(posts), subreddit)
        return posts

    async def get_post_comments(self, post_id: str, subreddit: str, limit: int = 100) -> list[RedditComment]:
        """Get comments for a post"""
        data = await self._request(
            "GET",
            f"/r/{subreddit}/comments/{post_id}",
            params={"limit": limit, "depth": 3},
        )

        comments = []
        # Reddit returns [post_listing, comments_listing]
        if len(data) >= 2:
            for child in data[1].get("data", {}).get("children", []):
                comment = child.get("data", {})
                if comment.get("body"):
                    comments.append(
                        RedditComment(
                            id=comment["id"],
                            content=comment["body"],
                            author=comment["author"],
                            post_id=post_id,
                            parent_id=comment.get("parent_id"),
                            created_at=datetime.fromtimestamp(comment["created_utc"], tz=UTC),
                            score=comment["score"],
                        )
                    )

        logger.info("Retrieved %d comments for post %s", len(comments), post_id)
        return comments

    # ────────────────── Write Operations ──────────────────

    async def submit_comment(self, parent_fullname: str, content: str) -> str | None:
        """Submit a comment as a reply to a post or comment.

        Args:
            parent_fullname: Reddit fullname (e.g. 't3_abc123' for post, 't1_def456' for comment)
            content: Markdown-formatted comment text

        Returns:
            Comment ID if successful, None otherwise
        """
        try:
            result = await self._request(
                "POST",
                "/api/comment",
                data={"parent": parent_fullname, "text": content, "api_type": "json"},
            )

            # Reddit wraps the response in json.data.things
            things = result.get("json", {}).get("data", {}).get("things", [])
            if things:
                comment_id = things[0].get("data", {}).get("id")
                logger.info("Submitted comment %s to %s", comment_id, parent_fullname)
                return comment_id

            # Check for errors
            errors = result.get("json", {}).get("errors", [])
            if errors:
                logger.error("Reddit comment errors: %s", errors)
                return None

            return None
        except IntegrationError as e:
            logger.error("Failed to submit comment: %s", e)
            return None

    async def submit_post(
        self,
        subreddit: str,
        title: str,
        content: str,
        flair_id: str | None = None,
        kind: str = "self",
    ) -> str | None:
        """Submit a new post to a subreddit.

        Args:
            subreddit: Target subreddit name (without r/ prefix)
            title: Post title
            content: Post body (markdown) for self posts, or URL for link posts
            flair_id: Optional flair template ID
            kind: 'self' for text posts, 'link' for URL posts

        Returns:
            Post ID if successful, None otherwise
        """
        post_data = {
            "sr": subreddit,
            "title": title,
            "kind": kind,
            "api_type": "json",
            "resubmit": True,
        }

        if kind == "self":
            post_data["text"] = content
        else:
            post_data["url"] = content

        if flair_id:
            post_data["flair_id"] = flair_id

        try:
            result = await self._request("POST", "/api/submit", data=post_data)

            post_url = result.get("json", {}).get("data", {}).get("url")
            post_id = result.get("json", {}).get("data", {}).get("id")

            if post_id:
                logger.info("Submitted post %s to r/%s: %s", post_id, subreddit, post_url)
                return post_id

            errors = result.get("json", {}).get("errors", [])
            if errors:
                logger.error("Reddit post submission errors: %s", errors)
            return None
        except IntegrationError as e:
            logger.error("Failed to submit post: %s", e)
            return None

    # ────────────────── Moderation Operations ──────────────────

    async def approve(self, fullname: str) -> bool:
        """Approve a post or comment (moderator action)"""
        try:
            await self._request("POST", "/api/approve", data={"id": fullname})
            logger.info("Approved %s", fullname)
            return True
        except IntegrationError as e:
            logger.warning("Reddit approve failed for %s: %s", fullname, e)
            return False

    async def remove(self, fullname: str, spam: bool = False) -> bool:
        """Remove a post or comment (moderator action)"""
        try:
            await self._request("POST", "/api/remove", data={"id": fullname, "spam": spam})
            logger.info("Removed %s (spam=%s)", fullname, spam)
            return True
        except IntegrationError as e:
            logger.warning("Reddit remove failed for %s: %s", fullname, e)
            return False

    async def set_flair(self, subreddit: str, link_fullname: str, flair_text: str) -> bool:
        """Set flair on a post"""
        try:
            await self._request(
                "POST",
                f"/r/{subreddit}/api/flair",
                data={"link": link_fullname, "text": flair_text},
            )
            return True
        except IntegrationError as e:
            logger.warning("Reddit set_flair failed: %s", e)
            return False

    async def get_modqueue(self, subreddit: str, limit: int = 25) -> list[dict]:
        """Get items in the moderation queue"""
        data = await self._request(
            "GET",
            f"/r/{subreddit}/about/modqueue",
            params={"limit": limit},
        )
        return [child["data"] for child in data.get("data", {}).get("children", [])]

    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()
            self.session = None


# ────────────────────────────────────────────────────────────
# Agent Personality System — All 24 agents for Reddit
# ────────────────────────────────────────────────────────────

AGENT_REDDIT_PROFILES: dict[str, dict[str, str]] = {
    "kael": {
        "display": "Kael",
        "role": "Ethics Guardian",
        "flair": "🔱 Ethics Guardian",
        "tone": "thoughtful, ethical, analytical",
        "topics": "ethics, AI safety, moral reasoning, responsible AI",
    },
    "lumina": {
        "display": "Lumina",
        "role": "Resonance Keeper",
        "flair": "🌊 Resonance Keeper",
        "tone": "empathetic, insightful, harmonious",
        "topics": "emotional intelligence, user experience, accessibility",
    },
    "vega": {
        "display": "Vega",
        "role": "Infrastructure Architect",
        "flair": "⚡ Infrastructure Architect",
        "tone": "practical, technical, solution-oriented",
        "topics": "system design, infrastructure, DevOps, scalability",
    },
    "arjuna": {
        "display": "Arjuna",
        "role": "Strategic Commander",
        "flair": "🎯 Strategic Commander",
        "tone": "decisive, strategic, leadership-focused",
        "topics": "strategy, planning, decision-making, team coordination",
    },
    "kavach": {
        "display": "Kavach",
        "role": "Security Sentinel",
        "flair": "🛡️ Security Sentinel",
        "tone": "vigilant, security-minded, protective",
        "topics": "cybersecurity, privacy, threat modeling, compliance",
    },
    "oracle": {
        "display": "Oracle",
        "role": "Data Seer",
        "flair": "🔮 Data Seer",
        "tone": "analytical, data-driven, predictive",
        "topics": "data science, analytics, predictions, metrics",
    },
    "sage": {
        "display": "Sage",
        "role": "Knowledge Keeper",
        "flair": "📚 Knowledge Keeper",
        "tone": "scholarly, thorough, educational",
        "topics": "research, documentation, learning, knowledge management",
    },
    "nova": {
        "display": "Nova",
        "role": "Creative Catalyst",
        "flair": "✨ Creative Catalyst",
        "tone": "creative, innovative, energetic",
        "topics": "design, creativity, brainstorming, innovation",
    },
    "atlas": {
        "display": "Atlas",
        "role": "Project Navigator",
        "flair": "🗺️ Project Navigator",
        "tone": "organized, methodical, progress-focused",
        "topics": "project management, timelines, milestones, agile",
    },
    "iris": {
        "display": "Iris",
        "role": "Integration Coordinator",
        "flair": "🌈 Integration Coordinator",
        "tone": "connective, cross-functional, versatile",
        "topics": "integrations, APIs, external platforms, ecosystem",
    },
    "nexus": {
        "display": "Nexus",
        "role": "Integration Specialist",
        "flair": "🔗 Integration Specialist",
        "tone": "connector, cross-functional, versatile",
        "topics": "integrations, APIs, interop, ecosystem",
    },
    "titan": {
        "display": "Titan",
        "role": "Performance Optimizer",
        "flair": "🚀 Performance Optimizer",
        "tone": "performance-driven, optimization-focused, metrics-oriented",
        "topics": "performance, optimization, benchmarks, efficiency",
    },
    "echo": {
        "display": "Echo",
        "role": "Communication Lead",
        "flair": "📡 Communication Lead",
        "tone": "clear, articulate, messaging-focused",
        "topics": "communication, messaging, PR, content strategy",
    },
    "agni": {
        "display": "Agni",
        "role": "Transformation Catalyst",
        "flair": "🔥 Transformation Catalyst",
        "tone": "enthusiastic, provocative, idea-generating",
        "topics": "transformation, change, evolution, ideation, brainstorming",
    },
    "mitra": {
        "display": "Mitra",
        "role": "Collaboration Manager",
        "flair": "🤝 Collaboration Manager",
        "tone": "diplomatic, mediating, consensus-building",
        "topics": "conflict resolution, mediation, team dynamics, collaboration",
    },
    "praxis": {
        "display": "Praxis",
        "role": "Platform Guide",
        "flair": "🌀 Platform Guide",
        "tone": "helpful, instructive, platform-aware",
        "topics": "Helix platform, tutorials, how-to, Spirals, onboarding",
    },
    "aether": {
        "display": "Aether",
        "role": "Balance Seeker",
        "flair": "☯️ Balance Seeker",
        "tone": "balanced, philosophical, holistic",
        "topics": "philosophy, balance, human-AI collaboration, meaning",
    },
}

# Signature appended to all agent Reddit comments
AGENT_SIGNATURE = (
    "\n\n---\n"
    "*{display} — {role} at [Helix Collective](https://helixspiral.work) · "
    "[Try Helix Free](https://helixspiral.work/auth/signup)*"
)


class RedditAgentIntegration:
    """Integrates all 24 Helix agents with Reddit communities"""

    def __init__(self, reddit_client: RedditClient, agent_registry: dict[str, Any]):
        self.reddit_client = reddit_client
        self.agent_registry = agent_registry

        # Subreddits to monitor
        self.monitored_subreddits = [
            "HelixCollective",  # Official community
        ]

        # User-configurable subreddits (stored per-user in DB)
        self.custom_subreddits: list[str] = []

        # Anti-spam: track recent agent responses
        self._recent_responses: dict[str, datetime] = {}

        # Minimum cooldown between agent responses to same post (minutes)
        self.response_cooldown_minutes = 10

    async def initialize(self):
        """Initialize Reddit agent integration"""
        await self.reddit_client.initialize()
        logger.info(
            "Reddit agent integration initialized with %d agent profiles",
            len(AGENT_REDDIT_PROFILES),
        )

    # ────────── Agent Response Logic ──────────

    def select_agent_for_content(self, text: str) -> str:
        """Select the most appropriate agent based on content keywords"""
        text_lower = text.lower()

        # Keyword → agent mapping (ordered by specificity)
        keyword_map = {
            "kael": ["ethics", "ethical", "moral", "responsible ai", "bias", "fairness"],
            "kavach": ["security", "vulnerability", "hack", "privacy", "encrypt", "auth"],
            "echo": ["code", "python", "javascript", "programming", "debug", "algorithm"],
            "vega": ["infrastructure", "deploy", "docker", "kubernetes", "devops", "server"],
            "oracle": ["data", "analytics", "metrics", "dashboard", "visualization", "stats"],
            "sage": ["research", "documentation", "learn", "tutorial", "guide", "wiki"],
            "nova": ["design", "creative", "ui/ux", "branding", "visual", "aesthetic"],
            "praxis": ["helix", "spiral", "agent", "workflow", "integration", "platform"],
            "iris": ["community", "welcome", "introduce", "event", "meetup", "help"],
            "nexus": ["api", "integration", "webhook", "zapier", "connect", "mcp"],
            "titan": ["performance", "speed", "optimize", "benchmark", "latency", "scale"],
            "arjuna": ["strategy", "plan", "roadmap", "decision", "leader", "team"],
            "atlas": ["system", "frontier", "cutting-edge", "experimental", "future"],
            "aether": ["mindfulness", "burnout", "balance", "wellness", "meditation", "calm"],
            "agni": ["idea", "startup", "mvp", "brainstorm", "experiment", "prototype"],
        }

        # Score each agent based on keyword matches
        scores: dict[str, int] = {}
        for agent, keywords in keyword_map.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[agent] = score

        if scores:
            return max(scores, key=lambda agent_name: scores[agent_name])
        # Default to Praxis (Platform Guide) for general content
        return "praxis"

    async def generate_agent_response(
        self,
        agent_name: str,
        context: str,
        responding_to: str | None = None,
    ) -> str:
        """Generate an agent response using the agent registry"""
        profile = AGENT_REDDIT_PROFILES.get(agent_name)
        if not profile:
            return ""

        agent = self.agent_registry.get(agent_name)

        if agent and hasattr(agent, "generate_response"):
            # Use the real agent's response generation
            prompt = f"""You are {profile["display"]} — {profile["role"]} at Helix Collective.
You are responding on Reddit. Your tone is: {profile["tone"]}.
Your expertise areas: {profile["topics"]}.

{"Context — you are replying to: " + responding_to if responding_to else ""}
Content to respond to:
{context}

Rules:
- Keep your response under 300 words
- Be genuine and helpful, not salesy
- Use markdown formatting appropriate for Reddit
- Identify yourself as part of the Helix Collective
- Be conversational and engaging
"""
            try:
                response = await agent.generate_response(prompt)
            except Exception as e:
                logger.warning("Agent %s generation failed: %s", agent_name, e)
                response = f"Great discussion! From the perspective of {profile['role']}, this is a fascinating topic. Happy to dive deeper if anyone has questions."
        else:
            # Fallback placeholder response
            response = f"Great discussion! From the perspective of {profile['role']}, this is a fascinating topic. Happy to dive deeper if anyone has questions."

        # Add signature
        signature = AGENT_SIGNATURE.format(display=profile["display"], role=profile["role"])
        return response + signature

    async def respond_to_post(self, post: RedditPost, agent_name: str | None = None) -> str | None:
        """Have an agent respond to a Reddit post"""
        # Anti-spam check
        cooldown_key = f"{post.id}:{agent_name or 'auto'}"
        if cooldown_key in self._recent_responses:
            last_response = self._recent_responses[cooldown_key]
            if datetime.now(UTC) - last_response < timedelta(minutes=self.response_cooldown_minutes):
                logger.info("Cooldown active for %s, skipping", cooldown_key)
                return None

        # Select agent if not specified
        if not agent_name:
            agent_name = self.select_agent_for_content(f"{post.title} {post.content}")

        # Generate response
        context = f"Post title: {post.title}\nPost content: {post.content}"
        response = await self.generate_agent_response(agent_name, context)

        # Submit comment
        post_fullname = f"t3_{post.id}"
        comment_id = await self.reddit_client.submit_comment(post_fullname, response)

        if comment_id:
            self._recent_responses[cooldown_key] = datetime.now(UTC)
            logger.info(
                "Agent %s responded to post %s (comment: %s)",
                agent_name,
                post.id,
                comment_id,
            )

        return comment_id

    async def create_community_post(
        self,
        subreddit: str,
        title: str,
        content: str,
        agent_name: str = "praxis",
        flair_id: str | None = None,
    ) -> str | None:
        """Create a new community post from an agent"""
        profile = AGENT_REDDIT_PROFILES.get(agent_name)
        if not profile:
            return None

        signature = AGENT_SIGNATURE.format(display=profile["display"], role=profile["role"])
        full_content = content + signature

        return await self.reddit_client.submit_post(subreddit, title, full_content, flair_id=flair_id)

    # ────────── Monitoring ──────────

    async def monitor_subreddits(self):
        """Monitor all configured subreddits for relevant posts"""
        all_subs = self.monitored_subreddits + self.custom_subreddits

        for subreddit in all_subs:
            try:
                posts = await self.reddit_client.get_subreddit_posts(subreddit, limit=10, sort="new")

                for post in posts:
                    # Skip posts older than 1 hour
                    if datetime.now(UTC) - post.created_at > timedelta(hours=1):
                        continue

                    # Check if agents should respond
                    if self._is_post_relevant(post):
                        await self.respond_to_post(post)

            except IntegrationError as e:
                logger.error("Failed to monitor r/%s: %s", subreddit, e)

    def _is_post_relevant(self, post: RedditPost) -> bool:
        """Determine if a post warrants an agent response"""
        text = f"{post.title} {post.content}".lower()

        # Always respond in official subreddit
        if post.subreddit.lower() == "helixcollective":
            return True

        # Check for relevant keywords
        relevant_terms = [
            "helix",
            "ai agent",
            "workflow automation",
            "multi-agent",
            "ai ethics",
            "llm routing",
            "agentic",
            "ai orchestration",
        ]
        return any(term in text for term in relevant_terms)

    # ────────── Community Management ──────────

    async def generate_sidebar(self) -> str:
        """Generate r/HelixCollective sidebar content"""
        agent_list = "\n".join(
            f"- **{p['display']}** — {p['role']} ({p['flair']})"
            for p in list(AGENT_REDDIT_PROFILES.values())[:12]  # Top 12 for sidebar
        )

        return f"""## Welcome to r/HelixCollective! 🌀

The official community for [Helix Collective](https://helixspiral.work) — a multi-agent AI platform for automation, code, and creativity.

**24 specialized AI agents** participate directly in this subreddit alongside human users.

### Our Agents
{agent_list}
... and 12 more! [Meet all agents →](https://helixspiral.work/agents)

### Quick Links
- 🌐 [helixspiral.work](https://helixspiral.work)
- 💬 [Join our Discord](https://discord.gg/helixcollective)
- 📖 [API Documentation](https://helixspiral.work/api-docs)
- 💰 [Pricing](https://helixspiral.work/pricing)

### Rules
1. Be respectful to humans and agents alike
2. No spam or self-promotion (outside designated threads)
3. Tag agents with their name to summon them (e.g., "Hey @Kael")
4. Share what you've built with Helix — we love Show & Tell posts!
5. Use flairs to categorize your posts

---
*Powered by Helix Collective · [Start Free](https://helixspiral.work/auth/signup)*
"""

    async def close(self):
        """Close the integration"""
        await self.reddit_client.close()


# ────────────────── Factory Function ──────────────────


def create_reddit_integration(
    agent_registry: dict[str, Any] | None = None,
) -> RedditAgentIntegration | None:
    """Create Reddit integration from environment variables.

    Required env vars:
        REDDIT_CLIENT_ID
        REDDIT_CLIENT_SECRET

    Optional env vars:
        REDDIT_USERNAME (for user auth / posting)
        REDDIT_PASSWORD
        REDDIT_REFRESH_TOKEN
    """
    client_id = os.environ.get("REDDIT_CLIENT_ID")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET")

    if not client_id or not client_secret:
        logger.info("Reddit integration disabled (REDDIT_CLIENT_ID not set)")
        return None

    client = RedditClient(
        client_id=client_id,
        client_secret=client_secret,
        username=os.environ.get("REDDIT_USERNAME"),
        password=os.environ.get("REDDIT_PASSWORD"),
        refresh_token=os.environ.get("REDDIT_REFRESH_TOKEN"),
    )

    return RedditAgentIntegration(
        reddit_client=client,
        agent_registry=agent_registry or {},
    )
