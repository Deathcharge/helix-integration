"""
Agent Memory Service - Cross-Platform Persistent Memory

Enables agents to maintain context continuity across:
- Discord channels and DMs
- Forum threads and comments
- Browser/web chat sessions
- VSCode Copilot interactions
- Voice channel conversations

Key Features:
- Privacy-aware with consent checking
- PII detection and anonymization
- PostgreSQL persistence with Redis caching
- Semantic search for relevant memories
- Memory importance scoring and decay
- Platform-specific context retrieval

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
from enum import Enum
from typing import Any

# Optional database dependencies with graceful fallback
try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None

from apps.backend.common import Platform
from apps.backend.learning.consent_system import ConsentSystem
from apps.backend.learning.learning_system import PIIDetector, PrivacyLevel

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """Types of memories agents can store"""

    EPISODIC = "episodic"  # Specific interaction memories
    SEMANTIC = "semantic"  # Learned facts/knowledge
    PROCEDURAL = "procedural"  # How to do things
    EMOTIONAL = "emotional"  # Relationship/sentiment
    CONTEXTUAL = "contextual"  # Platform/channel context


@dataclass
class AgentMemory:
    """Cross-platform agent memory entry"""

    id: str
    agent_id: str
    memory_type: MemoryType
    content: str
    summary: str

    # Cross-platform context
    source_platform: Platform
    source_channel_id: str | None = None
    source_thread_id: str | None = None

    # User interaction (anonymized if configured)
    user_id_hash: str | None = None  # SHA256 hash for privacy
    user_display_hint: str | None = None  # "Alex from Discord" or just "a user"

    # Importance and decay
    importance: float = 0.5  # 0.0 to 1.0
    access_count: int = 0
    last_accessed: datetime | None = None
    decay_factor: float = 0.95  # Memory fades over time without access

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None

    # Tags and metadata
    tags: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)  # Named entities mentioned
    sentiment: float | None = None  # -1.0 to 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    # Privacy
    privacy_level: PrivacyLevel = PrivacyLevel.SEMI_PRIVATE
    pii_redacted: bool = False
    consent_verified: bool = False

    # UCF coordination metrics
    ucf_harmony: float | None = None
    ucf_resilience: float | None = None
    ucf_throughput: float | None = None
    ucf_focus: float | None = None
    ucf_friction: float | None = None
    ucf_velocity: float | None = None

    # Emotional metadata (SHODH spec)
    emotional_valence: float | None = None  # -1.0 (negative) to 1.0 (positive)
    emotional_arousal: float | None = None  # 0.0 (calm) to 1.0 (activated)

    # Episode grouping
    episode_id: str | None = None
    sequence_num: int | None = None

    # Quality / lifecycle
    quality_score: float = 0.5
    retrieval_count: int = 0
    actionability: float = 0.5
    value_score: float = 0.5
    source_type: str = "agent"  # agent | user | system
    is_deleted: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "memory_type": self.memory_type.value,
            "content": self.content,
            "summary": self.summary,
            "source_platform": self.source_platform.value,
            "source_channel_id": self.source_channel_id,
            "source_thread_id": self.source_thread_id,
            "user_id_hash": self.user_id_hash,
            "user_display_hint": self.user_display_hint,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": (self.last_accessed.isoformat() if self.last_accessed else None),
            "decay_factor": self.decay_factor,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "tags": self.tags,
            "entities": self.entities,
            "sentiment": self.sentiment,
            "metadata": self.metadata,
            "privacy_level": self.privacy_level.value,
            "pii_redacted": self.pii_redacted,
            "consent_verified": self.consent_verified,
            "ucf_harmony": self.ucf_harmony,
            "ucf_resilience": self.ucf_resilience,
            "ucf_throughput": self.ucf_throughput,
            "ucf_focus": self.ucf_focus,
            "ucf_friction": self.ucf_friction,
            "ucf_velocity": self.ucf_velocity,
            "emotional_valence": self.emotional_valence,
            "emotional_arousal": self.emotional_arousal,
            "episode_id": self.episode_id,
            "sequence_num": self.sequence_num,
            "quality_score": self.quality_score,
            "retrieval_count": self.retrieval_count,
            "actionability": self.actionability,
            "value_score": self.value_score,
            "source_type": self.source_type,
            "is_deleted": self.is_deleted,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AgentMemory":
        """Create from dictionary"""
        return cls(
            id=data["id"],
            agent_id=data["agent_id"],
            memory_type=MemoryType(data["memory_type"]),
            content=data["content"],
            summary=data["summary"],
            source_platform=Platform(data["source_platform"]),
            source_channel_id=data.get("source_channel_id"),
            source_thread_id=data.get("source_thread_id"),
            user_id_hash=data.get("user_id_hash"),
            user_display_hint=data.get("user_display_hint"),
            importance=data.get("importance", 0.5),
            access_count=data.get("access_count", 0),
            last_accessed=(datetime.fromisoformat(data["last_accessed"]) if data.get("last_accessed") else None),
            decay_factor=data.get("decay_factor", 0.95),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            expires_at=(datetime.fromisoformat(data["expires_at"]) if data.get("expires_at") else None),
            tags=data.get("tags", []),
            entities=data.get("entities", []),
            sentiment=data.get("sentiment"),
            metadata=data.get("metadata", {}),
            privacy_level=PrivacyLevel(data.get("privacy_level", "semi_private")),
            pii_redacted=data.get("pii_redacted", False),
            consent_verified=data.get("consent_verified", False),
            ucf_harmony=data.get("ucf_harmony"),
            ucf_resilience=data.get("ucf_resilience"),
            ucf_throughput=data.get("ucf_throughput"),
            ucf_focus=data.get("ucf_focus"),
            ucf_friction=data.get("ucf_friction"),
            ucf_velocity=data.get("ucf_velocity"),
            emotional_valence=data.get("emotional_valence"),
            emotional_arousal=data.get("emotional_arousal"),
            episode_id=data.get("episode_id"),
            sequence_num=data.get("sequence_num"),
            quality_score=data.get("quality_score", 0.5),
            retrieval_count=data.get("retrieval_count", 0),
            actionability=data.get("actionability", 0.5),
            value_score=data.get("value_score", 0.5),
            source_type=data.get("source_type", "agent"),
            is_deleted=data.get("is_deleted", False),
        )

    def calculate_current_importance(self) -> float:
        """Calculate importance with time decay"""
        if not self.last_accessed:
            days_since_access = (datetime.now(UTC) - self.created_at).days
        else:
            days_since_access = (datetime.now(UTC) - self.last_accessed).days

        # Apply decay
        decayed = self.importance * (self.decay_factor**days_since_access)

        # Boost for frequently accessed memories
        access_boost = min(0.2, self.access_count * 0.01)

        return min(1.0, decayed + access_boost)


# ── Composite scoring utility ──────────────────────────────────────────


def _composite_rerank(
    query: str,
    memories: list["AgentMemory"],
    now: datetime,
    limit: int,
) -> list["AgentMemory"]:
    """Re-rank memories using composite scoring:

    ``composite = semantic * 0.5 + recency * 0.3 + importance * 0.2``

    Falls back to original order if VectorStore is unavailable.
    """
    # Get semantic scores from VectorStore
    semantic_scores: dict[str, float] = {}
    try:
        from apps.backend.core.vector_store import vector_store

        if vector_store is not None:
            results = vector_store.search(query, top_k=50)
            for hit in results:
                doc_id = hit.get("id", "")
                if doc_id.startswith("mem:"):
                    semantic_scores[doc_id[4:]] = hit.get("score", 0.0)
    except ImportError:
        logger.debug("VectorStore not available for memory ranking")
    except Exception as e:
        logger.debug("VectorStore search failed during memory ranking: %s", e)

    # If no semantic scores available, return original SQL-ranked order
    if not semantic_scores:
        return memories

    scored = []
    for mem in memories:
        semantic = semantic_scores.get(mem.id, 0.0)
        age_days = max(0, (now - mem.created_at).total_seconds() / 86400)
        recency = max(0.0, 1.0 - (age_days / 30.0))
        importance = mem.calculate_current_importance()
        score = semantic * 0.5 + recency * 0.3 + importance * 0.2
        scored.append((score, mem))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [mem for _, mem in scored[:limit]]


class AgentMemoryService:
    """
    Cross-platform agent memory service with privacy controls.

    Enables agents to remember context across Discord, Forum, Browser,
    VSCode while respecting user consent and privacy preferences.
    """

    def __init__(
        self,
        consent_system: ConsentSystem | None = None,
        redis_client: Any | None = None,
        db_pool: Any | None = None,
    ):
        self.consent_system = consent_system or ConsentSystem()
        self.redis = redis_client
        self.db_pool = db_pool

        # In-memory fallback (for development/testing)
        self._memory_store: dict[str, AgentMemory] = {}
        self._agent_index: dict[str, list[str]] = {}  # agent_id -> [memory_ids]
        self._platform_index: dict[str, dict[str, list[str]]] = {}  # platform -> channel -> [memory_ids]

        # Configuration
        self.max_memories_per_agent = 10000
        self.default_memory_ttl_days = 90
        self.enable_anonymization = True
        self.pii_redaction_enabled = True

        logger.info("🧠 Agent Memory Service initialized")

    async def initialize(self):
        """Initialize database connections and create tables"""
        logger.info("🧠 Initializing Agent Memory Service storage")

        # Connect to PostgreSQL if DATABASE_URL is set
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            # Railway uses postgres://, asyncpg needs postgresql://
            if database_url.startswith("postgres://"):
                database_url = database_url.replace("postgres://", "postgresql://", 1)
            try:
                self.db_pool = await asyncpg.create_pool(
                    database_url,
                    min_size=1,
                    max_size=5,
                    command_timeout=60,
                )
                await self._create_tables()
                logger.info("🧠 PostgreSQL connection pool established")
            except Exception as e:
                logger.warning("🧠 PostgreSQL unavailable, using in-memory: %s", e)
                self.db_pool = None

        # Connect to Redis if REDIS_URL is set
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            try:
                self.redis = await aioredis.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self.redis.ping()
                logger.info("🧠 Redis connection established")
            except Exception as e:
                logger.warning("🧠 Redis unavailable, no caching: %s", e)
                self.redis = None

    async def _create_tables(self):
        """Create agent_memories table with indexes"""
        if not self.db_pool:
            return

        async with self.db_pool.acquire() as conn:
            # Create agent_memories table
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_memories (
                    id UUID PRIMARY KEY,
                    agent_id VARCHAR(64) NOT NULL,
                    memory_type VARCHAR(32) NOT NULL,
                    content TEXT NOT NULL,
                    summary VARCHAR(256),
                    source_platform VARCHAR(32) NOT NULL,
                    source_channel_id VARCHAR(128),
                    source_thread_id VARCHAR(128),
                    user_id_hash VARCHAR(64),
                    user_display_hint VARCHAR(64),
                    importance FLOAT DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP,
                    decay_factor FLOAT DEFAULT 0.95,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP,
                    tags TEXT[],
                    entities TEXT[],
                    sentiment FLOAT,
                    metadata JSONB DEFAULT '{}',
                    privacy_level VARCHAR(32) DEFAULT 'semi_private',
                    pii_redacted BOOLEAN DEFAULT false,
                    consent_verified BOOLEAN DEFAULT false
                )
            """
            )

            # Create indexes for efficient queries
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_agent_memories_agent_id ON agent_memories(agent_id)")
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memories_platform_channel "
                "ON agent_memories(source_platform, source_channel_id)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memories_created_at ON agent_memories(created_at DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memories_importance ON agent_memories(importance DESC)"
            )
            await conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_agent_memories_expires_at "
                "ON agent_memories(expires_at) WHERE expires_at IS NOT NULL"
            )

            logger.info("🧠 Agent memories table and indexes created")

            # Add UCF + emotional + episode + quality columns (idempotent)
            # SECURITY: Frozen allowlist — never populate from config or user input
            _ALLOWED_COL_DEFS = frozenset(
                {
                    ("ucf_harmony", "FLOAT"),
                    ("ucf_resilience", "FLOAT"),
                    ("ucf_throughput", "FLOAT"),
                    ("ucf_focus", "FLOAT"),
                    ("ucf_friction", "FLOAT"),
                    ("ucf_velocity", "FLOAT"),
                    ("emotional_valence", "FLOAT"),
                    ("emotional_arousal", "FLOAT"),
                    ("episode_id", "VARCHAR(36)"),
                    ("sequence_num", "INTEGER"),
                    ("quality_score", "FLOAT DEFAULT 0.5"),
                    ("source_type", "VARCHAR(32) DEFAULT 'agent'"),
                    ("is_deleted", "BOOLEAN DEFAULT false"),
                    ("retrieval_count", "INTEGER DEFAULT 0"),
                    ("actionability", "FLOAT DEFAULT 0.5"),
                    ("value_score", "FLOAT DEFAULT 0.5"),
                }
            )
            new_columns = list(_ALLOWED_COL_DEFS)
            for col_name, col_type in new_columns:
                if (col_name, col_type) not in _ALLOWED_COL_DEFS:
                    logger.error("Rejected unknown column def: %s %s", col_name, col_type)
                    continue
                try:
                    await conn.execute(f'ALTER TABLE agent_memories ADD COLUMN IF NOT EXISTS "{col_name}" {col_type}')
                except Exception as e:
                    logger.debug("Column %s may already exist: %s", col_name, e)

            # Create memory_edges table for knowledge graph relationships
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_edges (
                    id VARCHAR(36) PRIMARY KEY,
                    source_id VARCHAR(36) NOT NULL,
                    target_id VARCHAR(36) NOT NULL,
                    relationship VARCHAR(32) NOT NULL,
                    weight FLOAT DEFAULT 1.0,
                    created_by VARCHAR(100),
                    created_at TIMESTAMP DEFAULT NOW()
                )
                """
            )
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_edges_source ON memory_edges(source_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_edges_target ON memory_edges(target_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_edges_relationship ON memory_edges(relationship)")

    def _hash_user_id(self, user_id: str) -> str:
        """Hash user ID for privacy"""
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def _anonymize_user_hint(self, user_id: str, platform: Platform) -> str:
        """Create anonymized user hint"""
        if not self.enable_anonymization:
            return f"user_{user_id[:8]}"

        # Consistent anonymous identifier per user
        hint_hash = hashlib.md5(user_id.encode(), usedforsecurity=False).hexdigest()[:4]
        return f"user_{hint_hash} on {platform.value}"

    def _prepare_content(self, content: str) -> tuple[str, bool]:
        """Prepare content with PII redaction"""
        if not self.pii_redaction_enabled:
            return content, False

        if PIIDetector.contains_pii(content):
            redacted = PIIDetector.redact_pii(content)
            return redacted, True

        return content, False

    async def check_consent(self, user_id: str) -> bool:
        """Check if user has consented to cross-platform learning"""
        prefs = self.consent_system.privacy_preferences.get(user_id)
        if prefs:
            return prefs.allow_cross_platform and prefs.allow_learning
        return False  # Default to no consent

    async def _snapshot_ucf_metrics(self) -> dict[str, float | None]:
        """Snapshot current UCF metrics for stamping onto new memories."""
        try:
            from apps.backend.core.ucf_helpers import get_current_ucf

            ucf_state = get_current_ucf()
            if ucf_state:
                return {
                    "ucf_harmony": ucf_state.get("harmony"),
                    "ucf_resilience": ucf_state.get("resilience"),
                    "ucf_throughput": ucf_state.get("throughput"),
                    "ucf_focus": ucf_state.get("focus"),
                    "ucf_friction": ucf_state.get("friction"),
                    "ucf_velocity": ucf_state.get("velocity"),
                }
        except Exception as e:
            logger.debug("UCF stamp unavailable: %s", e)
        return {
            "ucf_harmony": None,
            "ucf_resilience": None,
            "ucf_throughput": None,
            "ucf_focus": None,
            "ucf_friction": None,
            "ucf_velocity": None,
        }

    async def store_memory(
        self,
        agent_id: str,
        content: str,
        memory_type: MemoryType,
        platform: Platform,
        user_id: str | None = None,
        channel_id: str | None = None,
        thread_id: str | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
        entities: list[str] | None = None,
        sentiment: float | None = None,
        metadata: dict[str, Any] | None = None,
        require_consent: bool = True,
    ) -> AgentMemory | None:
        """
        Store a memory for an agent with privacy controls.

        Args:
            agent_id: Agent storing the memory
            content: Raw content to remember
            memory_type: Type of memory
            platform: Source platform
            user_id: User involved (will be hashed)
            channel_id: Source channel/room
            thread_id: Thread within channel
            importance: Memory importance (0.0-1.0)
            tags: Categorization tags
            entities: Named entities in content
            sentiment: Sentiment score (-1.0 to 1.0)
            metadata: Additional metadata
            require_consent: Whether to check user consent

        Returns:
            Stored AgentMemory or None if consent denied
        """
        # Check consent if user involved
        if user_id and require_consent:
            has_consent = await self.check_consent(user_id)
            if not has_consent:
                logger.debug("Memory not stored - no consent from user %s", self._hash_user_id(user_id))
                return None

        # Prepare content (PII redaction)
        prepared_content, pii_redacted = self._prepare_content(content)

        # Create summary (first 100 chars for quick retrieval)
        summary = prepared_content[:100] + "..." if len(prepared_content) > 100 else prepared_content

        # Snapshot UCF metrics at creation time
        ucf = await self._snapshot_ucf_metrics()

        # ── Memory Consolidation ──────────────────────────────────────────
        # Check if a near-duplicate memory already exists for this agent.
        # If so, boost the existing memory's importance rather than
        # inserting a duplicate.  Threshold: cosine similarity >= 0.90.
        existing = await self._find_similar_memory(agent_id, prepared_content)
        if existing is not None:
            existing_id, similarity = existing
            await self._boost_existing_memory(existing_id, importance)
            logger.info(
                "🧠 [%s] Consolidated memory (sim=%.3f) into %s instead of new insert",
                agent_id,
                similarity,
                existing_id,
            )
            # Return the boosted memory (retrieve it fresh)
            boosted = await self._get_memory_by_id(existing_id)
            return boosted

        # Create memory
        memory = AgentMemory(
            id=str(uuid.uuid4()),
            agent_id=agent_id,
            memory_type=memory_type,
            content=prepared_content,
            summary=summary,
            source_platform=platform,
            source_channel_id=channel_id,
            source_thread_id=thread_id,
            user_id_hash=self._hash_user_id(user_id) if user_id else None,
            user_display_hint=(self._anonymize_user_hint(user_id, platform) if user_id else None),
            importance=importance,
            tags=tags or [],
            entities=entities or [],
            sentiment=sentiment,
            metadata=metadata or {},
            pii_redacted=pii_redacted,
            consent_verified=not require_consent or (user_id is not None and await self.check_consent(user_id)),
            expires_at=datetime.now(UTC) + timedelta(days=self.default_memory_ttl_days),
            **ucf,
        )

        # Store in memory (replace with DB in production)
        await self._store(memory)

        logger.info(
            "🧠 [%s] Stored %s memory from %s: %s",
            agent_id,
            memory_type.value,
            platform.value,
            summary[:50],
        )

        return memory

    async def _store(self, memory: AgentMemory):
        """Store memory in PostgreSQL with Redis cache, fallback to in-memory"""
        # Try PostgreSQL first
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO agent_memories (
                            id, agent_id, memory_type, content, summary,
                            source_platform, source_channel_id, source_thread_id,
                            user_id_hash, user_display_hint, importance,
                            access_count, last_accessed, decay_factor,
                            created_at, updated_at, expires_at,
                            tags, entities, sentiment, metadata,
                            privacy_level, pii_redacted, consent_verified,
                            ucf_harmony, ucf_resilience, ucf_throughput,
                            ucf_focus, ucf_friction, ucf_velocity,
                            emotional_valence, emotional_arousal,
                            episode_id, sequence_num, quality_score,
                            source_type, is_deleted
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18, $19,
                            $20, $21, $22, $23, $24, $25, $26, $27, $28,
                            $29, $30, $31, $32, $33, $34, $35, $36, $37
                        )
                        """,
                        uuid.UUID(memory.id),
                        memory.agent_id,
                        memory.memory_type.value,
                        memory.content,
                        memory.summary,
                        memory.source_platform.value,
                        memory.source_channel_id,
                        memory.source_thread_id,
                        memory.user_id_hash,
                        memory.user_display_hint,
                        memory.importance,
                        memory.access_count,
                        memory.last_accessed,
                        memory.decay_factor,
                        memory.created_at,
                        memory.updated_at,
                        memory.expires_at,
                        memory.tags,
                        memory.entities,
                        memory.sentiment,
                        json.dumps(memory.metadata),
                        memory.privacy_level.value,
                        memory.pii_redacted,
                        memory.consent_verified,
                        memory.ucf_harmony,
                        memory.ucf_resilience,
                        memory.ucf_throughput,
                        memory.ucf_focus,
                        memory.ucf_friction,
                        memory.ucf_velocity,
                        memory.emotional_valence,
                        memory.emotional_arousal,
                        memory.episode_id,
                        memory.sequence_num,
                        memory.quality_score,
                        memory.source_type,
                        memory.is_deleted,
                    )

                # Cache in Redis for fast retrieval
                if self.redis:
                    cache_key = f"memory:{memory.id}"
                    await self.redis.setex(
                        cache_key,
                        3600,  # 1 hour TTL
                        json.dumps(memory.to_dict()),
                    )

                # Index in VectorStore for semantic search + consolidation
                self._index_memory_vector(memory)

                # Prune if over limit
                await self._prune_agent_memories(memory.agent_id)
                return

            except Exception as e:
                logger.error("🧠 PostgreSQL store failed, falling back: %s", e)

        # In-memory fallback (development/testing)
        self._memory_store[memory.id] = memory

        # Index by agent
        if memory.agent_id not in self._agent_index:
            self._agent_index[memory.agent_id] = []
        self._agent_index[memory.agent_id].append(memory.id)

        # Index by platform/channel
        platform_key = memory.source_platform.value
        if platform_key not in self._platform_index:
            self._platform_index[platform_key] = {}
        channel_key = memory.source_channel_id or "__global__"
        if channel_key not in self._platform_index[platform_key]:
            self._platform_index[platform_key][channel_key] = []
        self._platform_index[platform_key][channel_key].append(memory.id)

        # Prune if over limit
        await self._prune_agent_memories(memory.agent_id)

    # ── Consolidation helpers ─────────────────────────────────────────────

    def _index_memory_vector(self, memory: AgentMemory) -> None:
        """Index a memory in VectorStore for semantic search + consolidation."""
        try:
            from apps.backend.core.vector_store import vector_store

            if vector_store is None:
                return
            vector_store.add_document(
                doc_id=f"mem:{memory.id}",
                text=memory.content,
                metadata={
                    "agent_id": memory.agent_id,
                    "type": "agent_memory",
                    "memory_type": memory.memory_type.value,
                    "importance": memory.importance,
                },
            )
        except ImportError:
            logger.debug("vector_store not available, skipping memory indexing")
        except Exception as e:
            logger.warning("Error indexing memory for vector search: %s", e)

    async def _find_similar_memory(
        self,
        agent_id: str,
        content: str,
        threshold: float = 0.90,
    ) -> tuple | None:
        """Check if a near-duplicate memory exists for this agent via vector search.

        Returns (memory_id, similarity_score) if found, else None.
        """
        try:
            from apps.backend.core.vector_store import vector_store

            if vector_store is None:
                return None

            results = vector_store.search(content, top_k=3)
            for hit in results:
                score = hit.get("score", 0.0)
                if score < threshold:
                    continue
                meta = hit.get("metadata", {})
                # Only match memories for the same agent
                if meta.get("agent_id") == agent_id and meta.get("type") == "agent_memory":
                    doc_id = hit.get("id", "")
                    if doc_id.startswith("mem:"):
                        return (doc_id[4:], score)
        except ImportError:
            logger.debug("vector_store not available, skipping similarity check")
        except Exception as e:
            logger.warning("Error checking similar memory: %s", e)
        return None

    async def _boost_existing_memory(self, memory_id: str, new_importance: float) -> None:
        """Boost an existing memory's importance (capped at 1.0) and update timestamp."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE agent_memories "
                        "SET importance = LEAST(1.0, importance + $1 * 0.3), "
                        "    access_count = access_count + 1, "
                        "    quality_score = LEAST(1.0, COALESCE(quality_score, 0.5) + 0.05), "
                        "    updated_at = $2 "
                        "WHERE id = $3",
                        new_importance,
                        datetime.now(UTC),
                        uuid.UUID(memory_id),
                    )
            except Exception as e:
                logger.warning("Failed to boost memory %s: %s", memory_id, e)
        else:
            # In-memory fallback
            mem = self._memory_store.get(memory_id)
            if mem:
                mem.importance = min(1.0, mem.importance + new_importance * 0.3)
                mem.access_count += 1
                mem.updated_at = datetime.now(UTC)

    async def _get_memory_by_id(self, memory_id: str) -> AgentMemory | None:
        """Retrieve a single memory by ID."""
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT * FROM agent_memories WHERE id = $1",
                        uuid.UUID(memory_id),
                    )
                    if row:
                        return self._row_to_memory(row)
            except Exception as e:
                logger.warning("Failed to fetch memory %s: %s", memory_id, e)
        else:
            return self._memory_store.get(memory_id)
        return None

    async def _prune_agent_memories(self, agent_id: str):
        """Prune old/low-importance memories if over limit"""
        # Use SQL-based pruning for PostgreSQL
        if self.db_pool:
            try:
                async with self.db_pool.acquire() as conn:
                    # Count memories for agent
                    count = await conn.fetchval(
                        "SELECT COUNT(*) FROM agent_memories WHERE agent_id = $1",
                        agent_id,
                    )

                    if count <= self.max_memories_per_agent:
                        return

                    # Delete oldest/lowest-importance memories exceeding limit
                    # Score = importance * (decay_factor ^ days_since_creation)
                    await conn.execute(
                        """
                        DELETE FROM agent_memories
                        WHERE id IN (
                            SELECT id FROM agent_memories
                            WHERE agent_id = $1
                            ORDER BY
                                importance * POWER(decay_factor,
                                    EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400
                                ) ASC
                            LIMIT $2
                        )
                    """,
                        agent_id,
                        count - self.max_memories_per_agent,
                    )

                    pruned = count - self.max_memories_per_agent
                    logger.info("🧠 Pruned %d memories for %s via SQL", pruned, agent_id)
                return

            except Exception as e:
                logger.error("🧠 SQL prune failed: %s", e)

        # In-memory fallback
        if agent_id not in self._agent_index:
            return

        memory_ids = self._agent_index[agent_id]
        if len(memory_ids) <= self.max_memories_per_agent:
            return

        # Score and sort memories
        scored = []
        for mid in memory_ids:
            memory = self._memory_store.get(mid)
            if memory:
                score = memory.calculate_current_importance()
                scored.append((mid, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        # Keep top memories
        keep_ids = set(mid for mid, _ in scored[: self.max_memories_per_agent])

        # Remove pruned
        for mid in memory_ids:
            if mid not in keep_ids:
                del self._memory_store[mid]

        self._agent_index[agent_id] = list(keep_ids)
        logger.info("🧠 Pruned memories for %s, kept %d", agent_id, len(keep_ids))

    async def retrieve_memories(
        self,
        agent_id: str,
        query: str | None = None,
        platform: Platform | None = None,
        memory_type: MemoryType | None = None,
        tags: list[str] | None = None,
        min_importance: float = 0.0,
        limit: int = 20,
        include_expired: bool = False,
    ) -> list[AgentMemory]:
        """
        Retrieve relevant memories for an agent.

        Args:
            agent_id: Agent to retrieve memories for
            query: Optional search query
            platform: Filter by source platform
            memory_type: Filter by memory type
            tags: Filter by tags (any match)
            min_importance: Minimum importance threshold
            limit: Maximum results
            include_expired: Include expired memories

        Returns:
            List of relevant AgentMemory objects
        """
        now = datetime.now(UTC)

        # Try PostgreSQL first
        if self.db_pool:
            try:
                return await self._retrieve_from_db(
                    agent_id,
                    query,
                    platform,
                    memory_type,
                    tags,
                    min_importance,
                    limit,
                    include_expired,
                    now,
                )
            except Exception as e:
                logger.error("🧠 PostgreSQL retrieval failed: %s", e)

        # In-memory fallback
        if agent_id not in self._agent_index:
            return []

        results = []

        for memory_id in self._agent_index[agent_id]:
            memory = self._memory_store.get(memory_id)
            if not memory:
                continue

            # Check expiration
            if not include_expired and memory.expires_at and memory.expires_at < now:
                continue

            # Filter by platform
            if platform and memory.source_platform != platform:
                continue

            # Filter by type
            if memory_type and memory.memory_type != memory_type:
                continue

            # Filter by tags
            if tags and not any(t in memory.tags for t in tags):
                continue

            # Check importance
            current_importance = memory.calculate_current_importance()
            if current_importance < min_importance:
                continue

            # Query matching (simple substring for now)
            if query:
                query_lower = query.lower()
                if (
                    query_lower not in memory.content.lower()
                    and query_lower not in memory.summary.lower()
                    and not any(query_lower in t.lower() for t in memory.tags)
                ):
                    continue

            results.append((memory, current_importance))

        # Sort by importance and recency
        results.sort(key=lambda x: (x[1], x[0].created_at), reverse=True)

        # Update access counts
        memories = []
        for memory, _ in results[:limit]:
            memory.access_count += 1
            memory.last_accessed = now
            memories.append(memory)

        return memories

    async def _retrieve_from_db(
        self,
        agent_id: str,
        query: str | None,
        platform: Platform | None,
        memory_type: MemoryType | None,
        tags: list[str] | None,
        min_importance: float,
        limit: int,
        include_expired: bool,
        now: datetime,
    ) -> list[AgentMemory]:
        """Retrieve memories from PostgreSQL with dynamic filtering"""
        # Build SQL query with filters
        sql_parts = ["SELECT * FROM agent_memories WHERE agent_id = $1"]
        params: list[Any] = [agent_id]
        param_idx = 2

        if not include_expired:
            sql_parts.append(f"AND (expires_at IS NULL OR expires_at > ${param_idx})")
            params.append(now)
            param_idx += 1

        if platform:
            sql_parts.append(f"AND source_platform = ${param_idx}")
            params.append(platform.value)
            param_idx += 1

        if memory_type:
            sql_parts.append(f"AND memory_type = ${param_idx}")
            params.append(memory_type.value)
            param_idx += 1

        if tags:
            sql_parts.append(f"AND tags && ${param_idx}")  # Array overlap
            params.append(tags)
            param_idx += 1

        if min_importance > 0:
            sql_parts.append(f"AND importance >= ${param_idx}")
            params.append(min_importance)
            param_idx += 1

        if query:
            sql_parts.append(f"AND (content ILIKE ${param_idx} OR summary ILIKE ${param_idx})")
            params.append(f"%{query}%")
            param_idx += 1

        # Order by importance with decay and creation time
        sql_parts.append(
            "ORDER BY importance * POWER(decay_factor, "
            "EXTRACT(EPOCH FROM (NOW() - created_at)) / 86400) DESC, "
            "created_at DESC"
        )
        sql_parts.append(f"LIMIT ${param_idx}")
        params.append(limit)

        sql = " ".join(sql_parts)

        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *params)

            memories = []
            for row in rows:
                memory = self._row_to_memory(row)
                memories.append(memory)

                # Increment retrieval_count and recompute value_score.
                # value_score = quality_score * 0.4 + retrieval_frequency * 0.3 + actionability * 0.3
                # retrieval_frequency is normalized: min(retrieval_count / 50, 1.0)
                await conn.execute(
                    "UPDATE agent_memories "
                    "SET access_count = access_count + 1, "
                    "    retrieval_count = COALESCE(retrieval_count, 0) + 1, "
                    "    last_accessed = $1, "
                    "    quality_score = LEAST(1.0, COALESCE(quality_score, 0.5) + 0.02) "
                    "WHERE id = $2",
                    now,
                    row["id"],
                )

                # Update value_score after retrieval bump
                await conn.execute(
                    "UPDATE agent_memories "
                    "SET value_score = LEAST(1.0, "
                    "    COALESCE(quality_score, 0.5) * 0.4 "
                    "    + LEAST(1.0, COALESCE(retrieval_count, 0) / 50.0) * 0.3 "
                    "    + COALESCE(actionability, 0.5) * 0.3) "
                    "WHERE id = $1",
                    row["id"],
                )

                # Invalidate Redis cache
                if self.redis:
                    await self.redis.delete(f"memory:{row['id']}")

            # ── Composite re-ranking ──────────────────────────────────────
            # When a query is provided, re-rank using:
            #   composite = semantic * 0.5 + recency * 0.3 + importance * 0.2
            if query and memories:
                memories = _composite_rerank(query, memories, now, limit)

            return memories

    def _row_to_memory(self, row: "asyncpg.Record") -> AgentMemory:
        """Convert database row to AgentMemory object"""
        return AgentMemory(
            id=str(row["id"]),
            agent_id=row["agent_id"],
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            summary=row["summary"] or "",
            source_platform=Platform(row["source_platform"]),
            source_channel_id=row["source_channel_id"],
            source_thread_id=row["source_thread_id"],
            user_id_hash=row["user_id_hash"],
            user_display_hint=row["user_display_hint"],
            importance=row["importance"],
            access_count=row["access_count"],
            last_accessed=row["last_accessed"],
            decay_factor=row["decay_factor"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            tags=list(row["tags"]) if row["tags"] else [],
            entities=list(row["entities"]) if row["entities"] else [],
            sentiment=row["sentiment"],
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            privacy_level=PrivacyLevel(row["privacy_level"]),
            pii_redacted=row["pii_redacted"],
            consent_verified=row["consent_verified"],
            ucf_harmony=row.get("ucf_harmony"),
            ucf_resilience=row.get("ucf_resilience"),
            ucf_throughput=row.get("ucf_throughput"),
            ucf_focus=row.get("ucf_focus"),
            ucf_friction=row.get("ucf_friction"),
            ucf_velocity=row.get("ucf_velocity"),
            emotional_valence=row.get("emotional_valence"),
            emotional_arousal=row.get("emotional_arousal"),
            episode_id=row.get("episode_id"),
            sequence_num=row.get("sequence_num"),
            quality_score=row.get("quality_score", 0.5) or 0.5,
            retrieval_count=row.get("retrieval_count", 0) or 0,
            actionability=row.get("actionability", 0.5) or 0.5,
            value_score=row.get("value_score", 0.5) or 0.5,
            source_type=row.get("source_type", "agent") or "agent",
            is_deleted=row.get("is_deleted", False) or False,
        )

    async def get_cross_platform_context(
        self,
        agent_id: str,
        current_platform: Platform,
        current_channel_id: str | None = None,
        user_id_hash: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """
        Get context from other platforms for an agent.

        This enables agents to say things like:
        "I remember we discussed this on Discord last week..."

        Args:
            agent_id: Agent ID
            current_platform: Platform the agent is currently on
            current_channel_id: Current channel (to exclude)
            user_id_hash: User to get context about
            limit: Max memories per platform

        Returns:
            Dictionary with cross-platform context
        """
        context = {
            "platforms": {},
            "recent_topics": [],
            "user_history": [],
            "relevant_insights": [],
        }

        all_memories = await self.retrieve_memories(
            agent_id=agent_id,
            limit=limit * 5,  # Get more to filter
        )

        topics_seen = set()

        for memory in all_memories:
            # Skip same platform+channel
            if memory.source_platform == current_platform and memory.source_channel_id == current_channel_id:
                continue

            platform_key = memory.source_platform.value
            if platform_key not in context["platforms"]:
                context["platforms"][platform_key] = []

            if len(context["platforms"][platform_key]) < limit:
                context["platforms"][platform_key].append(
                    {
                        "summary": memory.summary,
                        "created_at": memory.created_at.isoformat(),
                        "importance": memory.calculate_current_importance(),
                        "tags": memory.tags,
                    }
                )

            # Collect topics
            for tag in memory.tags:
                if tag not in topics_seen:
                    topics_seen.add(tag)
                    context["recent_topics"].append(tag)

            # User history
            if user_id_hash and memory.user_id_hash == user_id_hash:
                context["user_history"].append(
                    {
                        "summary": memory.summary,
                        "platform": platform_key,
                        "sentiment": memory.sentiment,
                    }
                )

        return context

    async def get_agent_summary(
        self,
        agent_id: str,
    ) -> dict[str, Any]:
        """Get summary of agent's memories across platforms"""
        if agent_id not in self._agent_index:
            return {"total_memories": 0, "platforms": {}}

        summary = {
            "total_memories": len(self._agent_index[agent_id]),
            "platforms": {},
            "memory_types": {},
            "avg_importance": 0.0,
            "oldest_memory": None,
            "newest_memory": None,
        }

        total_importance = 0.0
        oldest = None
        newest = None

        for memory_id in self._agent_index[agent_id]:
            memory = self._memory_store.get(memory_id)
            if not memory:
                continue

            # Platform counts
            platform = memory.source_platform.value
            summary["platforms"][platform] = summary["platforms"].get(platform, 0) + 1

            # Type counts
            mtype = memory.memory_type.value
            summary["memory_types"][mtype] = summary["memory_types"].get(mtype, 0) + 1

            # Importance
            total_importance += memory.calculate_current_importance()

            # Date tracking
            if oldest is None or memory.created_at < oldest:
                oldest = memory.created_at
            if newest is None or memory.created_at > newest:
                newest = memory.created_at

        if summary["total_memories"] > 0:
            summary["avg_importance"] = total_importance / summary["total_memories"]

        summary["oldest_memory"] = oldest.isoformat() if oldest else None
        summary["newest_memory"] = newest.isoformat() if newest else None

        return summary


# ============================================================================
# INTENT-AWARE RETRIEVAL SCORING (SimpleMem-inspired)
#
# Before scoring archival memories, the query is classified into one of five
# intent buckets using fast keyword matching (no LLM call).  Each bucket uses
# different composite weights so the formula matches what the query actually
# needs:
#
#   episodic_recall   — "what did we discuss?" → recency matters most
#   factual_lookup    — "what is X / how does Y work?" → semantic match first
#   preference_check  — "do I prefer / what do I like?" → importance-weighted
#   task_context      — "how did I solve / pattern for X?" → balanced semantic
#   default           — fallback when no clear signal
# ============================================================================

_RETRIEVAL_INTENT_WEIGHTS: dict[str, dict[str, float]] = {
    "episodic_recall": {"semantic": 0.30, "recency": 0.50, "importance": 0.20},
    "factual_lookup": {"semantic": 0.70, "recency": 0.10, "importance": 0.20},
    "preference_check": {"semantic": 0.50, "recency": 0.20, "importance": 0.30},
    "task_context": {"semantic": 0.60, "recency": 0.20, "importance": 0.20},
    "default": {"semantic": 0.50, "recency": 0.30, "importance": 0.20},
}

_EPISODIC_TRIGGERS = frozenset(
    [
        "what did",
        "what we",
        "discussed",
        "said",
        "talked",
        "mentioned",
        "last time",
        "yesterday",
        "recall",
        "remember when",
        "you told",
        "i told",
        "conversation",
    ]
)
_FACTUAL_TRIGGERS = frozenset(
    ["what is", "what are", "define", "definition", "explain", "how does", "describe", "tell me about", "meaning of"]
)
_PREFERENCE_TRIGGERS = frozenset(
    [
        "prefer",
        "like",
        "favourite",
        "favorite",
        "want",
        "need",
        "feel about",
        "opinion",
        "my style",
        "i usually",
        "i tend",
    ]
)
_TASK_TRIGGERS = frozenset(
    [
        "how did",
        "how to",
        "solved",
        "fixed",
        "implemented",
        "approach",
        "solution",
        "pattern",
        "strategy",
        "workaround",
        "trick",
        "technique",
    ]
)


def _classify_retrieval_intent(query: str) -> dict[str, float]:
    """Return composite scoring weights based on the query's retrieval intent."""
    q = query.lower()
    if any(kw in q for kw in _EPISODIC_TRIGGERS):
        return _RETRIEVAL_INTENT_WEIGHTS["episodic_recall"]
    if any(kw in q for kw in _PREFERENCE_TRIGGERS):
        return _RETRIEVAL_INTENT_WEIGHTS["preference_check"]
    if any(kw in q for kw in _TASK_TRIGGERS):
        return _RETRIEVAL_INTENT_WEIGHTS["task_context"]
    if any(kw in q for kw in _FACTUAL_TRIGGERS):
        return _RETRIEVAL_INTENT_WEIGHTS["factual_lookup"]
    return _RETRIEVAL_INTENT_WEIGHTS["default"]


# ============================================================================
# THREE-TIER MEMORY MANAGER (Letta/MemGPT-inspired)
# ============================================================================


class MemoryTier(Enum):
    """Memory tier classification for Letta-style three-tier architecture."""

    CORE = "core"  # Always present, small, essential identity facts (<2KB)
    CONVERSATIONAL = "conversational"  # Recent turns, recency-weighted (last 20)
    ARCHIVAL = "archival"  # Long-term compressed, importance-ranked, searchable


@dataclass
class CoreMemoryBlock:
    """A pinned fact in the agent's core memory (always injected into every prompt)."""

    key: str
    value: str
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def byte_size(self) -> int:
        return len((self.key + self.value).encode("utf-8"))


class ThreeTierMemoryManager:
    """
    Letta-inspired three-tier memory architecture for Helix agents.

    CORE (< 2KB): Pinned facts always injected — agent identity, user preferences,
                  ongoing goals. Never evicted, only updated.
    CONVERSATIONAL (last 20 turns): Rolling buffer of recent interactions.
                  Oldest turns are compressed and archived automatically.
    ARCHIVAL (unlimited): Long-term compressed memories sorted by importance.
                  Retrieved by relevance scoring against current query.

    Usage::

        mgr = ThreeTierMemoryManager("kael", get_memory_service())
        await mgr.update_core("user_preference", "prefers concise responses")
        await mgr.push_conversational("user", "What's the UCF state?")
        await mgr.push_conversational("assistant", "Harmony is at 0.92...")
        memories = await mgr.search_archival("UCF metrics")
        prompt_block = await mgr.format_for_prompt("What is harmony?")
    """

    CORE_MAX_BYTES = 2048  # 2KB limit for core memory
    CONVERSATIONAL_MAX_TURNS = 20  # Rolling window
    CONVERSATIONAL_ARCHIVE_THRESHOLD = 15  # Archive oldest when buffer hits this
    CONVERSATIONAL_REDIS_TTL = 86400  # 24 hours

    def __init__(self, agent_id: str, memory_service: "AgentMemoryService"):
        self.agent_id = agent_id
        self.memory_service = memory_service

        # Core memory: key → CoreMemoryBlock
        self._core: dict[str, CoreMemoryBlock] = {}

        # Conversational buffer: list of {"role": str, "content": str, "ts": datetime}
        self._conversational: list[dict[str, Any]] = []

        # Track total core bytes
        self._core_bytes: int = 0

        # Lazy restoration flag — set after first Redis restore attempt
        self._restored: bool = False

    # ── Redis Persistence ────────────────────────────────────────────────

    @staticmethod
    async def _get_redis():
        """Get Redis client, returning None if unavailable."""
        try:
            from apps.backend.core.redis_client import get_redis

            return await get_redis()
        except Exception as e:
            logger.debug("Redis unavailable for agent memory: %s", e)
            return None

    async def _ensure_restored(self) -> None:
        """Lazily restore core + conversational memory from Redis on first access."""
        if self._restored:
            return
        self._restored = True

        r = await self._get_redis()
        if not r:
            return

        try:
            # Restore core memory
            raw_core = await r.get(f"helix:memory:core:{self.agent_id}")
            if raw_core:
                if isinstance(raw_core, bytes):
                    raw_core = raw_core.decode("utf-8")
                data = json.loads(raw_core)
                for k, v in data.items():
                    block = CoreMemoryBlock(
                        key=k,
                        value=v["value"],
                        updated_at=datetime.fromisoformat(v["updated_at"]),
                    )
                    self._core[k] = block
                    self._core_bytes += block.byte_size()
                logger.debug(
                    "Restored %d core facts from Redis for %s",
                    len(data),
                    self.agent_id,
                )

            # Restore conversational buffer
            raw_conv = await r.get(f"helix:memory:conv:{self.agent_id}")
            if raw_conv:
                if isinstance(raw_conv, bytes):
                    raw_conv = raw_conv.decode("utf-8")
                self._conversational = json.loads(raw_conv)
                logger.debug(
                    "Restored %d conversational turns from Redis for %s",
                    len(self._conversational),
                    self.agent_id,
                )
        except Exception as e:
            logger.warning("Redis restore failed for %s: %s", self.agent_id, e)

    # 30-day TTL for core memory — refreshed on every persist, prevents unbounded growth
    CORE_MEMORY_REDIS_TTL: int = 30 * 24 * 3600  # 30 days

    async def _persist_core(self) -> None:
        """Write core memory to Redis with 30-day TTL (refreshed on each write)."""
        r = await self._get_redis()
        if not r:
            return
        try:
            data = {k: {"value": v.value, "updated_at": v.updated_at.isoformat()} for k, v in self._core.items()}
            await r.set(
                f"helix:memory:core:{self.agent_id}",
                json.dumps(data),
                ex=self.CORE_MEMORY_REDIS_TTL,
            )
        except Exception as e:
            logger.warning("Failed to persist core memory to Redis: %s", e)

    async def _persist_conversational(self) -> None:
        """Write conversational buffer to Redis with 24h TTL."""
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.set(
                f"helix:memory:conv:{self.agent_id}",
                json.dumps(self._conversational),
                ex=self.CONVERSATIONAL_REDIS_TTL,
            )
        except Exception as e:
            logger.warning("Failed to persist conversational memory to Redis: %s", e)

    async def clear_redis_keys(self) -> None:
        """Delete this manager's Redis keys (for GDPR erasure)."""
        r = await self._get_redis()
        if not r:
            return
        try:
            await r.delete(f"helix:memory:core:{self.agent_id}")
            await r.delete(f"helix:memory:conv:{self.agent_id}")
        except Exception as e:
            logger.warning("Failed to clear Redis memory keys: %s", e)

    # ── Core Memory ──────────────────────────────────────────────────────

    async def update_core(self, key: str, value: str) -> bool:
        """
        Set or update a core memory fact.

        Returns True on success, False if it would exceed the 2KB limit.
        Persists to Redis for cross-restart durability.
        """
        await self._ensure_restored()

        existing = self._core.get(key)
        existing_bytes = existing.byte_size() if existing else 0
        new_bytes = len((key + value).encode("utf-8"))
        projected = self._core_bytes - existing_bytes + new_bytes

        if projected > self.CORE_MAX_BYTES:
            logger.warning(
                "Core memory full for agent %s — cannot add key '%s' (%d bytes, limit %d)",
                self.agent_id,
                key,
                projected,
                self.CORE_MAX_BYTES,
            )
            return False

        self._core[key] = CoreMemoryBlock(key=key, value=value)
        self._core_bytes = projected
        logger.debug("Core memory updated: %s[%s] = %s…", self.agent_id, key, value[:40])

        await self._persist_core()
        return True

    def get_core(self, key: str) -> str | None:
        """Retrieve a core memory value by key."""
        block = self._core.get(key)
        return block.value if block else None

    async def delete_core(self, key: str) -> bool:
        """Remove a core memory fact. Persists deletion to Redis."""
        await self._ensure_restored()
        if key in self._core:
            self._core_bytes -= self._core.pop(key).byte_size()
            await self._persist_core()
            return True
        return False

    # ── Conversational Memory ─────────────────────────────────────────────

    async def push_conversational(self, role: str, content: str) -> None:
        """
        Add a turn to the conversational buffer.

        When the buffer hits CONVERSATIONAL_ARCHIVE_THRESHOLD, the oldest
        turns are compressed into an archival memory to free space.
        Persists to Redis for cross-restart durability.
        """
        await self._ensure_restored()

        self._conversational.append(
            {
                "role": role,
                "content": content[:500],  # Truncate to 500 chars per turn
                "ts": datetime.now(UTC).isoformat(),
            }
        )

        if len(self._conversational) >= self.CONVERSATIONAL_ARCHIVE_THRESHOLD:
            await self._archive_oldest_turns(n=5)

        await self._persist_conversational()

    async def _archive_oldest_turns(self, n: int = 5) -> None:
        """Compress the oldest N turns into an archival memory entry."""
        if len(self._conversational) < n:
            return

        oldest = self._conversational[:n]
        self._conversational = self._conversational[n:]

        # Compress into a summary
        summary_parts = []
        for turn in oldest:
            prefix = "User" if turn["role"] == "user" else self.agent_id.capitalize()
            summary_parts.append(f"{prefix}: {turn['content'][:100]}")

        summary = " | ".join(summary_parts)
        content = f"Archived conversation from {oldest[0]['ts']}: {summary}"

        # Store as archival memory
        try:
            memory = AgentMemory(
                id=str(uuid.uuid4()),
                agent_id=self.agent_id,
                memory_type=MemoryType.EPISODIC,
                content=content,
                summary=summary[:200],
                source_platform=Platform.WEB if hasattr(Platform, "WEB") else list(Platform)[0],
                importance=0.4,
                tags=["archived_conversation"],
                privacy_level=PrivacyLevel.SEMI_PRIVATE,
            )
            await self.memory_service._store(memory)
            logger.debug("Archived %d turns for agent %s", n, self.agent_id)
        except Exception as e:
            logger.warning("Failed to archive conversational turns: %s", e)

    # ── Archival Memory ────────────────────────────────────────────────────

    async def search_archival(self, query: str, limit: int = 5) -> list[AgentMemory]:
        """
        Search archival memories by relevance to query.

        Uses intent-aware composite scoring.  The query is classified into one of
        five intent buckets (episodic_recall / factual_lookup / preference_check /
        task_context / default) and the semantic/recency/importance weights are
        adjusted accordingly.  Falls back to keyword scoring when VectorStore is
        unavailable.
        """
        await self._ensure_restored()
        try:
            all_memories = await self.memory_service.retrieve_memories(self.agent_id, limit=100)
        except Exception as e:
            logger.warning("Archival search failed: %s", e)
            return []

        if not all_memories:
            return []

        # Intent-aware weights (SimpleMem-inspired)
        weights = _classify_retrieval_intent(query)
        w_semantic = weights["semantic"]
        w_recency = weights["recency"]
        w_importance = weights["importance"]

        # Try semantic scoring via VectorStore
        semantic_scores = self._get_semantic_scores(query, all_memories)

        scored: list[tuple] = []
        now = datetime.now(UTC)

        for mem in all_memories:
            semantic = semantic_scores.get(mem.id, 0.0)

            # If no vector scores, fall back to keyword overlap
            if not semantic_scores:
                query_words = set(query.lower().split())
                content_words = set(mem.content.lower().split())
                summary_words = set(mem.summary.lower().split())
                overlap = len(query_words & (content_words | summary_words))
                semantic = overlap / max(len(query_words), 1)

            # Tag match bonus
            tag_match = any(tag.lower() in query.lower() for tag in mem.tags)
            tag_bonus = 0.1 if tag_match else 0.0

            # Recency factor (decays to 0 over 30 days)
            age_days = (now - mem.created_at).total_seconds() / 86400
            recency = max(0.0, 1.0 - (age_days / 30.0))

            # Importance (use current decay-adjusted importance)
            importance = mem.calculate_current_importance()

            # Intent-aware composite score
            score = (semantic + tag_bonus) * w_semantic + recency * w_recency + importance * w_importance

            if score > 0.01:
                scored.append((score, mem))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored[:limit]]

    @staticmethod
    def _get_semantic_scores(query: str, memories: list[AgentMemory]) -> dict[str, float]:
        """Get semantic similarity scores for memories against a query.

        Returns {memory_id: score} dict. Empty dict if VectorStore unavailable.
        """
        try:
            from apps.backend.core.vector_store import vector_store

            if vector_store is None:
                return {}

            results = vector_store.search(query, top_k=50)
            scores = {}
            for hit in results:
                doc_id = hit.get("id", "")
                if doc_id.startswith("mem:"):
                    mem_id = doc_id[4:]
                    scores[mem_id] = hit.get("score", 0.0)
            return scores
        except ImportError:
            return {}
        except Exception as exc:
            logger.debug("Vector search for consolidation scores failed: %s", exc)
            return {}

    # ── Prompt Formatting ─────────────────────────────────────────────────

    async def format_for_prompt(self, query: str = "") -> str:
        """
        Format memory tiers into a string block for LLM system prompt injection.

        Returns an empty string if no meaningful memories exist.
        """
        await self._ensure_restored()
        parts: list[str] = []

        # Core memory block
        if self._core:
            core_lines = [f"  - {k}: {v.value}" for k, v in self._core.items()]
            parts.append("### Core Memory (always active)\n" + "\n".join(core_lines))

        # Recent conversational context (last 5 turns only, to keep prompt tight)
        if self._conversational:
            recent = self._conversational[-5:]
            conv_lines = []
            for turn in recent:
                prefix = "User" if turn["role"] == "user" else "You"
                conv_lines.append(f"  {prefix}: {turn['content'][:200]}")
            parts.append("### Recent Context\n" + "\n".join(conv_lines))

        if not parts:
            return ""

        return "\n## Agent Memory\n" + "\n\n".join(parts) + "\n"

    async def format_for_prompt_with_archival(self, query: str) -> str:
        """
        Format all three memory tiers including archival search results.
        Slightly slower than format_for_prompt() due to archival DB query.
        """
        base = await self.format_for_prompt(query)
        archival = await self.search_archival(query, limit=3)

        if not archival:
            return base

        archival_lines = []
        for mem in archival:
            archival_lines.append(f"  [{mem.memory_type.value}] {mem.summary}")

        archival_block = "### Relevant Past Context\n" + "\n".join(archival_lines)

        if base:
            return base.rstrip() + "\n\n" + archival_block + "\n"
        return "\n## Agent Memory\n" + archival_block + "\n"


# ── Per-agent manager registry ─────────────────────────────────────────────

_three_tier_managers: dict[str, "ThreeTierMemoryManager"] = {}


def get_three_tier_manager(agent_id: str) -> "ThreeTierMemoryManager":
    """Get or create a ThreeTierMemoryManager for the given agent."""
    if agent_id not in _three_tier_managers:
        _three_tier_managers[agent_id] = ThreeTierMemoryManager(
            agent_id=agent_id,
            memory_service=get_memory_service(),
        )
    return _three_tier_managers[agent_id]


# Singleton instance
_memory_service: AgentMemoryService | None = None


def get_memory_service() -> AgentMemoryService:
    """Get or create the Agent Memory Service singleton"""
    global _memory_service
    if _memory_service is None:
        _memory_service = AgentMemoryService()
    return _memory_service
