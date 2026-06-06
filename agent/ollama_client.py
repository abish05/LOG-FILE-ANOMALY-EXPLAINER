import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT = 60
MAX_RETRIES = 3

# Single canonical fallback — valid JSON that _extract_json() can parse
_FALLBACK_JSON = (
    '{"root_cause": "Ollama AI offline — rule-based analysis used", '
    '"category": "Unknown Error", '
    '"severity_score": 5, '
    '"severity_label": "Medium", '
    '"remediation_steps": ['
    '"Start Ollama locally: ollama serve", '
    '"Pull the model: ollama pull llama3", '
    '"Set OLLAMA_HOST env var if running remotely"], '
    '"summary": "LLM analysis unavailable. Rule-based classification applied."}'
)

# Module-level availability cache — avoids re-probing Ollama on every analysis
# Cached for 30 seconds; set to None to force a fresh check.
_ollama_cache: dict = {"available": None, "checked_at": 0.0}
_CACHE_TTL = 30  # seconds


def _get_model() -> str:
    """Read MODEL_NAME fresh from env each call so the sidebar selector works."""
    return os.getenv("MODEL_NAME", "llama3")


def is_ollama_available() -> bool:
    """
    Check if Ollama service is reachable.
    Result is cached for 30 seconds to avoid repeated probes.
    """
    now = time.monotonic()
    if (
        _ollama_cache["available"] is not None
        and now - _ollama_cache["checked_at"] < _CACHE_TTL
    ):
        return _ollama_cache["available"]  # type: ignore[return-value]

    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        result = resp.status_code == 200
    except Exception:
        result = False

    _ollama_cache["available"] = result
    _ollama_cache["checked_at"] = now
    logger.info(f"Ollama availability probe: {'online' if result else 'offline'}")
    return result


def call_ollama(prompt: str, model: str | None = None) -> str:
    """
    Send prompt to Ollama and return response text.

    - Checks availability first (cached) — if offline, returns fallback INSTANTLY.
    - When online, retries up to MAX_RETRIES with exponential back-off.
    - Never raises — always returns a parseable string.
    """
    if model is None:
        model = _get_model()

    # ── Fast offline path ──────────────────────────────────────────────────────
    if not is_ollama_available():
        logger.warning("Ollama offline — returning rule-based fallback immediately")
        return _FALLBACK_JSON

    # ── Online path ────────────────────────────────────────────────────────────
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 512,
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Ollama request attempt {attempt}/{MAX_RETRIES} (model={model})"
            )
            response = requests.post(
                f"{OLLAMA_HOST}/api/generate",
                json=payload,
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            result = data.get("response", "").strip()
            if result:
                logger.info("Ollama response received successfully")
                return result
            logger.warning("Empty response from Ollama")
        except requests.exceptions.ConnectionError:
            logger.error(f"Ollama connection failed (attempt {attempt})")
        except requests.exceptions.Timeout:
            logger.error(f"Ollama timeout (attempt {attempt})")
        except Exception as e:
            logger.error(f"Ollama unexpected error: {e}")

        if attempt < MAX_RETRIES:
            wait = 2 ** attempt
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    return _FALLBACK_JSON
