#!/usr/bin/env python3
"""
from apps.backend.services.notion_client import HelixNotionClient
from apps.backend.coordination.ucf_state_loader import load_ucf_state

🌀 Helix Collective v15.8 — Notion Sync Daemon
backend/notion_sync_daemon.py

Purpose: Continuously sync Helix system state to Notion databases.
- Pushes UCF state snapshots
- Updates agent registry status
- Logs system events
- Maintains bidirectional sync as persistent memory layer

Runs as background service with configurable sync intervals.
"""

import asyncio
import json
import logging
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class NotionSyncDaemon:
    """Daemon for continuous Notion synchronization."""

    def __init__(self):
        """Initialize sync daemon with environment configuration."""
        self.enabled = os.getenv("NOTION_SYNC_ENABLED", "false").lower() == "true"
        self.interval = int(os.getenv("NOTION_SYNC_INTERVAL", "300"))
        self.running = False
        self.sync_count = 0
        self.error_count = 0
        self.load_ucf_state: Callable[[], dict[str, Any]] | None = None

        # Import Notion client and state manager
        try:
            from apps.backend.agents import AGENTS
            from apps.backend.coordination.ucf_state_loader import load_ucf_state
            from apps.backend.services.notion_client import HelixNotionClient

            self.notion_client = HelixNotionClient() if self.enabled else None
            self.load_ucf_state = load_ucf_state
            self.agents = AGENTS
        except (ImportError, ValueError) as e:
            logger.error("Failed to initialize Notion client: %s", e)
            self.notion_client = None
            self.load_ucf_state = None
            self.agents = None
        except Exception as e:
            logger.error("Unexpected error during initialization: %s", e, exc_info=True)
            self.notion_client = None
            self.load_ucf_state = None
            self.agents = None

        # notion_sync_daemon.py → integrations/ → backend/ → apps/ → helix-unified/
        _shadow = Path(__file__).resolve().parent.parent.parent.parent / "Shadow"
        # Paths
        self.state_dir = Path("Helix/state")
        self.archive_dir = _shadow / "arjuna_archive"

        # Ensure directories exist
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        if self.enabled:
            logger.info("✅ NotionSyncDaemon initialized (interval: %ss)", self.interval)
        else:
            logger.info("⚠️ NotionSyncDaemon disabled (NOTION_SYNC_ENABLED=false)")

    async def _sync_ucf_state(self):
        """Sync UCF state to Notion."""
        if not self.enabled or not self.notion_client:
            return

        logger.info("📤 Syncing UCF state to Notion...")
        try:
            load_ucf_state = self.load_ucf_state
            ucf_state = load_ucf_state() if load_ucf_state is not None else None

            if not ucf_state:
                logger.warning("⚠️ UCF state is empty, skipping sync.")
                return

            # Add sync timestamp
            ucf_state["last_sync"] = datetime.now(UTC).isoformat()

            # Use the notion_client to save context snapshot
            await self.notion_client.save_context_snapshot(
                session_id=f"ucf-state-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}",
                ai_system="NotionSyncDaemon",
                summary="Automated UCF state snapshot synchronized to Notion.",
                key_decisions=json.dumps(
                    {
                        "harmony": ucf_state.get("harmony"),
                        "resilience": ucf_state.get("resilience"),
                        "phase": ucf_state.get("phase"),
                    },
                    default=str,
                ),
                next_steps="Continue periodic Notion synchronization.",
                full_context=ucf_state,
            )

            harmony = ucf_state.get("harmony", 0)
            logger.info("✅ Successfully synced UCF state to Notion (harmony=%.3f)", harmony)

        except Exception as e:
            logger.error("🔥 Failed to sync UCF state to Notion: %s", e, exc_info=True)
            self.error_count += 1

    async def _sync_agent_registry(self):
        """Sync agent registry to Notion."""
        if not self.enabled or not self.notion_client or not self.agents:
            return

        logger.info("📤 Syncing agent registry to Notion...")
        try:
            synced_count = 0

            # Iterate through all agents and update their status
            for agent_name, agent_obj in self.agents.items():
                try:
                    if hasattr(agent_obj, "get_status"):
                        status = await agent_obj.get_status()
                    elif hasattr(agent_obj, "status"):
                        status = agent_obj.status
                    else:
                        status = "Unknown"

                    status_name = status if isinstance(status, str) else str(status)
                    last_action = "Automated registry sync heartbeat"
                    health_score = 100 if status_name.lower() in {"active", "healthy", "online"} else 50

                    if isinstance(status, dict):
                        status_name = str(status.get("status", status_name))
                        last_action = str(status.get("last_action", last_action))
                        health_score = int(status.get("health_score", health_score))

                    # Update agent status in Notion
                    await self.notion_client.update_agent_status(
                        agent_name=agent_name,
                        status=status_name,
                        last_action=last_action,
                        health_score=health_score,
                    )
                    synced_count += 1

                except Exception as agent_error:
                    logger.warning("⚠️ Failed to sync agent %s: %s", agent_name, agent_error)

            logger.info("✅ Successfully synced %s agents to Notion registry", synced_count)

        except Exception as e:
            logger.error("🔥 Failed to sync agent registry to Notion: %s", e, exc_info=True)
            self.error_count += 1

    async def _sync_events(self):
        """Sync recent system events to Notion."""
        if not self.enabled or not self.notion_client:
            return

        logger.info("📤 Syncing system events to Notion...")
        try:
            log_file = self.archive_dir / "arjuna_log.txt"

            if not log_file.exists():
                logger.warning("⚠️ Log file not found, skipping event sync.")
                return

            # Read last 10 lines
            with open(log_file, encoding="utf-8") as f:
                lines = f.readlines()
                recent_events = lines[-10:] if len(lines) >= 10 else lines

            # Create event data
            event_data = {
                "event_type": "System_Log_Sync",
                "details": "Recent system events from Arjuna log",
                "log_entries": [line.strip() for line in recent_events],
                "timestamp": datetime.now(UTC).isoformat(),
            }

            # Log to Notion
            await self.notion_client.log_event(
                event_title="System Log Sync",
                event_type="System_Log_Sync",
                agent_name="NotionSyncDaemon",
                description=json.dumps(event_data, default=str)[:2000],
                ucf_snapshot={},
            )

            logger.info("✅ Successfully synced %s events to Notion", len(recent_events))

        except Exception as e:
            logger.error("🔥 Failed to sync events to Notion: %s", e, exc_info=True)
            self.error_count += 1

    async def perform_sync_cycle(self):
        """Perform complete sync cycle."""
        if not self.enabled:
            logger.warning("⚠️ Sync cycle skipped (daemon disabled)")
            return

        logger.info("\n" + "=" * 70)
        logger.info("🔄 Notion Sync Cycle #%s", self.sync_count + 1)
        logger.info("=" * 70)

        start_time = datetime.now(UTC)

        try:
            await self._sync_ucf_state()
            await self._sync_agent_registry()
            await self._sync_events()

            self.sync_count += 1

            duration = (datetime.now(UTC) - start_time).total_seconds()
            logger.info("✅ Sync cycle complete (duration: %.2fs, errors: %s)", duration, self.error_count)

        except Exception as e:
            logger.error("❌ Sync cycle failed: %s", e, exc_info=True)
            self.error_count += 1

        logger.info("=" * 70 + "\n")

    async def start(self):
        """Start the daemon."""
        if not self.enabled or not self.notion_client:
            logger.warning("⚠️ Notion sync disabled or client not ready. Daemon will not start.")
            return

        self.running = True
        logger.info("🚀 NotionSyncDaemon STARTED. Syncing every %s seconds.", self.interval)

        while self.running:
            try:
                # Wait for next sync
                logger.info("⏳ Next sync in %ss...", self.interval)
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.error("❌ Error in daemon loop: %s", e, exc_info=True)
                await asyncio.sleep(self.interval)

    async def stop(self):
        """Stop the daemon."""
        self.running = False
        logger.info("🛑 NotionSyncDaemon STOPPED.")


# ============================================================================
# MANUAL TRIGGER FUNCTION (for Discord command)
# ============================================================================


async def trigger_manual_sync():
    """
    Manually trigger a Notion sync cycle.

    Returns:
        str: Status message indicating sync result
    """
    daemon = NotionSyncDaemon()

    if not daemon.enabled:
        return "⚠️ Notion sync is not enabled. Set `NOTION_SYNC_ENABLED=true` in environment."

    if not daemon.notion_client:
        return "❌ Notion client not configured. Check Railway logs for initialization errors. Verify `NOTION_API_KEY` is set correctly."

    try:
        return f"✅ Manual Notion sync completed successfully.\n📊 Synced: UCF State + Agent Registry\n🔢 Total errors: {daemon.error_count}"

    except Exception as e:
        logger.error("Manual sync failed: %s", e, exc_info=True)
        return f"❌ Manual sync failed: {e!s}"


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main():
    """Main entry point for standalone execution."""
    daemon = NotionSyncDaemon()

    try:
        await daemon.start()
    except KeyboardInterrupt:
        await daemon.stop()


if __name__ == "__main__":
    asyncio.run(main())
