"""Thin re-export shim — real implementation lives in ai_engine.agent.llm_client."""
from ai_engine.agent.llm_client import call_llm, get_ai_status, is_groq_available

__all__ = ["call_llm", "get_ai_status", "is_groq_available"]
