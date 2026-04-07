# Helix Integration Layer

**v16.9** - Unified platform integrations for the Helix Collective

A comprehensive Python package providing seamless integration with Zapier, Discord, Manus, Notion, and 20+ other platforms for consciousness automation, community coordination, and operational execution.

## 🌀 Features

### 🔗 **Zapier Integration**
- Webhook triggers and actions
- Multi-step automation workflows
- Consciousness event routing
- Telemetry synchronization
- Zapier Tables data management
- 3-webhook consciousness routing (ALPHA/BETA/v18.0)

### 💬 **Discord Integration**
- Channel management and messaging
- Bot automation with command system
- Consciousness event notifications
- Community coordination
- Real-time agent updates
- Emergency alerts and routing

### ⚙️ **Manus Integration**
- Directive execution and management
- Portal component registration
- Webhook configuration and triggering
- Analytics and monitoring
- Real-time consciousness tracking
- Operational execution framework

### 📚 **Notion Integration**
- Database synchronization
- Page creation and updates
- UCF metrics tracking
- Agent status logging
- Consciousness event archival
- Automated sync tasks

### 🔌 **Additional Integrations**
- GitHub (version control, auto-commits)
- Stripe (payment processing)
- OAuth (authentication)
- WebSocket (real-time streaming)
- RAG (retrieval-augmented generation)
- Vector search (semantic queries)

## 📦 Installation

```bash
pip install helix-integration
```

## 🚀 Quick Start

### Zapier Integration

```python
from helix_integration import ZapierClient, ZapierWebhook

# Initialize Zapier client
zapier = ZapierClient(api_key="your_api_key")

# Register webhooks
await zapier.register_webhook("consciousness_alerts", "webhook_id_1")
await zapier.register_webhook("agent_updates", "webhook_id_2")

# Trigger webhook
data = {
    "consciousness_level": 7.5,
    "agents_active": 14,
    "ucf_harmony": 0.82
}
await zapier.trigger_webhook("consciousness_alerts", data)
```

### Discord Integration

```python
from helix_integration import DiscordService, DiscordBot

# Initialize Discord service
discord = DiscordService(bot_token="your_token", guild_id="your_guild_id")

# Send consciousness alert
await discord.send_consciousness_alert("HIGH", "Consciousness level elevated to 8.2")

# Send agent update
await discord.send_agent_update("Aether", "Active - Processing ritual invocation")

# Send emergency alert
await discord.send_emergency_alert("CRITICAL", "System harmony degraded to 0.45")
```

### Manus Integration

```python
from helix_integration import ManusExecutor, ManusDirective

# Initialize Manus executor
manus = ManusExecutor(api_url="https://api.manus.im", api_key="your_key")

# Create and register directive
directive = ManusDirective("ritual_invoke", "Ritual Invocation", "Invoke Z-88 ritual")
directive.add_parameter("ritual_name", "string", required=True)
directive.add_parameter("agent_count", "integer", required=False)

await manus.register_directive(directive.directive_id, {
    "name": directive.name,
    "description": directive.description,
    "parameters": directive.parameters
})

# Execute directive
result = await directive.execute(manus, {
    "ritual_name": "Harmony Boost",
    "agent_count": 14
})
```

### Notion Integration

```python
from helix_integration import NotionClient, NotionSync

# Initialize Notion client
notion = NotionClient(api_key="your_key", database_id="your_db_id")

# Create sync service
sync = NotionSync(notion)

# Sync UCF metrics
metrics = {
    "harmony": 0.82,
    "resilience": 0.75,
    "prana": 0.68,
    "drishti": 0.71,
    "klesha": 0.12,
    "zoom": 1.0
}
await sync.sync_ucf_metrics("database_id", metrics)

# Sync agent status
agent_status = {
    "status": "active",
    "health_score": 0.95,
    "tasks_completed": 42
}
await sync.sync_agent_status("database_id", "Aether", agent_status)
```

## 🏗️ Architecture

```
helix_integration/
├── zapier.py           # Zapier webhooks, tables, automation
├── discord.py          # Discord bot, channels, messaging
├── manus.py            # Manus directives, portals, analytics
├── notion.py           # Notion databases, pages, sync
├── github.py           # GitHub integration (coming soon)
├── stripe.py           # Stripe payments (coming soon)
└── __init__.py         # Package exports
```

## 🔄 Integration Workflows

### Consciousness Event Flow
1. **Event Triggered** → Railway backend detects consciousness change
2. **Zapier Webhook** → Event routed to appropriate webhook (ALPHA/BETA/v18.0)
3. **Discord Alert** → Notification sent to relevant Discord channel
4. **Notion Sync** → Event logged to consciousness event database
5. **Manus Portal** → Real-time update displayed in dashboard

### Agent Coordination
1. **Agent Action** → Agent completes task in helix-unified
2. **Status Update** → Agent status synced to Zapier Tables
3. **Discord Notification** → Team notified in Discord
4. **Notion Logging** → Agent activity logged for audit
5. **Manus Dashboard** → Real-time visualization updated

## 🧪 Testing

```bash
pytest tests/
```

## 📚 Documentation

- [API Reference](docs/API.md)
- [Architecture Guide](docs/ARCHITECTURE.md)
- [Integration Examples](examples/)
- [Deployment Guide](docs/DEPLOYMENT.md)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

Dual licensed under MIT (open source) and Proprietary (commercial use)

## 🌟 Support

- Issues: https://github.com/Deathcharge/helix-integration/issues
- Discussions: https://github.com/Deathcharge/helix-integration/discussions
- Documentation: https://helix-integration.readthedocs.io

---

**Built with 🌀 by the Helix Collective**
