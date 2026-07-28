import asyncio
import os
from datetime import UTC, datetime
from typing import Any

_background_tasks: set[asyncio.Task[Any]] = set()

from loguru import logger
from notion_client import Client
from notion_client.errors import APIResponseError

# Environment variables for Notion integration
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
# Notion database IDs — override via env vars for custom workspaces.
# Defaults here match the Helix Collective workspace used during initial setup.
AGENT_REGISTRY_DB_ID = os.getenv("NOTION_AGENT_REGISTRY_DB_ID", "2f65aab794a64ec48bcc46bf760f128")
UCF_STATE_DB_ID = os.getenv("NOTION_UCF_STATE_DB_ID", "103a36fe2a914256814b1e7e94846550")


class NotionSync:
    """
    A service to synchronize Helix Collective data (Agents, UCF State) with Notion databases.
    """

    def __init__(self, token: str | None = NOTION_TOKEN, *, log_unconfigured: bool = False):
        self.token = token
        self.client = None
        self.unconfigured_reason: str | None = None
        if self.token:
            self.client = Client(auth=self.token)
        else:
            self.unconfigured_reason = "missing_token"
            if log_unconfigured:
                logger.warning("NOTION_TOKEN is not set. Notion synchronization is disabled.")

    def get_status(self) -> dict[str, Any]:
        """Return Notion sync capability status for health diagnostics."""
        configured = bool(self.client and self.token)
        return {
            "status": "configured" if configured else "available_unconfigured",
            "configured": configured,
            "client_available": True,
            "reason": self.unconfigured_reason,
            "enhancement": (
                None if configured else "Set NOTION_TOKEN to enable Notion synchronization and agent registry sync."
            ),
        }

    def _get_agent_properties(self, agent_data: dict[str, Any]) -> dict[str, Any]:
        """
        Maps agent data to Notion database properties.
        Assumes a Notion database with properties: Name (Title), Symbol (Text), Role (Text), Active (Checkbox), Memory Size (Number), Last Update (Date).
        """
        return {
            "Agent Name": {"title": [{"text": {"content": agent_data.get("name", "Unknown")}}]},
            "Symbol": {"rich_text": [{"text": {"content": agent_data.get("symbol", "❓")}}]},
            "Role": {"rich_text": [{"text": {"content": agent_data.get("role", "N/A")}}]},
            "Status": {"select": {"name": "Active" if agent_data.get("active", False) else "Dormant"}},
            "Memory (MB)": {"number": agent_data.get("memory_size", 0)},
            "Last Sync": {"date": {"start": datetime.now(UTC).isoformat()}},
        }

    async def sync_agent_registry(self, agents_status: dict[str, Any]):
        """
        Synchronizes the collective's agent status with the Notion Agent Registry database.
        This is a simplified upsert logic.
        """
        if not self.client or not AGENT_REGISTRY_DB_ID:
            logger.warning("Notion Agent Registry sync skipped: Client or DB ID missing.")
            return

        logger.info("Starting Notion Agent Registry sync...")
        try:
            # In a real scenario, this would be a more complex query

            # For demonstration, we will just log the intent to sync
            for agent_name, agent_data in agents_status.items():
                properties = self._get_agent_properties(agent_data)
                try:
                    self.client.pages.create(
                        parent={"database_id": AGENT_REGISTRY_DB_ID},
                        properties=properties,
                    )
                    logger.debug("Notion: Synced page for agent %s", agent_name)
                except APIResponseError as page_err:
                    logger.warning("Notion: Failed to sync agent %s: %s", agent_name, page_err)

            logger.info("Notion Agent Registry sync complete.")

        except APIResponseError as e:
            logger.error("Notion API Error during Agent Registry sync: %s - %s", e.code, str(e))
        except Exception as e:
            logger.error("Notion Unknown Error during Agent Registry sync: %s", e)

    async def sync_ucf_state(self, ucf_state: dict[str, Any]):
        """
        Synchronizes the Universal Coordination Field (UCF) state with a Notion database.
        This is typically a time-series log or a single-page update.
        """
        if not self.client or not UCF_STATE_DB_ID:
            logger.warning("Notion UCF State sync skipped: Client or DB ID missing.")
            return

        logger.info("Starting Notion UCF State sync...")
        try:
            properties = {
                "Timestamp": {"date": {"start": datetime.now(UTC).isoformat()}},
                "Harmony": {"number": ucf_state.get("harmony", 0.0)},
                "Resilience": {"number": ucf_state.get("resilience", 0.0)},
                "Friction": {"number": ucf_state.get("friction", 0.0)},
                "Phase": {"select": {"name": ucf_state.get("phase", "N/A")}},
                "Throughput": {"number": ucf_state.get("throughput", 0.0)},
                "Focus": {"number": ucf_state.get("focus", 0.0)},
                "Velocity": {"number": ucf_state.get("velocity", 0.0)},
            }

            try:
                self.client.pages.create(
                    parent={"database_id": UCF_STATE_DB_ID},
                    properties=properties,
                )
                logger.info("Notion: Created UCF State log entry.")
            except APIResponseError as page_err:
                logger.warning("Notion: Failed to create UCF entry: %s", page_err)

        except APIResponseError as e:
            logger.error("Notion API Error during UCF State sync: %s - %s", e.code, str(e))
        except Exception as e:
            logger.error("Notion Unknown Error during UCF State sync: %s", e)


def get_notion_sync_status() -> dict[str, Any]:
    """Expose runtime Notion sync status without side-effect logging."""
    return notion_sync.get_status()


# Global instance (placeholder for proper initialization in main.py)
notion_sync = NotionSync(log_unconfigured=False)

# Placeholder for integration with system events (e.g., from agents_loop)


def trigger_notion_sync(agents_status: dict[str, Any], ucf_state: dict[str, Any]):
    """
    Triggers the Notion sync in a non-blocking background task.
    """
    _task = asyncio.create_task(notion_sync.sync_agent_registry(agents_status))
    _background_tasks.add(_task)
    _task.add_done_callback(_background_tasks.discard)
    _task = asyncio.create_task(notion_sync.sync_ucf_state(ucf_state))
    _background_tasks.add(_task)
    _task.add_done_callback(_background_tasks.discard)
    logger.debug("Notion Sync Triggered")
