"""
OllamaService — backward-compatibility alias for LLMService.

The orchestrator imports OllamaService by name; this module satisfies that
import while delegating all behaviour to the new LLMService (Groq + OpenRouter).
"""

from .llm_service import LLMService as OllamaService

__all__ = ["OllamaService"]
