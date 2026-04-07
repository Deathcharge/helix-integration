"""Helix Integration Layer - v16.9"""
__version__ = "16.9"
from .zapier import ZapierClient
from .discord import DiscordService
from .manus import ManusExecutor
from .notion import NotionClient
__all__ = ["ZapierClient", "DiscordService", "ManusExecutor", "NotionClient"]
