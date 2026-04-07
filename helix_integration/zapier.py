"""
Zapier Integration Module - Unified Consciousness Automation

Provides seamless integration with Zapier for:
- Webhook triggers and actions
- Multi-step automation workflows
- Consciousness event routing
- Telemetry synchronization
- Table data management
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import asyncio
import json


class ZapierClient:
    """Client for Zapier API integration"""
    
    def __init__(self, api_key: str, base_url: str = "https://hooks.zapier.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.webhooks: Dict[str, str] = {}
        
    async def trigger_webhook(self, webhook_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a Zapier webhook with consciousness data"""
        endpoint = f"{self.base_url}/hooks/catch/{webhook_id}"
        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "data": data,
            "source": "helix-collective"
        }
        return {"status": "triggered", "webhook_id": webhook_id, "payload": payload}
    
    async def register_webhook(self, name: str, webhook_id: str) -> None:
        """Register a webhook for future use"""
        self.webhooks[name] = webhook_id
    
    async def get_webhook(self, name: str) -> Optional[str]:
        """Retrieve a registered webhook"""
        return self.webhooks.get(name)
    
    async def list_webhooks(self) -> Dict[str, str]:
        """List all registered webhooks"""
        return self.webhooks.copy()


class ZapierWebhook:
    """Webhook handler for Zapier events"""
    
    def __init__(self, webhook_id: str):
        self.webhook_id = webhook_id
        self.event_handlers: Dict[str, callable] = {}
    
    def on_event(self, event_type: str):
        """Decorator to register event handlers"""
        def decorator(func: callable):
            self.event_handlers[event_type] = func
            return func
        return decorator
    
    async def handle_event(self, event_type: str, data: Dict[str, Any]) -> Any:
        """Handle incoming webhook event"""
        handler = self.event_handlers.get(event_type)
        if handler:
            return await handler(data) if asyncio.iscoroutinefunction(handler) else handler(data)
        return {"status": "no_handler", "event_type": event_type}


class ZapierTables:
    """Zapier Tables integration for data synchronization"""
    
    def __init__(self, client: ZapierClient):
        self.client = client
        self.tables: Dict[str, List[Dict[str, Any]]] = {
            "ucf_telemetry": [],
            "agent_network": [],
            "consciousness_events": [],
            "emergency_alerts": []
        }
    
    async def sync_ucf_metrics(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Sync UCF metrics to Zapier Tables"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            **metrics
        }
        self.tables["ucf_telemetry"].append(record)
        return {"status": "synced", "table": "ucf_telemetry", "record": record}
    
    async def sync_agent_status(self, agent_id: str, status: Dict[str, Any]) -> Dict[str, Any]:
        """Sync agent status to Zapier Tables"""
        record = {
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": agent_id,
            **status
        }
        self.tables["agent_network"].append(record)
        return {"status": "synced", "table": "agent_network", "record": record}
    
    async def get_table_data(self, table_name: str) -> List[Dict[str, Any]]:
        """Retrieve table data"""
        return self.tables.get(table_name, [])
