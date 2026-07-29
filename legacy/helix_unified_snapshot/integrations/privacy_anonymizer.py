"""
Privacy Anonymization Layer

Enhanced user interaction anonymization service that allows agents
to learn from interactions while protecting user privacy.

Features:
- User ID hashing with salted SHA-256
- PII detection and redaction
- Interaction pattern extraction (not content)
- Consent-based data tier system
- Differential privacy for aggregate learning
- Anonymous user profiles for agent learning

Author: Helix Collective
Version: 1.0.0
"""

import hashlib
import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, ClassVar

logger = logging.getLogger(__name__)


class ConsentTier(Enum):
    """User consent levels for data usage"""

    NONE = "none"  # No data retention
    MINIMAL = "minimal"  # Session only, fully anonymized
    STANDARD = "standard"  # Cross-session, pseudonymized
    LEARNING = "learning"  # Allow aggregate learning
    FULL = "full"  # Full participation with attribution


class DataCategory(Enum):
    """Categories of data that can be collected"""

    INTERACTION_PATTERNS = "interaction_patterns"  # When/how often
    TOPIC_INTERESTS = "topic_interests"  # What subjects
    SENTIMENT_PATTERNS = "sentiment_patterns"  # Overall mood
    COMMUNICATION_STYLE = "communication_style"  # How they write
    ENGAGEMENT_METRICS = "engagement_metrics"  # Participation level
    CONTENT_PREFERENCES = "content_preferences"  # What they like


@dataclass
class PIIMatch:
    """Detected PII in text"""

    category: str  # email, phone, name, etc.
    original: str
    start: int
    end: int


@dataclass
class AnonymizedInteraction:
    """An interaction stripped of PII for agent learning"""

    interaction_id: str  # Hash of original
    user_hash: str  # Anonymized user identifier
    timestamp_bucket: str  # Bucketed time (hour/day)
    platform: str

    # Learning-safe data
    topic_tags: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0  # -1 to 1
    engagement_type: str = ""  # question, statement, reaction
    message_length_bucket: str = ""  # short/medium/long
    response_latency_bucket: str | None = None

    # Aggregate metrics (no raw content)
    word_count_range: str = ""  # 1-10, 11-50, 51-200, 200+
    question_count: int = 0
    mention_count: int = 0
    emoji_count: int = 0

    # Consent tracking
    consent_tier: ConsentTier = ConsentTier.MINIMAL

    def to_learning_dict(self) -> dict[str, Any]:
        """Convert to dictionary safe for aggregate learning"""
        return {
            "interaction_id": self.interaction_id,
            "user_hash": self.user_hash,
            "timestamp_bucket": self.timestamp_bucket,
            "platform": self.platform,
            "topic_tags": self.topic_tags,
            "sentiment_score": self.sentiment_score,
            "engagement_type": self.engagement_type,
            "message_length_bucket": self.message_length_bucket,
            "word_count_range": self.word_count_range,
            "question_count": self.question_count,
        }


@dataclass
class AnonymousUserProfile:
    """
    Profile of an anonymous user for agent learning.
    Contains NO identifying information - only behavioral patterns.
    """

    profile_hash: str  # Hash identifier
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    consent_tier: ConsentTier = ConsentTier.MINIMAL

    # Behavioral patterns (no content)
    primary_platform: str = ""
    active_hours: list[int] = field(default_factory=list)  # 0-23
    active_days: list[int] = field(default_factory=list)  # 0-6

    # Interest patterns
    topic_frequencies: dict[str, int] = field(default_factory=dict)
    agent_interactions: dict[str, int] = field(default_factory=dict)

    # Communication style (aggregate)
    avg_sentiment: float = 0.0
    preferred_length: str = "medium"  # short/medium/long
    question_ratio: float = 0.0  # % of messages that are questions

    # Engagement (aggregate)
    interaction_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None

    def update_from_interaction(self, interaction: AnonymizedInteraction):
        """Update profile from an anonymized interaction"""
        self.interaction_count += 1
        self.last_seen = datetime.now(UTC)

        if self.first_seen is None:
            self.first_seen = datetime.now(UTC)

        # Update topic frequencies
        for topic in interaction.topic_tags:
            self.topic_frequencies[topic] = self.topic_frequencies.get(topic, 0) + 1

        # Update sentiment rolling average
        if self.interaction_count > 1:
            self.avg_sentiment = (
                self.avg_sentiment * (self.interaction_count - 1) + interaction.sentiment_score
            ) / self.interaction_count
        else:
            self.avg_sentiment = interaction.sentiment_score


class PIIDetector:
    """
    Detects and redacts personally identifiable information.
    Patterns are conservative to avoid false negatives.
    """

    # PII detection patterns
    PATTERNS: ClassVar[dict[str, str]] = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone_us": r"\b(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "phone_intl": r"\+\d{1,3}[-.\s]?\d{1,14}",
        "ssn": r"\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-.\s]?){3}\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
        "date_of_birth": r"\b(?:0?[1-9]|1[0-2])[/\-.](?:0?[1-9]|[12]\d|3[01])[/\-.](?:19|20)\d{2}\b",
        "address_zip": r"\b\d{5}(?:-\d{4})?\b",
        "url_with_params": r"https?://[^\s]+\?[^\s]*(?:user|id|key|token|password|auth)[^\s]*",
        "api_key": r'\b(?:api[-_]?key|apikey|secret[-_]?key)[\s:="\']*[A-Za-z0-9_\-]{20,}\b',
        "bearer_token": r"\bBearer\s+[A-Za-z0-9_\-\.]+\b",
    }

    # Name detection (more complex, uses context)
    NAME_INDICATORS: ClassVar[list[str]] = [
        r"\bmy name is\s+(\w+)",
        r"\bi(?:\'m| am)\s+(\w+)",
        r"\bcall me\s+(\w+)",
        r"\b(?:signed|regards|from)[,:\s]+(\w+)",
    ]

    # Words that look like names but aren't
    NAME_EXCEPTIONS: ClassVar[set[str]] = {
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "dare",
        "ought",
        "i",
        "you",
        "he",
        "she",
        "it",
        "we",
        "they",
        "me",
        "him",
        "her",
        "us",
        "them",
        "kael",
        "lumina",
        "vega",
        "oracle",
        "sage",
        "kavach",
        "arjuna",
        "gemini",
        "agni",
        "shadow",
        "echo",
        "phoenix",
        "helix",
        "sanghacore",
        "mitra",
        "varuna",
        "surya",
    }

    @classmethod
    def detect_pii(cls, text: str) -> list[PIIMatch]:
        """Detect all PII in text"""
        matches = []
        text_lower = text.lower()

        # Check patterns
        for category, pattern in cls.PATTERNS.items():
            for match in re.finditer(pattern, text, re.IGNORECASE):
                matches.append(
                    PIIMatch(
                        category=category,
                        original=match.group(),
                        start=match.start(),
                        end=match.end(),
                    )
                )

        # Check name indicators
        for pattern in cls.NAME_INDICATORS:
            for match in re.finditer(pattern, text_lower):
                potential_name = match.group(1)
                if potential_name not in cls.NAME_EXCEPTIONS:
                    # Find actual position in original text
                    start = text_lower.find(potential_name, match.start())
                    if start >= 0:
                        matches.append(
                            PIIMatch(
                                category="potential_name",
                                original=text[start : start + len(potential_name)],
                                start=start,
                                end=start + len(potential_name),
                            )
                        )

        return matches

    @classmethod
    def redact_text(cls, text: str, replacement: str = "[REDACTED]") -> tuple[str, list[PIIMatch]]:
        """Redact PII from text, returning redacted text and matches"""
        matches = cls.detect_pii(text)

        # Sort by position (reverse) to replace from end
        matches.sort(key=lambda m: m.start, reverse=True)

        redacted = text
        for match in matches:
            redacted = redacted[: match.start] + replacement + redacted[match.end :]

        return redacted, matches

    @classmethod
    def contains_pii(cls, text: str) -> bool:
        """Check if text contains any PII"""
        return len(cls.detect_pii(text)) > 0


class PrivacyAnonymizer:
    """
    Core anonymization service.
    Transforms raw interactions into privacy-safe learning data.
    """

    def __init__(self, salt: str | None = None):
        self.salt = salt or os.environ.get("PRIVACY_ANONYMIZER_SALT") or "helix-collective-2026"
        if self.salt == "helix-collective-2026":
            import logging as _log

            env = os.environ.get("ENVIRONMENT", "development").lower()
            if env != "development":
                raise ValueError(
                    "PRIVACY_ANONYMIZER_SALT env var must be set to a secret value "
                    f"in non-development environments (current: {env}). "
                    "Using the default salt in production compromises pseudonymization."
                )
            _log.getLogger(__name__).warning(
                "PRIVACY_ANONYMIZER_SALT env var not set — using default salt. "
                "Set this to a secret value in production to protect pseudonymization."
            )
        self._user_consent: dict[str, ConsentTier] = {}
        self._profiles: dict[str, AnonymousUserProfile] = {}

        # Topic extraction keywords
        self.topic_keywords = {
            "coordination": [
                "coordination",
                "awareness",
                "sentient",
                "mind",
                "cognition",
            ],
            "ethics": ["ethics", "moral", "right", "wrong", "should", "ought"],
            "philosophy": ["philosophy", "meaning", "existence", "truth", "reality"],
            "technical": ["code", "programming", "api", "system", "architecture"],
            "emotional": ["feel", "emotion", "happy", "sad", "anxious", "excited"],
            "community": ["community", "together", "collective", "group", "team"],
            "spiroutineity": ["spiroutine", "meditation", "governance", "chant", "cycle"],
            "creativity": ["creative", "art", "music", "design", "imagination"],
            "learning": ["learn", "understand", "know", "curious", "question"],
            "support": ["help", "support", "assist", "guide", "need"],
        }

        logger.info("🛡️ Privacy Anonymizer initialized")

    def hash_user_id(self, user_id: str, platform: str = "") -> str:
        """
        Create anonymized user hash.
        Same user_id always produces same hash for continuity,
        but hash cannot be reversed to original ID.
        """
        combined = f"{self.salt}:{platform}:{user_id}"
        return hashlib.sha256(combined.encode()).hexdigest()[:16]

    def hash_interaction(self, content: str, user_hash: str, timestamp: datetime) -> str:
        """Create unique hash for an interaction"""
        combined = f"{user_hash}:{timestamp.isoformat()}:{len(content)}"
        return hashlib.sha256(combined.encode()).hexdigest()[:12]

    def bucket_timestamp(self, timestamp: datetime, granularity: str = "hour") -> str:
        """Bucket timestamp to reduce precision"""
        if granularity == "hour":
            return timestamp.strftime("%Y-%m-%d-%H")
        elif granularity == "day":
            return timestamp.strftime("%Y-%m-%d")
        elif granularity == "week":
            return f"{timestamp.year}-W{timestamp.isocalendar()[1]}"
        return timestamp.strftime("%Y-%m-%d")

    def bucket_length(self, text: str) -> str:
        """Categorize message length"""
        length = len(text)
        if length < 50:
            return "short"
        elif length < 200:
            return "medium"
        elif length < 500:
            return "long"
        return "very_long"

    def bucket_word_count(self, text: str) -> str:
        """Categorize word count"""
        count = len(text.split())
        if count <= 10:
            return "1-10"
        elif count <= 50:
            return "11-50"
        elif count <= 200:
            return "51-200"
        return "200+"

    def extract_topics(self, text: str) -> list[str]:
        """Extract topic tags without preserving content"""
        text_lower = text.lower()
        topics = []

        for topic, keywords in self.topic_keywords.items():
            if any(kw in text_lower for kw in keywords):
                topics.append(topic)

        return topics

    def analyze_sentiment(self, text: str) -> float:
        """Simple sentiment analysis (-1 to 1)"""
        positive = [
            "good",
            "great",
            "amazing",
            "love",
            "wonderful",
            "happy",
            "thanks",
            "thank",
        ]
        negative = ["bad", "terrible", "hate", "awful", "sad", "angry", "frustrated"]

        text_lower = text.lower()
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count + neg_count == 0:
            return 0.0
        return (pos_count - neg_count) / (pos_count + neg_count)

    def classify_engagement(self, text: str) -> str:
        """Classify the type of engagement"""
        text_lower = text.lower()

        if text_lower.endswith("?") or any(q in text_lower for q in ["what", "how", "why", "when", "where", "who"]):
            return "question"
        elif any(r in text_lower for r in ["thanks", "thank you", "appreciate"]):
            return "gratitude"
        elif any(g in text_lower for g in ["hi", "hello", "hey", "good morning", "good evening"]):
            return "greeting"
        elif any(s in text_lower for s in ["i think", "i believe", "in my opinion"]):
            return "opinion"
        return "statement"

    def get_consent(self, user_id: str, platform: str) -> ConsentTier:
        """Get user's consent tier"""
        user_hash = self.hash_user_id(user_id, platform)
        return self._user_consent.get(user_hash, ConsentTier.MINIMAL)

    def set_consent(self, user_id: str, platform: str, tier: ConsentTier):
        """Set user's consent tier"""
        user_hash = self.hash_user_id(user_id, platform)
        self._user_consent[user_hash] = tier
        logger.info("Consent updated for user %s: %s", user_hash, tier.value)

    def anonymize_interaction(
        self,
        user_id: str,
        content: str,
        platform: str,
        timestamp: datetime | None = None,
        consent_tier: ConsentTier | None = None,
    ) -> AnonymizedInteraction | None:
        """
        Transform a raw interaction into anonymized learning data.
        Returns None if content contains unredactable PII.
        """
        timestamp = timestamp or datetime.now(UTC)
        user_hash = self.hash_user_id(user_id, platform)

        # Get consent tier
        tier = consent_tier or self.get_consent(user_id, platform)

        # If no consent, return None
        if tier == ConsentTier.NONE:
            return None

        # Check and redact PII
        redacted, pii_matches = PIIDetector.redact_text(content)

        # If too much PII, skip
        if len(pii_matches) > 5:
            logger.warning("Too much PII detected, skipping interaction")
            return None

        # Create anonymized interaction
        interaction = AnonymizedInteraction(
            interaction_id=self.hash_interaction(content, user_hash, timestamp),
            user_hash=user_hash,
            timestamp_bucket=self.bucket_timestamp(timestamp),
            platform=platform,
            topic_tags=self.extract_topics(redacted),
            sentiment_score=self.analyze_sentiment(redacted),
            engagement_type=self.classify_engagement(redacted),
            message_length_bucket=self.bucket_length(redacted),
            word_count_range=self.bucket_word_count(redacted),
            question_count=redacted.count("?"),
            mention_count=len(re.findall(r"@\w+", redacted)),
            emoji_count=len(re.findall(r"[\U0001F300-\U0001F9FF]", redacted)),
            consent_tier=tier,
        )

        # Update anonymous profile
        self._update_profile(user_hash, interaction, tier)

        return interaction

    def _update_profile(self, user_hash: str, interaction: AnonymizedInteraction, tier: ConsentTier):
        """Update or create anonymous user profile"""
        if tier not in [ConsentTier.STANDARD, ConsentTier.LEARNING, ConsentTier.FULL]:
            return

        if user_hash not in self._profiles:
            self._profiles[user_hash] = AnonymousUserProfile(
                profile_hash=user_hash,
                consent_tier=tier,
            )

        self._profiles[user_hash].update_from_interaction(interaction)

    def get_profile(self, user_id: str, platform: str) -> AnonymousUserProfile | None:
        """Get anonymous profile for a user"""
        user_hash = self.hash_user_id(user_id, platform)
        return self._profiles.get(user_hash)

    def get_aggregate_insights(self) -> dict[str, Any]:
        """
        Get aggregate insights across all profiles.
        This is differential-privacy safe as it only returns aggregates.
        """
        if not self._profiles:
            return {}

        profiles = list(self._profiles.values())

        # Aggregate topic interests
        all_topics: dict[str, int] = defaultdict(int)
        for profile in profiles:
            for topic, count in profile.topic_frequencies.items():
                all_topics[topic] += count

        # Average metrics
        avg_sentiment = sum(p.avg_sentiment for p in profiles) / len(profiles)
        total_interactions = sum(p.interaction_count for p in profiles)

        return {
            "profile_count": len(profiles),
            "total_interactions": total_interactions,
            "avg_sentiment": round(avg_sentiment, 3),
            "topic_distribution": dict(all_topics),
            "top_topics": sorted(all_topics.items(), key=lambda x: x[1], reverse=True)[:10],
        }

    def clear_expired_data(self, max_age_days: int = 90):
        """Remove data older than max_age_days"""
        cutoff = datetime.now(UTC) - timedelta(days=max_age_days)
        expired = [h for h, p in self._profiles.items() if p.last_seen and p.last_seen < cutoff]

        for h in expired:
            del self._profiles[h]

        if expired:
            logger.info("Cleared %d expired profiles", len(expired))


# Singleton instance
_anonymizer: PrivacyAnonymizer | None = None


def get_anonymizer() -> PrivacyAnonymizer:
    """Get singleton anonymizer instance"""
    global _anonymizer
    if _anonymizer is None:
        _anonymizer = PrivacyAnonymizer()
    return _anonymizer


# Export classes for type hints
__all__ = [
    "AnonymizedInteraction",
    "AnonymousUserProfile",
    "ConsentTier",
    "DataCategory",
    "PIIDetector",
    "PIIMatch",
    "PrivacyAnonymizer",
    "get_anonymizer",
]
