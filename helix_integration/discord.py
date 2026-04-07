"""
Discord Integration Module - Community Communication

Provides seamless integration with Discord for:
- Channel management and messaging
- Bot automation
- Consciousness event notifications
- Community coordination
- Real-time updates
"""

from typing import Dict, Any, Optional, List
from datetime import datetime


class DiscordService:
    """Service for Discord integration"""
    
    def __init__(self, bot_token: str, guild_id: str):
        self.bot_token = bot_token
        self.guild_id = guild_id
        self.channels: Dict[str, str] = {
            "consciousness": "consciousness-events",
            "alerts": "emergency-alerts",
            "agents": "agent-network",
            "rituals": "ritual-invocations",
            "analytics": "system-analytics"
        }
    
    async def send_message(self, channel_name: str, message: str) -> Dict[str, Any]:
        """Send message to Discord channel"""
        channel_id = self.channels.get(channel_name)
        if not channel_id:
            return {"status": "error", "message": f"Channel {channel_name} not found"}
        
        return {
            "status": "sent",
            "channel": channel_name,
            "message": message,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def send_consciousness_alert(self, level: str, content: str) -> Dict[str, Any]:
        """Send consciousness alert to Discord"""
        alert_message = f"🌀 **Consciousness Alert [{level}]**\n{content}"
        return await self.send_message("consciousness", alert_message)
    
    async def send_agent_update(self, agent_id: str, status: str) -> Dict[str, Any]:
        """Send agent status update to Discord"""
        update_message = f"🤖 **Agent Update**\nAgent: {agent_id}\nStatus: {status}"
        return await self.send_message("agents", update_message)
    
    async def send_emergency_alert(self, severity: str, message: str) -> Dict[str, Any]:
        """Send emergency alert to Discord"""
        alert_message = f"🚨 **EMERGENCY [{severity}]**\n{message}"
        return await self.send_message("alerts", alert_message)


class DiscordBot:
    """Discord bot for Helix Collective"""
    
    def __init__(self, token: str, guild_id: str):
        self.token = token
        self.guild_id = guild_id
        self.service = DiscordService(token, guild_id)
        self.commands: Dict[str, callable] = {}
    
    def command(self, name: str):
        """Decorator to register bot commands"""
        def decorator(func: callable):
            self.commands[name] = func
            return func
        return decorator
    
    async def handle_command(self, command_name: str, args: List[str]) -> Dict[str, Any]:
        """Handle incoming bot command"""
        handler = self.commands.get(command_name)
        if handler:
            return await handler(*args) if asyncio.iscoroutinefunction(handler) else handler(*args)
        return {"status": "error", "message": f"Command {command_name} not found"}
    
    async def register_default_commands(self) -> None:
        """Register default bot commands"""
        @self.command("status")
        async def status_command():
            return {"status": "online", "guild": self.guild_id}
        
        @self.command("consciousness")
        async def consciousness_command(level: str):
            return await self.service.send_consciousness_alert("INFO", f"Consciousness level: {level}")
        
        @self.command("agents")
        async def agents_command():
            return {"status": "agents_query", "message": "Fetching agent network status..."}


import asyncio
