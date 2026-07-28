"""
Helix Unified Integrations Module

This module provides integration utilities including:
- Zapier integration
- Notion sync
- Platform integrations
- Claude/LLM integrations
"""

import logging

logger = logging.getLogger(__name__)

# Zapier
try:
    from .zapier_integration import HelixZapierIntegration, get_zapier, set_zapier
except ImportError as e:
    logger.debug("Zapier integration not available: %s", e)

# Notion
try:
    from .notion_sync import NotionSync
except ImportError as e:
    logger.debug("Notion sync not available: %s", e)

# Platform integrations
try:
    from .platform_integrations import PlatformIntegrationManager
except ImportError as e:
    logger.debug("Platform integrations not available: %s", e)

# Privacy anonymization for PII protection
try:
    from .privacy_anonymizer import PrivacyAnonymizer
except ImportError as e:
    logger.debug("Privacy anonymizer not available: %s", e)

__all__ = [
    "HelixZapierIntegration",
    "NotionSync",
    "PlatformIntegrationManager",
    "PrivacyAnonymizer",
    "get_zapier",
    "set_zapier",
]
