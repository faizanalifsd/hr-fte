"""
DEPRECATED — Gemini service removed.

AI sub-agent tasks are handled by the service in:
backend/services/ai/ollama_service.py

LLM provider to be configured.
"""

# Re-export OllamaService under the old name for backward compatibility
# with any direct imports still referencing GeminiService.
from .ollama_service import OllamaService as GeminiService  # noqa: F401

__all__ = ["GeminiService"]
