"""
MCP Client Integration for Helix Backend
Connects to deployed MCP server and exposes 44 tools via REST API
"""

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SSRF Protection — reused from execution_engine.py / generic_http_connector.py
# ---------------------------------------------------------------------------

_BLOCKED_HOST_PATTERNS = [
    re.compile(r"^localhost$", re.IGNORECASE),
    re.compile(r"^127\.", re.IGNORECASE),
    re.compile(r"^0\.0\.0\.0$"),
    re.compile(r"^::1$"),
    re.compile(r"^169\.254\.", re.IGNORECASE),  # cloud metadata
    re.compile(r"^10\.", re.IGNORECASE),  # private RFC1918
    re.compile(r"^172\.(1[6-9]|2\d|3[01])\.", re.IGNORECASE),  # private
    re.compile(r"^192\.168\.", re.IGNORECASE),  # private RFC1918
    re.compile(r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.", re.IGNORECASE),  # CGNAT
    re.compile(r"metadata\.google\.internal", re.IGNORECASE),
    re.compile(r"metadata\.internal", re.IGNORECASE),
]


def _is_safe_mcp_url(url: str) -> bool:
    """Validate MCP server URL to prevent SSRF.

    Blocks:
      - localhost / loopback
      - Private IP ranges (RFC1918, CGNAT)
      - Cloud metadata endpoints (GCP, AWS)
      - Non-http(s) schemes

    Returns True if URL is safe to call, False otherwise.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Only allow http/https schemes
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname or ""

    # Check against blocked patterns
    for pattern in _BLOCKED_HOST_PATTERNS:
        if pattern.search(hostname):
            logger.warning("MCP client SSRF protection: blocked URL %s (matched %s)", url, pattern.pattern)
            return False

    # DNS resolution check — block if resolves to private IP
    try:
        import socket

        for info in socket.getaddrinfo(hostname, parsed.port or 443):
            addr = info[4][0]
            # Check if resolved IP is private
            parts = addr.split(".")
            if len(parts) == 4:
                octets = [int(p) for p in parts]
                if (
                    octets[0] == 10
                    or (octets[0] == 172 and 16 <= octets[1] <= 31)
                    or (octets[0] == 192 and octets[1] == 168)
                    or (octets[0] == 127)
                    or (octets[0] == 0)
                    or (octets[0] == 169 and octets[1] == 254)
                ):
                    logger.warning("MCP client SSRF protection: %s resolved to private IP %s", hostname, addr)
                    return False
    except (socket.gaierror, ValueError):
        pass  # Resolution failed — let it fail at request time

    return True


class HelixMCPClient:
    """Client to interact with deployed Helix MCP server"""

    def __init__(self, mcp_url: str | None = None):
        """
        Initialize MCP client

        Args:
            mcp_url: MCP server URL (defaults to MCP_SERVER_URL env var)
        """
        raw_url = mcp_url or os.getenv("MCP_SERVER_URL", "http://localhost:3000")

        # P1-7b: SSRF protection — validate MCP server URL before storing
        if not _is_safe_mcp_url(raw_url):
            raise HTTPException(
                status_code=400,
                detail=f"MCP server URL '{raw_url}' is not allowed (SSRF protection: private/internal IPs blocked)",
            )

        self.mcp_url = raw_url.rstrip("/")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.tools_cache: list[dict[str, Any]] | None = None

    async def health_check(self) -> dict[str, Any]:
        """
        Check if MCP server is reachable

        Returns:
            Health status dictionary
        """
        try:
            response = await self.client.get(f"{self.mcp_url}/health")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"status": "unhealthy", "error": type(e).__name__}

    async def list_tools(self, refresh: bool = False) -> list[dict[str, Any]]:
        """
        List all 44 MCP tools

        Args:
            refresh: Force refresh cache

        Returns:
            List of tool definitions
        """
        if self.tools_cache and not refresh:
            return self.tools_cache

        try:
            response = await self.client.get(f"{self.mcp_url}/tools")
            response.raise_for_status()
            self.tools_cache = response.json()
            return self.tools_cache
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="MCP server unavailable") from None

    async def call_tool(self, tool_name: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Call any MCP tool by name

        Args:
            tool_name: Name of the tool (e.g., 'helix_get_ucf_metrics')
            params: Tool parameters

        Returns:
            Tool execution result
        """
        try:
            response = await self.client.post(f"{self.mcp_url}/tools/{tool_name}", json=params or {})
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning("MCP tool %s error: %s", tool_name, e.response.text[:500])
            raise HTTPException(
                status_code=502,
                detail="MCP tool call failed",
            ) from e
        except httpx.HTTPError:
            raise HTTPException(status_code=503, detail="MCP server error") from None

    # ========================================================================
    # UCF METRICS TOOLS (8 tools)
    # ========================================================================

    async def get_ucf_metrics(self) -> dict[str, Any]:
        """Get all UCF coordination metrics"""
        return await self.call_tool("helix_get_ucf_metrics")

    async def get_harmony_score(self) -> float:
        """Get system harmony score (0-100)"""
        result = await self.call_tool("helix_get_harmony_score")
        return result.get("harmony", 0)

    async def get_performance_score(self) -> str:
        """Get overall coordination state"""
        result = await self.call_tool("helix_get_performance_score")
        return result.get("level", "unknown")

    # ========================================================================
    # AGENT CONTROL TOOLS (4 tools)
    # ========================================================================

    async def list_agents(self) -> list[dict[str, Any]]:
        """List all 14+ AI agents and their status"""
        result = await self.call_tool("helix_list_agents")
        return result.get("agents", [])

    async def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Get specific agent state"""
        return await self.call_tool("helix_get_agent_status", {"agent_id": agent_id})

    async def activate_agent(self, agent_id: str) -> dict[str, Any]:
        """Wake up an agent"""
        return await self.call_tool("helix_activate_agent", {"agent_id": agent_id})

    # ========================================================================
    # RAILWAY TOOLS (2 tools)
    # ========================================================================

    async def get_railway_status(self) -> dict[str, Any]:
        """Get all Railway services status"""
        return await self.call_tool("helix_get_railway_status")

    # ========================================================================
    # MEMORY VAULT TOOLS (3 tools)
    # ========================================================================

    async def store_memory(self, key: str, value: Any) -> dict[str, Any]:
        """Store persistent memory"""
        return await self.call_tool("helix_store_memory", {"key": key, "value": value})

    async def retrieve_memory(self, key: str) -> dict[str, Any]:
        """Retrieve persistent memory"""
        return await self.call_tool("helix_retrieve_memory", {"key": key})

    async def list_memories(self) -> list[str]:
        """List all stored memory keys"""
        result = await self.call_tool("helix_list_memories")
        return result.get("keys", [])

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Global singleton instance
_mcp_client: HelixMCPClient | None = None


def get_mcp_client() -> HelixMCPClient:
    """Get global MCP client instance"""
    global _mcp_client
    if _mcp_client is None:
        _mcp_client = HelixMCPClient()
    return _mcp_client


async def close_mcp_client():
    """Close global MCP client"""
    global _mcp_client
    if _mcp_client:
        await _mcp_client.close()
        _mcp_client = None
