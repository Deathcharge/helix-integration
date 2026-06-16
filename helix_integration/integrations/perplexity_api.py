"""
Perplexity API Integration
Provides access to multiple LLMs through Perplexity's unified API
"""

import asyncio
import os
from typing import Any, ClassVar

import aiohttp
from loguru import logger

from apps.backend.core.exceptions import IntegrationError


class PerplexityAPI:
    """
    Perplexity API client for multi-LLM access and search-augmented generation.

    Perplexity provides access to:
    - llama-3.1-sonar-small-128k-online (fast, search-enabled)
    - llama-3.1-sonar-large-128k-online (powerful, search-enabled)
    - llama-3.1-sonar-huge-128k-online (most capable, search-enabled)
    - llama-3.1-8b-instruct (fast, offline)
    - llama-3.1-70b-instruct (powerful, offline)
    """

    BASE_URL = "https://api.perplexity.ai"

    # Available models
    MODELS: ClassVar[dict] = {
        "sonar-small": "llama-3.1-sonar-small-128k-online",
        "sonar-large": "llama-3.1-sonar-large-128k-online",
        "sonar-huge": "llama-3.1-sonar-huge-128k-online",
        "llama-8b": "llama-3.1-8b-instruct",
        "llama-70b": "llama-3.1-70b-instruct",
    }

    def __init__(self, api_key: str | None = None):
        """
        Initialize Perplexity API client.

        Args:
            api_key: Perplexity API key (defaults to PERPLEXITY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("PERPLEXITY_API_KEY")

        if not self.api_key:
            logger.warning("⚠️  PERPLEXITY_API_KEY not set - Perplexity features disabled")
        else:
            logger.info("✅ Perplexity API initialized")

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        model: str = "sonar-large",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        search: bool = True,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        Generate a chat completion using the Perplexity API.

        Parameters:
            messages (List[Dict[str, str]]): Conversation messages in OpenAI-compatible format (each message should include at least a `role` and `content`).
            model (str): Model alias or full model identifier; common aliases are mapped to Perplexity model names.
            temperature (float): Sampling temperature; higher values produce more diverse outputs.
            max_tokens (int): Maximum number of tokens to generate for the completion.
            search (bool): If true and the model supports it (e.g., "sonar" models), enable web search augmentation and request citations.
            stream (bool): If true, request a streaming response when supported by the API.

        Returns:
            Dict[str, Any]: The parsed JSON response from the Perplexity API, including choices and usage information.

        Raises:
            ValueError: If the Perplexity API key is not configured.
            Exception: On HTTP errors, API errors, or when the request times out.
        """
        if not self.api_key:
            raise ValueError("PERPLEXITY_API_KEY not configured")

        # Resolve model alias to full name
        model_name = self.MODELS.get(model, model)

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        # Add search parameters for sonar models
        if search and "sonar" in model_name:
            payload["search_domain_filter"] = None  # Search all domains
            payload["return_citations"] = True
            payload["return_images"] = False

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(
                    f"{self.BASE_URL}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=60),
                ) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error("Perplexity API error %s: %s", resp.status, error_text)
                        raise IntegrationError(f"Perplexity API error: {resp.status}")

                    result = await resp.json()

                    # Log usage
                    usage = result.get("usage", {})
                    logger.info(
                        f"Perplexity {model_name}: "
                        f"{usage.get('total_tokens', 0)} tokens "
                        f"(prompt: {usage.get('prompt_tokens', 0)}, "
                        f"completion: {usage.get('completion_tokens', 0)})"
                    )

                    return result

            except TimeoutError:
                logger.error("Perplexity API request timeout")
                raise IntegrationError("Perplexity API timeout") from None
            except Exception as e:
                logger.error("Perplexity API error: %s", str(e))
                raise

    async def search_query(self, query: str, model: str = "sonar-large", max_tokens: int = 1024) -> dict[str, Any]:
        """
        Perform a search-augmented query.

        Args:
            query: Search query/question
            model: Sonar model to use (with web search)
            max_tokens: Maximum response tokens

        Returns:
            Search-augmented response with citations
        """
        messages = [{"role": "user", "content": query}]

        return await self.chat_completion(messages=messages, model=model, search=True, max_tokens=max_tokens)

    async def multi_llm_comparison(self, prompt: str, models: list[str] | None = None) -> dict[str, dict[str, Any]]:
        """
        Get responses from multiple LLMs for comparison.

        Args:
            prompt: The prompt to send to all models
            models: List of models to query (defaults to all available)

        Returns:
            Dictionary mapping model names to their responses
        """
        if models is None:
            models = ["sonar-small", "sonar-large", "llama-8b", "llama-70b"]

        messages = [{"role": "user", "content": prompt}]

        tasks = []
        for model in models:
            tasks.append(self.chat_completion(messages, model=model, search=False))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        output: dict[str, dict[str, Any]] = {}
        for model, result in zip(models, results, strict=False):
            if isinstance(result, BaseException):
                output[model] = {"error": str(result)}
            else:
                output[model] = {
                    "content": result["choices"][0]["message"]["content"],
                    "model": result["model"],
                    "usage": result.get("usage", {}),
                }

        return output

    async def validate_api_key(self) -> bool:
        """
        Validate Perplexity API key by making a test request.

        Returns:
            True if API key is valid, False otherwise
        """
        if not self.api_key:
            return False

        try:
            result = await self.chat_completion(
                messages=[{"role": "user", "content": "Hello"}],
                model="llama-8b",
                max_tokens=10,
                search=False,
            )
            return "choices" in result
        except Exception as e:
            logger.error("Perplexity API key validation failed: %s", str(e))
            return False


# Global instance
_perplexity_client: PerplexityAPI | None = None


def get_perplexity() -> PerplexityAPI:
    """Get the global Perplexity API client instance."""
    global _perplexity_client

    if _perplexity_client is None:
        _perplexity_client = PerplexityAPI()

    return _perplexity_client


def set_perplexity(client: PerplexityAPI):
    """Set the global Perplexity API client instance."""
    global _perplexity_client
    _perplexity_client = client


# Example usage
if __name__ == "__main__":

    async def main():
        client = PerplexityAPI()

        # Search query
        result = await client.search_query("What are the latest developments in AI coordination research?")

        logger.info("Response:", result["choices"][0]["message"]["content"])

        if "citations" in result:
            logger.info("\nCitations:")
            for citation in result.get("citations", []):
                logger.info("- %s", citation)

        # Multi-LLM comparison
        comparison = await client.multi_llm_comparison("Explain system coordination in one sentence.")

        logger.info("\n\nMulti-LLM Comparison:")
        for model, response in comparison.items():
            if "error" in response:
                logger.error("%s: ERROR - %s", model, response["error"])
            else:
                logger.info("%s: %s", model, response["content"])

    asyncio.run(main())
