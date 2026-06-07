"""
Unified LLM client for LogSage AI (now under ai_engine.agent).
"""
import os
import logging
import requests
from typing import Optional

logger = logging.getLogger(__name__)

# Groq Cloud API — OpenAI-compatible, free tier, no credit card
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
_GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

_FALLBACK_JSON = (
    '{"root_cause": "AI analysis unavailable — rule-based analysis used", '
    '"category": "Unknown Error", '
    '"severity_score": 5, '
    '"severity_label": "Medium", '
    '"remediation_steps": ['
    '"Review error manually", '
    '"Check application logs", '
    '"Contact development team"], '
    '"summary": "AI analysis unavailable. Rule-based classification applied."}'
)


def is_groq_available() -> bool:
    """True if GROQ_API_KEY env var is set (key existence, not validity)."""
    return bool(os.getenv("GROQ_API_KEY", "").strip())


def _call_groq(prompt: str) -> Optional[str]:
    """
    Call Groq Cloud API (OpenAI-compatible).
    Returns response text or None on any failure.
    """
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        return None

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": _GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 600,
    }

    try:
        resp = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"].strip()
        logger.info(f"Groq response received (model={_GROQ_MODEL})")
        return content
    except requests.exceptions.HTTPError as e:
        logger.error(f"Groq HTTP error {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        logger.error(f"Groq API error: {e}")
    return None


def get_ai_status() -> dict:
    """
    Returns the current AI provider status for the sidebar.
    Dict keys: provider (str), available (bool), model (str)
    """
    if is_groq_available():
        return {
            "provider": "Groq",
            "available": True,
            "model": _GROQ_MODEL,
            "icon": "🟢",
            "label": f"Groq AI online · {_GROQ_MODEL}",
        }

    # Lazy import to avoid circular deps
    from ai_engine.agent.ollama_client import is_ollama_available, _get_model
    if is_ollama_available():
        return {
            "provider": "Ollama",
            "available": True,
            "model": _get_model(),
            "icon": "🟢",
            "label": f"Ollama online · {_get_model()}",
        }

    return {
        "provider": "Rule-based",
        "available": True,   # rule-based ALWAYS works
        "model": "built-in",
        "icon": "🔵",
        "label": "Rule-based mode · no API key needed",
    }


def call_llm(prompt: str) -> str:
    """
    Unified LLM call. Tries Groq → Ollama → fallback JSON.
    Never raises — always returns a parseable string.
    """
    # 1. Groq Cloud
    if is_groq_available():
        result = _call_groq(prompt)
        if result:
            return result
        logger.warning("Groq failed — falling back to Ollama/rule-based")

    # 2. Local Ollama
    from ai_engine.agent.ollama_client import is_ollama_available, call_ollama
    if is_ollama_available():
        return call_ollama(prompt)

    # 3. No LLM — rule-based takes over in analyzer.py
    logger.info("No LLM available — rule-based fallback will be used")
    return _FALLBACK_JSON
