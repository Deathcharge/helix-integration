# pylint: disable=not-callable  # SQLAlchemy func.count is a dynamic callable
"""
Helix Collective SaaS - Multi-LLM Smart Router
==============================================

Intelligent routing to optimal LLM based on:
- Cost optimization
- Speed optimization
- Quality optimization
- User tier restrictions

Author: Claude (Helix Validator)
Date: 2025-11-30
"""

import logging
import os
import time
from datetime import UTC
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field

# Import auth system
from apps.backend.core.unified_auth import track_usage
from apps.backend.services.unified_llm import unified_llm
from apps.backend.utils.safe_error_utils import SafeErrorResponse

_saas_logger = logging.getLogger(__name__)


# ============================================================================
# USER ROUTING PROFILE LOOKUP
# ============================================================================


async def _get_user_routing_preference(user_id: str) -> str | None:
    """
    Look up the user's saved routing profile and return the preferred model.

    When a user selects a routing profile (e.g. "ethics", "tapas") via the
    CoordinationRoutingSelector, the profile's primary_model is persisted in
    user_llm_preferences. This function retrieves that model so the chat
    endpoint can honour the selection.

    Returns:
        The preferred model string, or None to fall back to auto-routing.
    """
    if not user_id or user_id == "anonymous":
        return None
    try:
        from sqlalchemy import text

        from apps.backend.db_models import get_db_session

        async with get_db_session() as db:
            result = await db.execute(
                text(
                    "SELECT preferred_model FROM user_llm_preferences"
                    " WHERE user_id = :uid OR discord_user_id = :uid LIMIT 1"
                ),
                {"uid": user_id},
            )
            row = result.fetchone()
            if row and row[0]:
                return row[0]
    except Exception as e:
        _saas_logger.debug("Could not fetch user routing preference: %s", e)
    return None


# ============================================================================
# CONFIGURATION
# ============================================================================

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
XAI_API_KEY = os.getenv("XAI_API_KEY")  # Grok
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

# ============================================================================
# PYDANTIC MODELS
# ============================================================================


class Message(BaseModel):
    """Chat message"""

    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    """Chat completion request"""

    messages: list[Message]
    optimize: Literal["cost", "speed", "quality", "auto"] = "auto"
    model: str | None = None  # Specific model or None for auto-route
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1000, ge=1, le=4096)
    stream: bool = False


class ChatResponse(BaseModel):
    """Chat completion response"""

    id: str
    model: str
    provider: str
    choices: list[dict[str, Any]]
    usage: dict[str, int]
    cost_usd: float
    response_time_ms: int
    optimize_mode: str


# ============================================================================
# MODEL ROUTING LOGIC
# ============================================================================

# All local models running via llama.cpp on Oracle Cloud ARM (4C/24GB).
# Free tier users ONLY get these; paid API models require hobby+.
LOCAL_MODEL_IDS = frozenset(
    {
        "helix-ai",
        "phi-3-mini",
        "qwen2.5-3b",
        "qwen2.5-1.5b",
        "qwen2.5-coder-3b",
        "qwen2.5-coder-1.5b",
        "tinyllama",
    }
)

CEREBRAS_MODEL_IDS = frozenset({"gpt-oss-120b", "zai-glm-4.7"})

GROQ_MODEL_IDS = frozenset(
    {
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "groq/compound",
        "groq/compound-mini",
        "qwen/qwen3-32b",
    }
)

# Model costs (per 1M tokens) - Updated April 2026
MODEL_PRICING = {
    # Local models (free — CPU inference on Oracle ARM)
    "helix-ai": {"input": 0.00, "output": 0.00},
    "phi-3-mini": {"input": 0.00, "output": 0.00},
    "qwen2.5-3b": {"input": 0.00, "output": 0.00},
    "qwen2.5-1.5b": {"input": 0.00, "output": 0.00},
    "qwen2.5-coder-3b": {"input": 0.00, "output": 0.00},
    "qwen2.5-coder-1.5b": {"input": 0.00, "output": 0.00},
    "tinyllama": {"input": 0.00, "output": 0.00},
    # xAI / Grok
    "grok-4-1-fast-reasoning": {"input": 0.20, "output": 0.50},
    "grok-code-fast-1": {"input": 0.20, "output": 1.50},
    "grok-3-mini": {"input": 0.30, "output": 0.50},
    "grok-3": {"input": 3.00, "output": 15.00},
    # Google Gemini
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    # Anthropic Claude
    "claude-opus-4-6": {"input": 5.00, "output": 25.00},
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    # OpenAI
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "o3": {"input": 10.00, "output": 40.00},
    "o4-mini": {"input": 1.10, "output": 4.40},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    # DeepSeek
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
    # Mistral
    "mistral-large-latest": {"input": 2.00, "output": 6.00},
    "codestral-latest": {"input": 0.30, "output": 0.90},
    "mistral-small-latest": {"input": 0.10, "output": 0.30},
    # Cerebras (wafer-scale inference — free tier available)
    "gpt-oss-120b": {"input": 0.10, "output": 0.10},
    "zai-glm-4.7": {"input": 0.60, "output": 0.60},
    # Groq (inference cost per million tokens — very cheap)
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "meta-llama/llama-4-scout-17b-16e-instruct": {"input": 0.11, "output": 0.34},
    "groq/compound": {"input": 0.00, "output": 0.00},
    "groq/compound-mini": {"input": 0.00, "output": 0.00},
    "qwen/qwen3-32b": {"input": 0.29, "output": 0.59},
    # Perplexity (online search-augmented)
    "sonar-pro": {"input": 3.00, "output": 15.00},
    "sonar": {"input": 1.00, "output": 1.00},
}

# Model performance scores (0-100, higher = better)
MODEL_SCORES = {
    # Cost score (higher = cheaper)
    "cost": {
        "helix-ai": 100,  # Free — local inference
        "phi-3-mini": 100,
        "qwen2.5-3b": 100,
        "qwen2.5-1.5b": 100,
        "qwen2.5-coder-3b": 100,
        "qwen2.5-coder-1.5b": 100,
        "tinyllama": 100,
        "gemini-2.5-flash": 98,
        "gemini-2.0-flash": 97,
        "gpt-4.1-nano": 97,
        "deepseek-chat": 96,
        "grok-4-1-fast-reasoning": 95,
        "grok-3-mini": 94,
        "grok-code-fast-1": 93,
        "mistral-small-latest": 93,
        "gpt-4o-mini": 92,
        "gpt-4.1-mini": 90,
        "codestral-latest": 89,
        "claude-haiku-4-5": 88,
        "sonar": 87,
        "llama-3.3-70b-versatile": 86,
        "groq/compound": 85,
        "groq/compound-mini": 84,
        "meta-llama/llama-4-scout-17b-16e-instruct": 83,
        "qwen/qwen3-32b": 82,
        "llama-3.1-8b-instant": 97,  # Very cheap inference
        "gpt-oss-120b": 96,  # Cerebras fast path
        "zai-glm-4.7": 80,
        "deepseek-reasoner": 82,
        "o4-mini": 80,
        "gemini-2.5-pro": 75,
        "gpt-4.1": 70,
        "mistral-large-latest": 68,
        "gpt-4o": 60,
        "grok-3": 50,
        "claude-sonnet-4-6": 48,
        "claude-sonnet-4-5": 47,
        "sonar-pro": 45,
        "claude-opus-4-6": 25,
        "o3": 20,
    },
    # Speed score (higher = faster)
    "speed": {
        "gemini-2.5-flash": 97,
        "grok-3-mini": 95,
        "gemini-2.0-flash": 94,
        "gpt-4.1-nano": 93,
        "grok-4-1-fast-reasoning": 92,
        "gpt-4o-mini": 91,
        "gpt-4.1-mini": 90,
        "grok-code-fast-1": 89,
        "gpt-oss-120b": 97,  # Cerebras wafer-scale — extremely fast
        "llama-3.1-8b-instant": 96,  # Groq 8b — fastest option
        "groq/compound-mini": 95,
        "llama-3.3-70b-versatile": 90,  # Groq inference is very fast
        "groq/compound": 89,
        "meta-llama/llama-4-scout-17b-16e-instruct": 88,
        "qwen/qwen3-32b": 87,
        "mistral-small-latest": 88,
        "claude-haiku-4-5": 87,
        "deepseek-chat": 85,
        "codestral-latest": 84,
        "sonar": 83,
        "gpt-4.1": 82,
        "gpt-4o": 80,
        "gemini-2.5-pro": 78,
        "o4-mini": 77,
        "claude-sonnet-4-6": 75,
        "claude-sonnet-4-5": 74,
        "mistral-large-latest": 73,
        "grok-3": 72,
        "sonar-pro": 70,
        "deepseek-reasoner": 68,
        "helix-ai": 65,  # Local CPU inference — moderate
        "phi-3-mini": 60,
        "qwen2.5-3b": 58,
        "qwen2.5-1.5b": 70,
        "qwen2.5-coder-3b": 58,
        "qwen2.5-coder-1.5b": 70,
        "tinyllama": 80,
        "claude-opus-4-6": 60,
        "o3": 55,
    },
    # Quality score (higher = better)
    "quality": {
        "claude-opus-4-6": 99,
        "o3": 98,
        "claude-sonnet-4-6": 96,
        "gemini-2.5-pro": 95,
        "claude-sonnet-4-5": 94,
        "gpt-4.1": 93,
        "gpt-4o": 92,
        "grok-3": 91,
        "deepseek-reasoner": 90,
        "o4-mini": 89,
        "mistral-large-latest": 88,
        "grok-4-1-fast-reasoning": 87,
        "grok-code-fast-1": 85,
        "sonar-pro": 83,
        "deepseek-chat": 80,
        "groq/compound": 82,
        "llama-3.3-70b-versatile": 79,
        "meta-llama/llama-4-scout-17b-16e-instruct": 78,
        "qwen/qwen3-32b": 78,
        "claude-haiku-4-5": 78,
        "groq/compound-mini": 74,
        "llama-3.1-8b-instant": 65,
        "gpt-oss-120b": 66,
        "zai-glm-4.7": 84,
        "codestral-latest": 77,
        "gemini-2.5-flash": 76,
        "gpt-4o-mini": 75,
        "gpt-4.1-mini": 75,
        "gemini-2.0-flash": 74,
        "grok-3-mini": 73,
        "sonar": 72,
        "mistral-small-latest": 70,
        "gpt-4.1-nano": 65,
        "helix-ai": 55,  # Small local model — decent for free tier
        "phi-3-mini": 52,
        "qwen2.5-3b": 58,
        "qwen2.5-1.5b": 45,
        "qwen2.5-coder-3b": 60,
        "qwen2.5-coder-1.5b": 48,
        "tinyllama": 35,
    },
}

# Tier restrictions — free tier gets LOCAL models only; paid API models require hobby+
TIER_MODELS = {
    "free": list(LOCAL_MODEL_IDS),
    "hobby": [
        # All local models
        *LOCAL_MODEL_IDS,
        # Cheap paid API models (hobby unlocks external providers)
        "grok-4-1-fast-reasoning",
        "grok-code-fast-1",
        "grok-3-mini",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gpt-4o-mini",
        "gpt-4.1-nano",
        "gpt-4.1-mini",
        "deepseek-chat",
        "deepseek-reasoner",
        "mistral-small-latest",
        "codestral-latest",
        "claude-haiku-4-5",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "groq/compound",
        "groq/compound-mini",
        "qwen/qwen3-32b",
        "gpt-oss-120b",
        "zai-glm-4.7",
        "sonar",
    ],
    "builder": [
        # All local models
        *LOCAL_MODEL_IDS,
        "grok-3-mini",
        "grok-3",
        "grok-4-1-fast-reasoning",
        "grok-code-fast-1",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gpt-4o-mini",
        "gpt-4.1-nano",
        "gpt-4.1-mini",
        "gpt-4.1",
        "gpt-4o",
        "o4-mini",
        "deepseek-chat",
        "deepseek-reasoner",
        "mistral-small-latest",
        "mistral-large-latest",
        "codestral-latest",
        "claude-haiku-4-5",
        "claude-sonnet-4-5",
        "claude-sonnet-4-6",
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "groq/compound",
        "groq/compound-mini",
        "qwen/qwen3-32b",
        "gpt-oss-120b",
        "zai-glm-4.7",
        "sonar",
        "sonar-pro",
    ],
    "pro": None,  # All models
    "workflow": None,  # All models
    "enterprise": None,  # All models
}


def _infer_tier_requirement(model: str) -> str:
    """Infer the minimum tier required for a model based on TIER_MODELS lists."""
    if model in (TIER_MODELS["free"] or []):
        return "free"
    if model in (TIER_MODELS["hobby"] or []):
        return "hobby"
    if model in (TIER_MODELS["builder"] or []):
        return "builder"
    return "pro"  # default to pro when not in lower tiers


def _provider_for_model(model: str) -> str:
    """Determine the provider for a given model ID."""
    if model in LOCAL_MODEL_IDS:
        return "local"
    if model in CEREBRAS_MODEL_IDS:
        return "cerebras"
    if model in GROQ_MODEL_IDS:
        return "groq"
    if "helix" in model:
        return "local"
    if "claude" in model:
        return "anthropic"
    if model.startswith(("gpt-", "o3", "o4-")):
        return "openai"
    if "grok" in model:
        return "xai"
    if "gemini" in model:
        return "google"
    if "deepseek" in model:
        return "deepseek"
    if "mistral" in model or "codestral" in model:
        return "mistral"
    if "sonar" in model:
        return "perplexity"
    if "/" in model:
        return "openrouter"
    return "openrouter"


# Model metadata — display names, context windows, capabilities
# Used by /api/llm/routing/models endpoint for the dynamic model catalogue.
MODEL_METADATA: dict[str, dict[str, Any]] = {
    "helix-ai": {"name": "Praxis", "context_window": 32_768, "capabilities": ["code", "reasoning", "writing"]},
    "phi-3-mini": {"name": "Phi-3 Mini", "context_window": 4_096, "capabilities": ["code"], "hidden": True},
    "qwen2.5-3b": {"name": "Qwen 2.5 3B", "context_window": 32_768, "capabilities": ["code"], "hidden": True},
    "qwen2.5-1.5b": {"name": "Helix Nano", "context_window": 32_768, "capabilities": ["writing"]},
    "qwen2.5-coder-3b": {"name": "Helix Coder", "context_window": 32_768, "capabilities": ["code", "tools"]},
    "qwen2.5-coder-1.5b": {
        "name": "Qwen 2.5 Coder 1.5B",
        "context_window": 32_768,
        "capabilities": ["code"],
        "hidden": True,
    },
    "tinyllama": {"name": "TinyLlama 1.1B", "context_window": 4_096, "capabilities": [], "hidden": True},
    "grok-4-1-fast-reasoning": {
        "name": "Grok 4.1 Fast",
        "context_window": 2_000_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "grok-code-fast-1": {"name": "Grok Code Fast", "context_window": 256_000, "capabilities": ["code", "tools"]},
    "grok-3-mini": {"name": "Grok 3 Mini", "context_window": 131_000, "capabilities": ["tools", "code"]},
    "grok-3": {"name": "Grok 3", "context_window": 131_000, "capabilities": ["vision", "tools", "code"]},
    "gemini-2.5-flash": {
        "name": "Gemini 2.5 Flash",
        "context_window": 1_048_576,
        "capabilities": ["vision", "tools", "code", "search"],
    },
    "gemini-2.5-pro": {
        "name": "Gemini 2.5 Pro",
        "context_window": 1_000_000,
        "capabilities": ["vision", "tools", "code", "search"],
    },
    "gemini-2.0-flash": {
        "name": "Gemini 2.0 Flash",
        "context_window": 1_048_576,
        "capabilities": ["vision", "tools", "code", "search"],
    },
    "claude-opus-4-6": {
        "name": "Claude Opus 4.6",
        "context_window": 200_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "claude-sonnet-4-6": {
        "name": "Claude Sonnet 4.6",
        "context_window": 200_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "claude-haiku-4-5": {
        "name": "Claude Haiku 4.5",
        "context_window": 200_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "claude-sonnet-4-5": {
        "name": "Claude Sonnet 4.5",
        "context_window": 200_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "gpt-4.1": {"name": "GPT-4.1", "context_window": 1_047_576, "capabilities": ["vision", "tools", "code"]},
    "gpt-4.1-mini": {"name": "GPT-4.1 Mini", "context_window": 1_047_576, "capabilities": ["vision", "tools", "code"]},
    "gpt-4.1-nano": {"name": "GPT-4.1 Nano", "context_window": 1_047_576, "capabilities": ["tools", "code"]},
    "o3": {"name": "o3", "context_window": 200_000, "capabilities": ["vision", "tools", "code"]},
    "o4-mini": {"name": "o4 Mini", "context_window": 200_000, "capabilities": ["vision", "tools", "code"]},
    "gpt-4o": {"name": "GPT-4o", "context_window": 128_000, "capabilities": ["vision", "tools", "code"]},
    "gpt-4o-mini": {"name": "GPT-4o Mini", "context_window": 128_000, "capabilities": ["vision", "tools", "code"]},
    "deepseek-chat": {"name": "DeepSeek Chat", "context_window": 128_000, "capabilities": ["code"]},
    "deepseek-reasoner": {"name": "DeepSeek Reasoner", "context_window": 128_000, "capabilities": ["code"]},
    "mistral-large-latest": {
        "name": "Mistral Large",
        "context_window": 128_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "codestral-latest": {"name": "Codestral", "context_window": 256_000, "capabilities": ["code"]},
    "mistral-small-latest": {"name": "Mistral Small", "context_window": 128_000, "capabilities": ["tools", "code"]},
    "gpt-oss-120b": {
        "name": "GPT OSS 120B (Cerebras)",
        "context_window": 8_192,
        "capabilities": ["code"],
    },
    "zai-glm-4.7": {
        "name": "Z.ai GLM 4.7 (Cerebras)",
        "context_window": 65_536,
        "capabilities": ["tools", "code"],
    },
    "llama-3.3-70b-versatile": {"name": "Llama 3.3 70B", "context_window": 128_000, "capabilities": ["tools", "code"]},
    "llama-3.1-8b-instant": {"name": "Llama 3.1 8B Instant", "context_window": 128_000, "capabilities": ["code"]},
    "meta-llama/llama-4-scout-17b-16e-instruct": {
        "name": "Llama 4 Scout 17B",
        "context_window": 128_000,
        "capabilities": ["vision", "tools", "code"],
    },
    "groq/compound": {"name": "Groq Compound", "context_window": 128_000, "capabilities": ["tools", "code", "search"]},
    "groq/compound-mini": {
        "name": "Groq Compound Mini",
        "context_window": 128_000,
        "capabilities": ["tools", "code", "search"],
    },
    "qwen/qwen3-32b": {"name": "Qwen3 32B", "context_window": 128_000, "capabilities": ["tools", "code"]},
    "sonar-pro": {"name": "Sonar Pro", "context_window": 127_072, "capabilities": ["search"]},
    "sonar": {"name": "Sonar", "context_window": 127_072, "capabilities": ["search"]},
}


# Model profiles consolidate provider/tier and normalized performance scores (0-10 scale)
MODEL_PROFILES: dict[str, dict[str, Any]] = {}
for _model in MODEL_PRICING:
    quality_raw = MODEL_SCORES["quality"].get(_model, 50)
    speed_raw = MODEL_SCORES["speed"].get(_model, 50)
    MODEL_PROFILES[_model] = {
        "provider": _provider_for_model(_model),
        "tier_requirement": _infer_tier_requirement(_model),
        "quality_score": round(quality_raw / 10, 2),
        "speed_score": round(speed_raw / 10, 2),
    }


def route_to_best_model(optimize: str, tier: str, specific_model: str | None = None) -> tuple[str, str]:
    """
    Route to best model based on optimization mode and tier

    Args:
        optimize: 'cost', 'speed', or 'quality'
        tier: User tier ('free', 'pro', 'workflow', 'enterprise')
        specific_model: Specific model requested (or None for auto-route)

    Returns:
        (provider, model) tuple

    Raises:
        HTTPException if specific_model not allowed for tier
    """
    # If specific model requested, validate tier access
    if specific_model:
        allowed_models = TIER_MODELS.get(tier)
        if allowed_models is not None and specific_model not in allowed_models:
            required_tier = _infer_tier_requirement(specific_model)
            raise HTTPException(
                status_code=403,
                detail="Model '{}' requires {} tier or higher. Upgrade at {}/pricing".format(
                    specific_model,
                    required_tier.capitalize(),
                    os.getenv("FRONTEND_URL", "https://helixspiral.work").rstrip("/"),
                ),
            )

        return _provider_for_model(specific_model), specific_model

    # Auto-routing based on optimize mode
    if optimize == "free_balanced":
        # Composite: 70% cost + 30% quality — gives free users decent quality
        # without burning through credits on the cheapest/worst model.
        cost_scores = MODEL_SCORES.get("cost", {})
        quality_scores = MODEL_SCORES.get("quality", {})
        scores = {m: int(cost_scores.get(m, 50) * 0.7 + quality_scores.get(m, 50) * 0.3) for m in MODEL_PRICING}
    else:
        scores = MODEL_SCORES.get(optimize, MODEL_SCORES["cost"])
    allowed_models = TIER_MODELS.get(tier)

    # Filter by tier
    if allowed_models is not None:
        available_scores = {k: v for k, v in scores.items() if k in allowed_models}
    else:
        available_scores = scores

    if not available_scores:
        raise HTTPException(status_code=500, detail="No models available for your tier")

    # Check which providers are actually available (have API keys / local model loaded)
    live_providers = set(unified_llm.get_available_providers())

    # Sort candidates by score descending, pick the first whose provider is live
    sorted_candidates = sorted(available_scores.items(), key=lambda kv: kv[1], reverse=True)

    for candidate_model, _score in sorted_candidates:
        candidate_provider = _provider_for_model(candidate_model)
        if candidate_provider in live_providers:
            return candidate_provider, candidate_model

    # No provider is available — fall back to best-scored model and let the
    # downstream call_* function return a clear 503.
    best_model = sorted_candidates[0][0]
    return _provider_for_model(best_model), best_model


# ============================================================================
# LLM PROVIDER CALLS
# ============================================================================


async def call_anthropic(model: str, messages: list[Message], temperature: float, max_tokens: int) -> dict[str, Any]:
    """Call Anthropic Claude API via unified LLM service"""
    if "anthropic" not in unified_llm.get_available_providers():
        raise HTTPException(status_code=500, detail="Anthropic API key not configured")

    formatted_messages = []
    for msg in messages:
        formatted_messages.append({"role": msg.role, "content": msg.content})

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider="anthropic",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage,
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=SafeErrorResponse.sanitize_error(e)) from e


async def call_openai(model: str, messages: list[Message], temperature: float, max_tokens: int) -> dict[str, Any]:
    """Call OpenAI GPT API via unified LLM service"""
    if "openai" not in unified_llm.get_available_providers():
        raise HTTPException(status_code=500, detail="OpenAI API key not configured")

    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider="openai",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage,
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=SafeErrorResponse.sanitize_error(e)) from e


async def call_xai(model: str, messages: list[Message], temperature: float, max_tokens: int) -> dict[str, Any]:
    """Call xAI Grok API via unified LLM service"""
    if "xai" not in unified_llm.get_available_providers():
        raise HTTPException(status_code=500, detail="xAI API key not configured")

    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider="xai",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage,
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=SafeErrorResponse.sanitize_error(e)) from e


async def call_perplexity(model: str, messages: list[Message], temperature: float, max_tokens: int) -> dict[str, Any]:
    """Call Perplexity API via unified LLM service"""
    if "perplexity" not in unified_llm.get_available_providers():
        raise HTTPException(status_code=500, detail="Perplexity API key not configured")

    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider="perplexity",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage,
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=SafeErrorResponse.sanitize_error(e)) from e


async def call_local(model: str, messages: list[Message], temperature: float, max_tokens: int) -> dict[str, Any]:
    """Call Helix AI local LLM via unified LLM service (free tier)"""
    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider="local",
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception:
        # Local LLM failure — surface a friendly message
        raise HTTPException(
            status_code=500,
            detail="Helix AI local model unavailable. Try again shortly.",
        ) from None


async def call_generic_provider(
    provider: str, model: str, messages: list[Message], temperature: float, max_tokens: int
) -> dict[str, Any]:
    """Call any provider via unified LLM service (Google, OpenRouter, etc.)"""
    formatted_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

    try:
        resp = await unified_llm.chat_with_metadata(
            formatted_messages,
            model=model,
            provider=provider,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if resp.error:
            raise HTTPException(status_code=500, detail=resp.error)

        return {
            "content": resp.content,
            "usage": resp.usage or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            "finish_reason": resp.finish_reason,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=SafeErrorResponse.sanitize_error(e)) from e


# ============================================================================
# COST CALCULATION
# ============================================================================


def calculate_cost(model: str, usage: dict[str, int]) -> float:
    """
    Calculate cost in USD for a completion

    Args:
        model: Model name
        usage: Usage dict with input_tokens and output_tokens

    Returns:
        Cost in USD
    """
    pricing = MODEL_PRICING.get(model)
    if not pricing:
        return 0.0

    input_cost = (usage["input_tokens"] / 1_000_000) * pricing["input"]
    output_cost = (usage["output_tokens"] / 1_000_000) * pricing["output"]

    return round(input_cost + output_cost, 6)


# ============================================================================
# MAIN CHAT COMPLETION ENDPOINT
# ============================================================================


async def chat_completion(request: ChatRequest, user: dict[str, Any]) -> ChatResponse:
    """
    Handle chat completion request with smart routing

    Args:
        request: Chat request
        user: User data from auth middleware

    Returns:
        Chat response with model output and metadata
    """
    start_time = time.time()

    # When optimize="auto" and no specific model, consult the user's routing profile
    effective_model = request.model
    effective_optimize: str = request.optimize

    if effective_optimize == "auto" and not effective_model:
        profile_model = await _get_user_routing_preference(user.get("id") or user.get("user_id", "anonymous"))
        if profile_model:
            effective_model = profile_model

    # If still "auto" after profile lookup, use smart defaults per tier:
    # Free tier gets a composite cost+quality score so they get decent results
    # without burning money. Paid tiers get pure cost optimization.
    if effective_optimize == "auto":
        effective_optimize = "cost" if user.get("tier", "free") != "free" else "free_balanced"

    # Route to best model
    provider, model = route_to_best_model(
        optimize=effective_optimize, tier=user["tier"], specific_model=effective_model
    )

    # ── Credit pre-flight check ──
    user_id = user.get("id") or user.get("user_id", "anonymous")
    user_tier = user.get("tier", "free")

    if user_id != "anonymous":
        try:
            from apps.backend.database.connection import get_db_session
            from apps.backend.services.credit_service import CreditService

            async with get_db_session() as credit_session:
                credit_svc = CreditService(credit_session)

                # For paid API models, check credit balance
                if model not in LOCAL_MODEL_IDS:
                    cost_check = await credit_svc.check_request_cost(
                        user_id=user_id,
                        model_id=model,
                        input_tokens=sum(len(m.content.split()) * 4 for m in request.messages),
                        estimated_output_tokens=request.max_tokens,
                    )

                    if not cost_check.can_afford:
                        _saas_logger.info(
                            "User %s out of credits (need $%.4f) — falling back to local model",
                            user_id,
                            cost_check.cost,
                        )
                        provider, model = "local", "qwen2.5-3b"

                # Free tier: enforce daily request cap (local models included)
                if user_tier == "free":
                    from datetime import datetime

                    from sqlalchemy import and_, func, select

                    from apps.backend.db_models import APIUsage

                    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                    count_result = await credit_session.execute(
                        select(func.count()).where(
                            and_(
                                APIUsage.user_id == user_id,
                                APIUsage.created_at >= today_start,
                            )
                        )
                    )
                    daily_count = count_result.scalar_one()

                    if daily_count >= 100:
                        raise HTTPException(
                            status_code=429,
                            detail="Free tier daily limit reached (100 requests/day). "
                            "Upgrade to Hobby for 500 requests/day and access to premium models.",
                        )
        except HTTPException:
            raise
        except Exception as e:
            _saas_logger.warning("Credit pre-flight check failed (non-blocking): %s", e)

    # Call appropriate provider
    if provider == "local":
        result = await call_local(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    elif provider == "anthropic":
        result = await call_anthropic(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    elif provider == "openai":
        result = await call_openai(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    elif provider == "xai":
        result = await call_xai(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    elif provider == "perplexity":
        result = await call_perplexity(
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    elif provider in ("google", "openrouter", "groq", "cerebras", "deepseek", "mistral"):
        result = await call_generic_provider(
            provider=provider,
            model=model,
            messages=request.messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
    else:
        raise HTTPException(status_code=500, detail=f"Unknown provider: {provider}")

    # Calculate metrics
    response_time_ms = int((time.time() - start_time) * 1000)
    cost_usd = calculate_cost(model, result["usage"])

    # ── Post-call: deduct credits atomically (paid models only) ──
    if user_id != "anonymous" and cost_usd > 0:
        try:
            from apps.backend.database.connection import get_db_session
            from apps.backend.services.credit_service import CreditService

            async with get_db_session() as deduct_session:
                credit_svc = CreditService(deduct_session)
                await credit_svc.deduct_credits(
                    user_id=user_id,
                    model_id=model,
                    input_tokens=result["usage"]["input_tokens"],
                    output_tokens=result["usage"]["output_tokens"],
                    request_id=f"chatcmpl-{int(time.time())}",
                )
                await deduct_session.commit()
        except ValueError as e:
            # Soft overage: response already generated, log the overage
            _saas_logger.warning("Credit overage for user %s: %s", user_id, e)
        except Exception as e:
            _saas_logger.warning("Credit deduction failed (non-blocking): %s", e)

    # Track usage analytics (separate from credit deduction)
    await track_usage(
        user_id=user_id,
        endpoint="/v1/chat",
        method="POST",
        provider=provider,
        model=model,
        tokens_input=result["usage"]["input_tokens"],
        tokens_output=result["usage"]["output_tokens"],
        cost_usd=cost_usd,
        response_time_ms=response_time_ms,
        status_code=200,
    )

    # Build response
    response_id = f"chatcmpl-{int(time.time())}"

    return ChatResponse(
        id=response_id,
        model=model,
        provider=provider,
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["content"]},
                "finish_reason": result["finish_reason"],
            }
        ],
        usage=result["usage"],
        cost_usd=cost_usd,
        response_time_ms=response_time_ms,
        optimize_mode=request.optimize,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


async def get_available_models(tier: str) -> list[dict[str, Any]]:
    """
    Get list of available models for a tier

    Args:
        tier: User tier

    Returns:
        List of model info dicts
    """
    allowed_models = TIER_MODELS.get(tier)

    # If None (enterprise/workflow), all models available
    if allowed_models is None:
        allowed_models = list(MODEL_PRICING.keys())

    models = []
    for model in allowed_models:
        pricing = MODEL_PRICING.get(model)
        models.append(
            {
                "id": model,
                "provider": (
                    "anthropic"
                    if "claude" in model
                    else ("openai" if "gpt" in model else "xai" if "grok" in model else "perplexity")
                ),
                "pricing": pricing,
                "scores": {
                    "cost": MODEL_SCORES["cost"].get(model, 50),
                    "speed": MODEL_SCORES["speed"].get(model, 50),
                    "quality": MODEL_SCORES["quality"].get(model, 50),
                },
            }
        )

    return models


async def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate cost for a completion

    Args:
        model: Model name
        input_tokens: Estimated input tokens
        output_tokens: Estimated output tokens

    Returns:
        Estimated cost in USD
    """
    return calculate_cost(model, {"input_tokens": input_tokens, "output_tokens": output_tokens})
