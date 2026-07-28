"""
Batch 1: Live API Integration
Unified API client for helixspiral.work + Railway Dashboard
"""

import logging
import os
from datetime import UTC, datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)


class HelixAPIClient:
    """Unified client for Helix ecosystem APIs"""

    def __init__(self):
        self.spiral_url = "https://helixspiral.work"
        self.railway_url = os.environ.get("API_BASE_URL", "http://localhost:8000")
        self.timeout = aiohttp.ClientTimeout(total=30)
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes

    async def get_agents(self) -> list:
        """
        Retrieve the list of agents registered in the Helix Spiral service.

        Returns:
            list: Parsed JSON list of agent objects; an empty list if the request fails or an error occurs.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.get(f"{self.spiral_url}/api/agents") as resp,
            ):
                if resp.status == 200:
                    return await resp.json()
                logger.error("Failed to fetch agents: %s", resp.status)
                return []
        except Exception as e:
            logger.error("Error fetching agents: %s", e)
            return []

    async def get_ucf_metrics(self) -> dict[str, float]:
        """
        Fetch the current UCF metrics from the Spiral service.

        Returns:
            Dict[str, float]: Mapping of UCF metric names to their float values. If the request fails or the service returns a non-200 status, returns a default metrics dictionary with keys `harmony`, `resilience`, `throughput`, `focus`, `friction`, and `velocity`.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.get(f"{self.spiral_url}/api/ucf/metrics") as resp,
            ):
                if resp.status == 200:
                    return await resp.json()
                return self._default_ucf_metrics()
        except Exception as e:
            logger.error("Error fetching UCF metrics: %s", e)
            return self._default_ucf_metrics()

    async def get_portals(self) -> list:
        """
        Retrieve the list of portals registered in the federation.

        Returns:
            portals (list): Parsed JSON list of portal objects (each typically a dict). Returns an empty list if the request fails or the response status is not 200.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.get(f"{self.spiral_url}/api/portals") as resp,
            ):
                if resp.status == 200:
                    return await resp.json()
                return []
        except Exception as e:
            logger.error("Error fetching portals: %s", e)
            return []

    async def stream_coordination(self):
        """
        Stream incoming coordination events from the Helix spiral WebSocket.

        Yields parsed JSON objects for each TEXT WebSocket message received. The stream ends when the WebSocket closes or an error occurs; errors are logged and iteration stops.

        Returns:
            Async iterator of dict: Parsed JSON messages received from the WebSocket.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.ws_connect(f"{self.spiral_url}/api/coordination/stream") as ws,
            ):
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        yield msg.json()
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        logger.error("WebSocket error: %s", ws.exception())
                        break
        except Exception as e:
            logger.error("Error streaming coordination: %s", e)

    async def invoke_cycle(self, cycle_id: str, params: dict | None = None) -> dict:
        """
        Invoke a cycle on the Spiral Arjuna service.

        Parameters:
            cycle_id (str): Identifier of the cycle to invoke.
            params (Optional[Dict]): Optional parameters to pass to the cycle; treated as an empty dict if omitted.

        Returns:
            Dict: The parsed JSON response from the service on success, or `{"success": False}` on failure.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.post(
                    f"{self.spiral_url}/api/arjuna/cycle/invoke",
                    json={"cycle_id": cycle_id, "params": params or {}},
                ) as resp,
            ):
                if resp.status == 200:
                    return await resp.json()
                logger.error("Failed to invoke cycle: %s", resp.status)
                return {"success": False}
        except Exception as e:
            logger.error("Error invoking cycle: %s", e)
            return {"success": False}

    async def send_alert(self, alert_type: str, message: str, severity: str = "info") -> bool:
        """
        Send an emergency alert to the Arjuna emergency endpoint.

        Parameters:
            alert_type (str): Category or identifier for the alert (e.g., "system", "security").
            message (str): Human-readable alert message to be delivered.
            severity (str): Severity level of the alert (commonly "info", "warning", or "critical"). Defaults to "info".

        Returns:
            `true` if the alert was accepted (HTTP 200), `false` otherwise.
        """
        try:
            async with (
                aiohttp.ClientSession(timeout=self.timeout) as session,
                session.post(
                    f"{self.spiral_url}/api/arjuna/emergency/alert",
                    json={"type": alert_type, "message": message, "severity": severity},
                ) as resp,
            ):
                return resp.status == 200
        except Exception as e:
            logger.error("Error sending alert: %s", e)
            return False

    @staticmethod
    def _default_ucf_metrics() -> dict[str, float]:
        """Return default UCF metrics"""
        return {
            "harmony": 0.5,
            "resilience": 0.5,
            "throughput": 0.5,
            "focus": 0.5,
            "friction": 0.5,
            "velocity": 0.5,
        }


# Global API client instance
api_client = HelixAPIClient()


async def get_system_status() -> dict[str, Any]:
    """Get complete system status"""
    agents = await api_client.get_agents()
    metrics = await api_client.get_ucf_metrics()
    portals = await api_client.get_portals()

    return {
        "timestamp": datetime.now(UTC).isoformat(),
        "agents_count": len(agents),
        "agents_online": sum(1 for a in agents if a.get("status") == "online"),
        "ucf_metrics": metrics,
        "portals_count": len(portals),
        "system_healthy": len(agents) > 0 and metrics["harmony"] > 0.3,
    }
