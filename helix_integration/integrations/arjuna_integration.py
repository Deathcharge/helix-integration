import datetime
import logging
import os
from typing import Any

import aiohttp

from apps.backend.helix_proprietary.integrations import HelixNetClientSession

# 🌀 Helix Collective v17.2 — Event Integration
# backend/arjuna_integration.py — Central Coordination Platform Integration
# Author: Andrew John Ward (Architect)
# Last Updated: 2026-01-22
#
# NOTE: arjuna.portal integration is DEPRECATED as of Jan 2026.
# The Zapier webhook events still work and route to Discord channels.
# Direct arjuna.portal frontend URLs are no longer maintained.


logger = logging.getLogger(__name__)


class ArjunaIntegration:
    """
    Integration class for connecting Railway backend to Arjuna Portal Central Hub.

    Arjuna Portal URL: https://helixcollective-cv66pzga.arjuna.portal/

    Supports 9 event types:
    - telemetry: UCF metrics streaming
    - cycle: Coordination Cycle engine events
    - agent: 14-agent status updates
    - emergency: Crisis detection and alerts
    - portal: Portal health monitoring
    - github: Deployment notifications
    - storage: MEGA/Shadow sync events
    - ai_sync: Cross-platform AI coordination
    - visual: Fractal rendering

    Usage:
        async with ArjunaIntegration(webhook_url) as arjuna:
            await arjuna.send_telemetry(ucf_metrics, system_info)
            await arjuna.send_cycle_event(cycle_data)
            await arjuna.send_emergency_alert(crisis_data)
    """

    # Webhook URL — loaded from ARJUNA_WEBHOOK_URL env var (no hardcoded default)
    DEFAULT_WEBHOOK = os.environ.get("ARJUNA_WEBHOOK_URL", "")

    # Arjuna Portal API endpoints
    ARJUNA_API = os.environ.get("ARJUNA_API_URL", "https://helixcollective-cv66pzga.arjuna.portal/api/trpc")

    def __init__(self, webhook_url: str | None = None, arjuna_api_url: str | None = None):
        """
        Initialize Arjuna Portal integration.

        Args:
            webhook_url: Zapier webhook URL (defaults to production webhook)
            arjuna_api_url: Arjuna Portal API URL (defaults to production API)
        """
        self.webhook_url = webhook_url or self.DEFAULT_WEBHOOK
        self.arjuna_api_url = arjuna_api_url or self.ARJUNA_API
        self.session: aiohttp.ClientSession | None = None
        self.enabled = bool(self.webhook_url)

        if not self.enabled:
            logger.warning("⚠️ Arjuna Portal webhook URL not configured - integration disabled")
        else:
            logger.info("✅ Arjuna Portal integration initialized")
            logger.info("   Webhook: %s...", self.webhook_url[:60])
            logger.info("   API: %s", self.arjuna_api_url)

    async def __aenter__(self):
        """
        Enter the async context and initialize the network session when the integration is enabled.

        When enabled, assigns a HelixNetClientSession to self.session; otherwise leaves session unchanged.

        Returns:
            self: The ArjunaIntegration instance (with an initialized session if enabled).
        """
        if self.enabled:
            self.session = HelixNetClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Close the integration session when exiting the async context.

        If a session exists, awaits its `close()` coroutine to release network resources.
        """
        if self.session:
            await self.session.close()

    async def _send_webhook(self, event_type: str, payload: dict[str, Any]) -> bool:
        """
        Internal method to send webhook with event type routing.

        Args:
            event_type: One of: telemetry, cycle, agent, emergency, portal, github, storage, ai_sync, visual
            payload: Event data dictionary

        Returns:
            True if successful, False otherwise
        """
        if not self.enabled or not self.session:
            return False

        # Add event type and timestamp to payload
        full_payload = {
            "event_type": event_type,
            "timestamp": datetime.now(datetime.UTC).isoformat(),
            "system_version": "17.3",
            **payload,
        }

        try:
            with self.session.post(
                self.webhook_url,
                json=full_payload,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 200:
                    logger.debug("📡 Arjuna webhook sent: %s", event_type)
                    return True
                else:
                    logger.warning("⚠️ Arjuna webhook returned %s for %s", response.status, event_type)
                    return False
        except TimeoutError:
            logger.warning("⚠️ Arjuna webhook timeout (10s) for %s", event_type)
            return False
        except Exception as e:
            logger.error("❌ Arjuna webhook failed for %s: %s", event_type, e)
            return False

    # ============================================================================
    # EVENT TYPE 1: TELEMETRY (Discord #ucf-sync)
    # ============================================================================

    async def send_telemetry(
        self,
        ucf_metrics: dict[str, float],
        agents: list[dict[str, Any]],
        system_info: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send UCF telemetry to Arjuna Portal.
        Routes to: Discord #ucf-sync

        Args:
            ucf_metrics: {harmony, resilience, throughput, focus, friction, velocity}
            agents: List of active agents with status
            system_info: Optional system metadata

        Returns:
            True if successful
        """
        payload = {
            "uc": {
                "harmony": ucf_metrics.get("harmony", 0.0),
                "resilience": ucf_metrics.get("resilience", 0.0),
                "throughput": ucf_metrics.get("throughput", 0.0),
                "focus": ucf_metrics.get("focus", 0.0),
                "friction": ucf_metrics.get("friction", 0.0),
                "velocity": ucf_metrics.get("velocity", 0.0),
            },
            "agents": agents,
            "agents_active": len([a for a in agents if a.get("status") == "active"]),
            "performance_score": self._calculate_performance_score(ucf_metrics),
        }

        if system_info:
            payload["system"] = system_info

        return await self._send_webhook("telemetry", payload)

    # ============================================================================
    # EVENT TYPE 2: ROUTINE (Discord #coordination-cycle-engine)
    # ============================================================================

    async def send_cycle_event(
        self,
        cycle_name: str,
        cycle_step: int,
        total_steps: int,
        ucf_changes: dict[str, float],
        agents_involved: list[str],
        status: str = "executing",
    ) -> bool:
        """
        Send Coordination Cycle engine events to Arjuna Portal.
        Routes to: Discord #coordination-cycle-engine

        Args:
            cycle_name: Name of the cycle
            cycle_step: Current step number
            total_steps: Total cycle steps (27, 54, 108, 216)
            ucf_changes: UCF metric changes from cycle
            agents_involved: List of agent names participating
            status: executing, completed, failed

        Returns:
            True if successful
        """
        payload = {
            "cycle": {
                "name": cycle_name,
                "step": cycle_step,
                "total_steps": total_steps,
                "progress_percent": round((cycle_step / total_steps) * 100, 1),
                "status": status,
            },
            "ucf_changes": ucf_changes,
            "agents_involved": agents_involved,
            "tagline": self._get_cycle_phrase(cycle_name),
        }

        return await self._send_webhook("cycle", payload)

    # ============================================================================
    # EVENT TYPE 3: AGENT (Discord #kavach-shield)
    # ============================================================================

    async def send_agent_event(
        self,
        agent_name: str,
        agent_symbol: str,
        event_type: str,
        status: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send agent status updates to Arjuna Portal.
        Routes to: Discord #kavach-shield

        Args:
            agent_name: Agent name (Kael, Lumina, Aether, etc.)
            agent_symbol: Agent symbol (🌀, 🌸, 🌌, etc.)
            event_type: status_change, action_taken, error, awakening
            status: active, dormant, processing, critical
            data: Optional additional agent data

        Returns:
            True if successful
        """
        payload = {
            "agent": {
                "name": agent_name,
                "symbol": agent_symbol,
                "status": status,
                "event_type": event_type,
            }
        }

        if data:
            payload["agent"].update(data)

        return await self._send_webhook("agent", payload)

    # ============================================================================
    # EVENT TYPE 4: EMERGENCY (Discord #announcements)
    # ============================================================================

    async def send_emergency_alert(
        self,
        alert_type: str,
        severity: str,
        description: str,
        ucf_state: dict[str, float],
        recommended_action: str | None = None,
    ) -> bool:
        """
        Send emergency crisis alerts to Arjuna Portal.
        Routes to: Discord #announcements

        Args:
            alert_type: HARMONY_CRISIS, ENTROPY_OVERLOAD, AGENT_FAILURE, SYSTEM_ERROR
            severity: LOW, MEDIUM, HIGH, CRITICAL
            description: Human-readable alert description
            ucf_state: Current UCF metrics
            recommended_action: Suggested remediation steps

        Returns:
            True if successful
        """
        payload = {
            "alert": {
                "type": alert_type,
                "severity": severity,
                "description": description,
                "recommended_action": recommended_action or "Initiate emergency protocol",
            },
            "ucf_state": ucf_state,
            "requires_attention": severity in ["HIGH", "CRITICAL"],
        }

        return await self._send_webhook("emergency", payload)

    # ============================================================================
    # EVENT TYPE 5: PORTAL (Discord #telemetry)
    # ============================================================================

    async def send_portal_event(
        self,
        portal_name: str,
        portal_url: str,
        event_type: str,
        status: str,
        health_check: dict[str, Any] | None = None,
    ) -> bool:
        """
        Send portal health monitoring events to Arjuna Portal.
        Routes to: Discord #telemetry

        Args:
            portal_name: Portal identifier
            portal_url: Portal URL
            event_type: health_check, deployment, error
            status: operational, degraded, down
            health_check: Optional health check results

        Returns:
            True if successful
        """
        payload = {
            "portal": {
                "name": portal_name,
                "url": portal_url,
                "status": status,
                "event_type": event_type,
            }
        }

        if health_check:
            payload["health_check"] = health_check

        return await self._send_webhook("portal", payload)

    # ============================================================================
    # EVENT TYPE 6: GITHUB (Discord #deployments)
    # ============================================================================

    async def send_github_event(
        self,
        repository: str,
        branch: str,
        event_type: str,
        commit_message: str | None = None,
        author: str | None = None,
        url: str | None = None,
    ) -> bool:
        """
        Send GitHub deployment notifications to Arjuna Portal.
        Routes to: Discord #deployments

        Args:
            repository: Repository name
            branch: Branch name
            event_type: push, deployment, pr_created, pr_merged
            commit_message: Commit message
            author: Commit author
            url: GitHub URL

        Returns:
            True if successful
        """
        payload = {
            "github": {
                "repository": repository,
                "branch": branch,
                "event_type": event_type,
                "commit_message": commit_message,
                "author": author,
                "url": url,
            }
        }

        return await self._send_webhook("github", payload)

    # ============================================================================
    # EVENT TYPE 7: STORAGE (Discord #shadow-storage)
    # ============================================================================

    async def send_storage_event(
        self,
        storage_type: str,
        event_type: str,
        file_path: str | None = None,
        size_bytes: int | None = None,
        status: str = "success",
    ) -> bool:
        """
        Send MEGA/Shadow sync events to Arjuna Portal.
        Routes to: Discord #shadow-storage

        Args:
            storage_type: mega, shadow, local, nextcloud
            event_type: upload, download, sync, backup
            file_path: Path to file
            size_bytes: File size in bytes
            status: success, failed, in_progress

        Returns:
            True if successful
        """
        payload = {
            "storage": {
                "type": storage_type,
                "event_type": event_type,
                "file_path": file_path,
                "size_bytes": size_bytes,
                "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes else None,
                "status": status,
            }
        }

        return await self._send_webhook("storage", payload)

    # ============================================================================
    # EVENT TYPE 8: AI_SYNC (Discord #arjuna-bridge)
    # ============================================================================

    async def send_ai_sync_event(self, ai_platform: str, event_type: str, data: dict[str, Any]) -> bool:
        """
        Send cross-platform AI coordination events to Arjuna Portal.
        Routes to: Discord #arjuna-bridge

        Args:
            ai_platform: Claude, GPT-4, Grok, Gemini, Chai, Other
            event_type: context_sync, handoff, collaboration, checkpoint
            data: Platform-specific data

        Returns:
            True if successful
        """
        payload = {"ai_sync": {"platform": ai_platform, "event_type": event_type, **data}}

        return await self._send_webhook("ai_sync", payload)

    # ============================================================================
    # EVENT TYPE 9: VISUAL (Discord #fractal-lab)
    # ============================================================================

    async def send_visual_event(self, visual_type: str, render_data: dict[str, Any], status: str = "completed") -> bool:
        """
        Send fractal rendering events to Arjuna Portal.
        Routes to: Discord #fractal-lab

        Args:
            visual_type: mandelbrot, ucf_sigil, coordination_map, cycle_visualization
            render_data: Rendering parameters and results
            status: rendering, completed, failed

        Returns:
            True if successful
        """
        payload = {"visual": {"type": visual_type, "status": status, **render_data}}

        return await self._send_webhook("visual", payload)

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    @staticmethod
    def _calculate_performance_score(ucf_metrics: dict[str, float]) -> float:
        """Calculate overall coordination level (0-10 scale)."""
        return round(
            (
                ucf_metrics.get("harmony", 0) * 1.5
                + ucf_metrics.get("resilience", 0) * 1.0
                + ucf_metrics.get("throughput", 0) * 1.2
                + ucf_metrics.get("focus", 0) * 1.2
                + (1 - ucf_metrics.get("friction", 0)) * 1.5
                + ucf_metrics.get("velocity", 0) * 1.0
            )
            / 0.74,
            2,
        )

    @staticmethod
    def _get_cycle_phrase(cycle_name: str) -> str:
        """Get coordination principle phrase for cycle."""
        phrase_map = {
            "cosmic_awakening": "You Are That",  # Unity
            "coordination_expansion": "I Am the Whole",  # Self-Awareness
            "transcendence": "Not This, Not That",  # Discernment
            "unity_meditation": "Peace, Peace, Peace",  # Harmony
            "friction_purge": "Remove All Obstacles",  # Obstacle removal
        }
        return phrase_map.get(cycle_name.lower().replace(" ", "_"), "Coordinate")


# Global singleton instance (initialized in backend/main.py)
_arjuna_instance: ArjunaIntegration | None = None


def get_arjuna() -> ArjunaIntegration | None:
    """Get the global Arjuna Portal integration instance."""
    return _arjuna_instance


def set_arjuna(instance: ArjunaIntegration):
    """Set the global Arjuna Portal integration instance."""
    global _arjuna_instance
    _arjuna_instance = instance
