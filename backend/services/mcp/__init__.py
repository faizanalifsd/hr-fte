"""
MCP (Model Context Protocol) Integration Layer.

As per execution_plan.md:
- Only the Backend Orchestrator may invoke MCP tools
- Ollama models cannot directly access external APIs
- All MCP integrations use environment variables for authentication
"""

from .apify_service import ApifyService
from .gmail_service import GmailService
from .apollo_service import enrich_jobs_with_hr_emails

__all__ = ["ApifyService", "GmailService", "enrich_jobs_with_hr_emails"]
