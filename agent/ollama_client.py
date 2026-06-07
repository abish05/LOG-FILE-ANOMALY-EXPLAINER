"""Thin re-export shim — real implementation lives in ai_engine.agent.ollama_client."""
from ai_engine.agent.ollama_client import call_ollama, is_ollama_available, _get_model

__all__ = ["call_ollama", "is_ollama_available", "_get_model"]
