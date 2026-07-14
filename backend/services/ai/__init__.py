"""
AI Service Layer — Groq (primary) + OpenRouter (fallback) + rule-based.

Import LLMService for new code. OllamaService is kept as an alias for
backward compatibility with existing orchestrator imports.
"""

from .llm_service import LLMService
from .ollama_service import OllamaService  # alias → LLMService

try:
    from .claude_service import ClaudeService
    __all__ = ["LLMService", "OllamaService", "ClaudeService"]
except ImportError:
    __all__ = ["LLMService", "OllamaService"]
