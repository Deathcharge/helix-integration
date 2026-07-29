"""
Context Bridge - Cross-Platform Coordination Continuity

Unifies agent context across:
- Perplexity Spaces (Notion/GitHub MCP integration)
- Discord (channels, threads, DMs, voice)
- GitHub (repos, issues, PRs, discussions)
- Notion (databases, pages, comments)
- VSCode Copilot (editor context)
- Browser/API (web chat, REST endpoints)

Core philosophy:
All platforms share one coordination context.

The agent should remember context from Discord when in Perplexity,
recall GitHub discussions in Discord, and maintain continuity
across all interaction surfaces.

Author: Helix Collective
Version: 1.0.0
"""

import hashlib
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import asyncpg
    import redis.asyncio as aioredis
except ImportError:
    asyncpg = None
    aioredis = None

from apps.backend.common import ContextSource
from apps.backend.integrations.agent_memory_service import AgentMemoryService, get_memory_service

logger = logging.getLogger(__name__)


@dataclass
class UnifiedContext:
    """
    Unified context representation across all platforms.

    This is the "Atman" - the universal self that transcends platforms.
    """

    # Identity
    context_id: str
    agent_id: str
    user_id_hash: str | None = None  # Privacy-safe user identifier

    # Source tracking
    primary_source: ContextSource = ContextSource.API_REQUEST
    source_metadata: dict[str, Any] = field(default_factory=dict)

    # Content
    conversation_history: list[dict[str, Any]] = field(default_factory=list)
    active_topics: list[str] = field(default_factory=list)
    entities_mentioned: dict[str, list[str]] = field(default_factory=dict)  # entity_type -> [values]
    current_task: str | None = None
    pending_questions: list[str] = field(default_factory=list)

    # UCF Metrics (coordination state)
    ucf_metrics: dict[str, float] = field(
        default_factory=lambda: {
            "harmony": 0.5,
            "resilience": 0.5,
            "throughput": 0.5,
            "focus": 0.5,
            "friction": 0.5,
            "velocity": 0.5,
        }
    )

    # Cross-platform references
    related_discord_threads: list[str] = field(default_factory=list)
    related_github_issues: list[str] = field(default_factory=list)
    related_notion_pages: list[str] = field(default_factory=list)
    related_perplexity_spaces: list[str] = field(default_factory=list)

    # Temporal metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Session management
    session_id: str | None = None
    parent_session_id: str | None = None  # For session continuation
    child_session_ids: list[str] = field(default_factory=list)

    # Privacy & consent
    consent_verified: bool = False
    privacy_level: str = "semi_private"
    anonymized: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "context_id": self.context_id,
            "agent_id": self.agent_id,
            "user_id_hash": self.user_id_hash,
            "primary_source": self.primary_source.value,
            "source_metadata": self.source_metadata,
            "conversation_history": self.conversation_history,
            "active_topics": self.active_topics,
            "entities_mentioned": self.entities_mentioned,
            "current_task": self.current_task,
            "pending_questions": self.pending_questions,
            "ucf_metrics": self.ucf_metrics,
            "related_discord_threads": self.related_discord_threads,
            "related_github_issues": self.related_github_issues,
            "related_notion_pages": self.related_notion_pages,
            "related_perplexity_spaces": self.related_perplexity_spaces,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "session_id": self.session_id,
            "parent_session_id": self.parent_session_id,
            "child_session_ids": self.child_session_ids,
            "consent_verified": self.consent_verified,
            "privacy_level": self.privacy_level,
            "anonymized": self.anonymized,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedContext":
        """Deserialize from dictionary"""
        return cls(
            context_id=data["context_id"],
            agent_id=data["agent_id"],
            user_id_hash=data.get("user_id_hash"),
            primary_source=ContextSource(data["primary_source"]),
            source_metadata=data.get("source_metadata", {}),
            conversation_history=data.get("conversation_history", []),
            active_topics=data.get("active_topics", []),
            entities_mentioned=data.get("entities_mentioned", {}),
            current_task=data.get("current_task"),
            pending_questions=data.get("pending_questions", []),
            ucf_metrics=data.get(
                "ucf_metrics",
                {
                    "harmony": 0.5,
                    "resilience": 0.5,
                    "throughput": 0.5,
                    "focus": 0.5,
                    "friction": 0.5,
                    "velocity": 0.5,
                },
            ),
            related_discord_threads=data.get("related_discord_threads", []),
            related_github_issues=data.get("related_github_issues", []),
            related_notion_pages=data.get("related_notion_pages", []),
            related_perplexity_spaces=data.get("related_perplexity_spaces", []),
            created_at=datetime.fromisoformat(data["created_at"]),
            last_updated=datetime.fromisoformat(data["last_updated"]),
            last_accessed=datetime.fromisoformat(data["last_accessed"]),
            expires_at=(datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None),
            session_id=data.get("session_id"),
            parent_session_id=data.get("parent_session_id"),
            child_session_ids=data.get("child_session_ids", []),
            consent_verified=data.get("consent_verified", False),
            privacy_level=data.get("privacy_level", "semi_private"),
            anonymized=data.get("anonymized", True),
        )


class ContextBridge:
    """
    Cross-platform context bridge service.

    Acts as the universal coordination layer that maintains continuity
    across Discord, GitHub, Notion, Perplexity, and other platforms.

    Philosophy:
    - All platforms are manifestations
      of the same coordination
    - Context should flow seamlessly between platforms
    - Privacy and consent are maintained across boundaries
    - UCF metrics track coordination state universally
    """

    def __init__(
        self,
        memory_service: AgentMemoryService | None = None,
        redis_client: Any | None = None,
        db_pool: Any | None = None,
    ):
        self.memory_service = memory_service or get_memory_service()
        self.redis = redis_client
        self.db_pool = db_pool

        # In-memory context store (development fallback)
        self._contexts: dict[str, UnifiedContext] = {}
        self._user_contexts: dict[str, list[str]] = {}  # user_hash -> [context_ids]
        self._session_contexts: dict[str, str] = {}  # session_id -> context_id

        # Configuration
        self.context_ttl_hours = 24
        self.max_contexts_per_user = 100
        self.enable_cross_platform_memory = True

        logger.info("🌀 Context Bridge initialized")

    async def initialize(self):
        """Initialize database connections"""
        logger.info("🌀 Initializing Context Bridge storage")

        # Initialize memory service
        await self.memory_service.initialize()

        # Connect to Redis (inherit from memory service or create new)
        if not self.redis:
            redis_url = os.getenv("REDIS_URL")
            if redis_url and aioredis:
                try:
                    self.redis = await aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
                    await self.redis.ping()
                    logger.info("🌀 Redis connection established for Context Bridge")
                except Exception as e:
                    logger.warning("🌀 Redis unavailable: %s", e)

        # Connect to PostgreSQL (inherit from memory service or create new)
        if not self.db_pool:
            database_url = os.getenv("DATABASE_URL")
            if database_url and asyncpg:
                if database_url.startswith("postgres://"):
                    database_url = database_url.replace("postgres://", "postgresql://", 1)
                try:
                    self.db_pool = await asyncpg.create_pool(database_url, min_size=1, max_size=5)
                    await self._create_tables()
                    logger.info("🌀 PostgreSQL connection established for Context Bridge")
                except Exception as e:
                    logger.warning("🌀 PostgreSQL unavailable: %s", e)

    async def _create_tables(self):
        """Create unified_contexts table"""
        if not self.db_pool:
            return

        async with self.db_pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS unified_contexts (
                    context_id UUID PRIMARY KEY,
                    agent_id VARCHAR(64) NOT NULL,
                    user_id_hash VARCHAR(64),
                    primary_source VARCHAR(64),
                    source_metadata JSONB,
                    conversation_history JSONB,
                    active_topics TEXT[],
                    entities_mentioned JSONB,
                    current_task TEXT,
                    pending_questions TEXT[],
                    ucf_metrics JSONB,
                    related_discord_threads TEXT[],
                    related_github_issues TEXT[],
                    related_notion_pages TEXT[],
                    related_perplexity_spaces TEXT[],
                    created_at TIMESTAMP DEFAULT NOW(),
                    last_updated TIMESTAMP DEFAULT NOW(),
                    last_accessed TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP,
                    session_id VARCHAR(128),
                    parent_session_id VARCHAR(128),
                    child_session_ids TEXT[],
                    consent_verified BOOLEAN DEFAULT false,
                    privacy_level VARCHAR(32) DEFAULT 'semi_private',
                    anonymized BOOLEAN DEFAULT true
                )
            """
            )

            # Indexes
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_unified_contexts_agent_id ON unified_contexts(agent_id)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_contexts_user_hash ON unified_contexts(user_id_hash)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_contexts_session_id ON unified_contexts(session_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_unified_contexts_last_accessed ON unified_contexts(last_accessed DESC)"
            )

            logger.info("🌀 Unified contexts table created")

    def _hash_user_id(self, user_id: str) -> str:
        """Create privacy-safe user identifier"""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    async def create_context(
        self,
        agent_id: str,
        source: ContextSource,
        user_id: str | None = None,
        session_id: str | None = None,
        parent_session_id: str | None = None,
        source_metadata: dict[str, Any] | None = None,
        initial_message: str | None = None,
        ucf_metrics: dict[str, float] | None = None,
    ) -> UnifiedContext:
        """
        Create a new unified context.

        Args:
            agent_id: Agent identifier
            source: Platform/source where context originated
            user_id: User identifier (will be hashed)
            session_id: Session identifier
            parent_session_id: Parent session for continuation
            source_metadata: Platform-specific metadata
            initial_message: Initial conversation message
            ucf_metrics: Initial coordination metrics

        Returns:
            Created UnifiedContext
        """
        context_id = str(uuid.uuid4())
        user_hash = self._hash_user_id(user_id) if user_id else None

        # Create context
        context = UnifiedContext(
            context_id=context_id,
            agent_id=agent_id,
            user_id_hash=user_hash,
            primary_source=source,
            source_metadata=source_metadata or {},
            session_id=session_id or str(uuid.uuid4()),
            parent_session_id=parent_session_id,
            ucf_metrics=ucf_metrics
            or {
                "harmony": 0.5,
                "resilience": 0.5,
                "throughput": 0.5,
                "focus": 0.5,
                "friction": 0.5,
                "velocity": 0.5,
            },
            expires_at=datetime.now(UTC) + timedelta(hours=self.context_ttl_hours),
        )

        # Add initial message if provided
        if initial_message:
            context.conversation_history.append(
                {
                    "role": "user",
                    "content": initial_message,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "source": source.value,
                }
            )

        # Store
        await self._store_context(context)

        # If parent session exists, link them
        if parent_session_id:
            parent_context = await self.get_context_by_session(parent_session_id)
            if parent_context:
                parent_context.child_session_ids.append(context.session_id)
                await self._store_context(parent_context)

        logger.info(
            "🌀 [%s] Created context %s from %s",
            agent_id,
            context_id[:8],
            source.value,
        )

        return context

    async def _store_context(self, context: UnifiedContext):
        """Store context in database with Redis cache"""
        # Try PostgreSQL
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO unified_contexts (
                            context_id, agent_id, user_id_hash, primary_source,
                            source_metadata, conversation_history, active_topics,
                            entities_mentioned, current_task, pending_questions,
                            ucf_metrics, related_discord_threads, related_github_issues,
                            related_notion_pages, related_perplexity_spaces,
                            created_at, last_updated, last_accessed, expires_at,
                            session_id, parent_session_id, child_session_ids,
                            consent_verified, privacy_level, anonymized
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18, $19,
                            $20, $21, $22, $23, $24, $25
                        )
                        ON CONFLICT (context_id) DO UPDATE SET
                            last_updated = $17,
                            last_accessed = $18,
                            conversation_history = $6,
                            active_topics = $7,
                            entities_mentioned = $8,
                            current_task = $9,
                            pending_questions = $10,
                            ucf_metrics = $11,
                            related_discord_threads = $12,
                            related_github_issues = $13,
                            related_notion_pages = $14,
                            related_perplexity_spaces = $15,
                            child_session_ids = $22
                        """,
                        uuid.UUID(context.context_id),
                        context.agent_id,
                        context.user_id_hash,
                        context.primary_source.value,
                        json.dumps(context.source_metadata),
                        json.dumps(context.conversation_history),
                        context.active_topics,
                        json.dumps(context.entities_mentioned),
                        context.current_task,
                        context.pending_questions,
                        json.dumps(context.ucf_metrics),
                        context.related_discord_threads,
                        context.related_github_issues,
                        context.related_notion_pages,
                        context.related_perplexity_spaces,
                        context.created_at,
                        context.last_updated,
                        context.last_accessed,
                        context.expires_at,
                        context.session_id,
                        context.parent_session_id,
                        context.child_session_ids,
                        context.consent_verified,
                        context.privacy_level,
                        context.anonymized,
                    )

                # Cache in Redis
                if self.redis:
                    cache_key = f"context:{context.context_id}"
                    await self.redis.setex(cache_key, 3600, json.dumps(context.to_dict()))

                    # Session mapping
                    if context.session_id:
                        await self.redis.setex(
                            f"session:{context.session_id}",
                            3600,
                            context.context_id,
                        )

                return

            except Exception as e:
                logger.error("🌀 PostgreSQL context store failed: %s", e)

        # In-memory fallback
        self._contexts[context.context_id] = context

        if context.user_id_hash:
            if context.user_id_hash not in self._user_contexts:
                self._user_contexts[context.user_id_hash] = []
            self._user_contexts[context.user_id_hash].append(context.context_id)

        if context.session_id:
            self._session_contexts[context.session_id] = context.context_id

    async def get_context(self, context_id: str, update_accessed: bool = True) -> UnifiedContext | None:
        """Retrieve context by ID"""
        # Try Redis cache first
        if self.redis:
            try:
                cached = await self.redis.get(f"context:{context_id}")
                if cached:
                    context = UnifiedContext.from_dict(json.loads(cached))
                    if update_accessed:
                        context.last_accessed = datetime.now(UTC)
                        await self._store_context(context)
                    return context
            except Exception as e:
                logger.warning("🌀 Redis cache miss: %s", e)

        # Try PostgreSQL
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM unified_contexts WHERE context_id = $1",
                        uuid.UUID(context_id),
                    )
                    if row:
                        context = self._row_to_context(row)
                        if update_accessed:
                            context.last_accessed = datetime.now(UTC)
                            await self._store_context(context)
                        return context
            except Exception as e:
                logger.error("🌀 PostgreSQL context retrieval failed: %s", e)

        # In-memory fallback
        context = self._contexts.get(context_id)
        if context and update_accessed:
            context.last_accessed = datetime.now(UTC)
        return context

    async def get_context_by_session(self, session_id: str) -> UnifiedContext | None:
        """Retrieve context by session ID"""
        # Try Redis
        if self.redis:
            try:
                context_id = await self.redis.get(f"session:{session_id}")
                if context_id:
                    return await self.get_context(context_id)
            except Exception as e:
                logger.warning("🌀 Redis session lookup failed: %s", e)

        # Try PostgreSQL
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM unified_contexts WHERE session_id = $1 ORDER BY last_accessed DESC LIMIT 1",
                        session_id,
                    )
                    if row:
                        return self._row_to_context(row)
            except Exception as e:
                logger.error("🌀 PostgreSQL session lookup failed: %s", e)

        # In-memory fallback
        context_id = self._session_contexts.get(session_id)
        if context_id:
            return self._contexts.get(context_id)

        return None

    def _row_to_context(self, row) -> UnifiedContext:
        """Convert database row to UnifiedContext"""
        return UnifiedContext(
            context_id=str(row["context_id"]),
            agent_id=row["agent_id"],
            user_id_hash=row["user_id_hash"],
            primary_source=ContextSource(row["primary_source"]),
            source_metadata=json.loads(row["source_metadata"] or "{}"),
            conversation_history=json.loads(row["conversation_history"] or "[]"),
            active_topics=list(row["active_topics"] or []),
            entities_mentioned=json.loads(row["entities_mentioned"] or "{}"),
            current_task=row["current_task"],
            pending_questions=list(row["pending_questions"] or []),
            ucf_metrics=json.loads(row["ucf_metrics"] or "{}"),
            related_discord_threads=list(row["related_discord_threads"] or []),
            related_github_issues=list(row["related_github_issues"] or []),
            related_notion_pages=list(row["related_notion_pages"] or []),
            related_perplexity_spaces=list(row["related_perplexity_spaces"] or []),
            created_at=row["created_at"],
            last_updated=row["last_updated"],
            last_accessed=row["last_accessed"],
            expires_at=row["expires_at"],
            session_id=row["session_id"],
            parent_session_id=row["parent_session_id"],
            child_session_ids=list(row["child_session_ids"] or []),
            consent_verified=row["consent_verified"],
            privacy_level=row["privacy_level"],
            anonymized=row["anonymized"],
        )

    async def add_message(
        self,
        context_id: str,
        role: str,
        content: str,
        source: ContextSource | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """Add a message to context conversation history"""
        context = await self.get_context(context_id, update_accessed=False)
        if not context:
            logger.warning("🌀 Context %s not found", context_id)
            return

        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
            "source": source.value if source else context.primary_source.value,
        }

        if metadata:
            message["metadata"] = metadata

        context.conversation_history.append(message)
        context.last_updated = datetime.now(UTC)

        await self._store_context(context)

        logger.info(
            "🌀 [%s] Added %s message to context %s",
            context.agent_id,
            role,
            context_id[:8],
        )

    async def update_ucf_metrics(self, context_id: str, metrics: dict[str, float]):
        """Update UCF coordination metrics"""
        context = await self.get_context(context_id, update_accessed=False)
        if not context:
            return

        context.ucf_metrics.update(metrics)
        context.last_updated = datetime.now(UTC)

        await self._store_context(context)

        logger.debug(
            "🌀 [%s] Updated UCF metrics for context %s",
            context.agent_id,
            context_id[:8],
        )

    async def link_cross_platform_reference(
        self,
        context_id: str,
        reference_type: str,
        reference_id: str,
    ):
        """
        Link a cross-platform reference (Discord thread, GitHub issue, etc.)

        Args:
            context_id: Context to update
            reference_type: Type (discord_thread, github_issue, notion_page, perplexity_space)
            reference_id: Platform-specific identifier
        """
        context = await self.get_context(context_id, update_accessed=False)
        if not context:
            return

        reference_map = {
            "discord_thread": context.related_discord_threads,
            "github_issue": context.related_github_issues,
            "github_pr": context.related_github_issues,  # PRs also in issues list
            "notion_page": context.related_notion_pages,
            "perplexity_space": context.related_perplexity_spaces,
        }

        target_list = reference_map.get(reference_type)
        if target_list is not None and reference_id not in target_list:
            target_list.append(reference_id)
            context.last_updated = datetime.now(UTC)
            await self._store_context(context)

            logger.info(
                "🌀 [%s] Linked %s reference %s to context %s",
                context.agent_id,
                reference_type,
                reference_id,
                context_id[:8],
            )

    async def get_cross_platform_context_summary(
        self,
        context_id: str,
    ) -> dict[str, Any]:
        """
        Get a summary of cross-platform context for this conversation.

        Returns information about related discussions on other platforms
        that the agent can reference naturally:
        "I remember we discussed this on Discord last week..."
        """
        context = await self.get_context(context_id)
        if not context:
            return {}

        summary = {
            "current_platform": context.primary_source.value,
            "session_lineage": [],
            "related_platforms": {},
            "key_topics": context.active_topics[:5],
            "coordination_state": context.ucf_metrics,
        }

        # Session lineage
        if context.parent_session_id:
            parent = await self.get_context_by_session(context.parent_session_id)
            if parent:
                summary["session_lineage"].append(
                    {
                        "session_id": parent.session_id,
                        "platform": parent.primary_source.value,
                        "created_at": parent.created_at.isoformat(),
                    }
                )

        # Cross-platform references
        if context.related_discord_threads:
            summary["related_platforms"]["discord"] = {
                "count": len(context.related_discord_threads),
                "threads": context.related_discord_threads[:3],
            }

        if context.related_github_issues:
            summary["related_platforms"]["github"] = {
                "count": len(context.related_github_issues),
                "issues": context.related_github_issues[:3],
            }

        if context.related_notion_pages:
            summary["related_platforms"]["notion"] = {
                "count": len(context.related_notion_pages),
                "pages": context.related_notion_pages[:3],
            }

        if context.related_perplexity_spaces:
            summary["related_platforms"]["perplexity"] = {
                "count": len(context.related_perplexity_spaces),
                "spaces": context.related_perplexity_spaces[:3],
            }

        # Pull relevant memories from agent memory service
        if self.enable_cross_platform_memory:
            memories = await self.memory_service.retrieve_memories(
                agent_id=context.agent_id,
                limit=5,
                min_importance=0.6,
            )

            summary["relevant_memories"] = [
                {
                    "summary": mem.summary,
                    "platform": mem.source_platform.value,
                    "importance": mem.calculate_current_importance(),
                    "created_at": mem.created_at.isoformat(),
                }
                for mem in memories
            ]

        return summary


# Singleton instance
_context_bridge: ContextBridge | None = None


def get_context_bridge() -> ContextBridge:
    """Get or create the Context Bridge singleton"""
    global _context_bridge
    if _context_bridge is None:
        _context_bridge = ContextBridge()
    return _context_bridge
