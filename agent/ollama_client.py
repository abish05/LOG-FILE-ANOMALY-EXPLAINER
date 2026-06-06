import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT = 60
MAX_RETRIES = 3

# Single canonical fallback — valid JSON for _extract_json()
_FALLBACK_JSON = (
    '{"root_cause": "Ollama AI offline — rule-based analysis used", '
    '"category": "Unknown Error", '
    '"severity_score": 5, '
    '"severity_label": "Medium", '
    '"remediation_steps": ['
    '"Start Ollama locally: ollama serve", '
    '"Pull the model: ollama pull llama3", '
    '"Set OLLAMA_HOST env var if running remotely"], '
    '"summary": "LLM analysis unavailable. '
    'Rule-based classification was applied automatically."}'
)


def _get_model() -> str:
    """Read MODEL_NAME fresh from env each call so the sidebar selector works."""
    return os.getenv("MODEL_NAME", "llama3")


def is_ollama_available() -> bool:
    """Check if Ollama service is reachable (quick 3-second probe)."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)
        return resp.status_code == 200
    except Exception:
        return False


def call_ollama(prompt: str, model: str | None = None) -> str:
    """
    Send prompt to Ollama and return response text.

    - Checks availability first — if offline, returns fallback INSTANTLY
      (no retry delays) so the UI never freezes.
    - When online, retries up to MAX_RETRIES with exponential back-off.
    - Never raises — always returns a parseable string.
    """
    if model is None:
        model = _get_model()

    # ── Fast offline path ──────────────────────────────────────────────────────
    # Check once upfront. If Ollama isn't reachable, return immediately —
    # no retries, no sleeping, no 120-second timeouts.
    if not is_ollama_available():
        logger.warning("Ollama offline — returning rule-based fallback immediately")
        return _FALLBACK_JSON

    # ── Online path ────────────────────────────────────────────────────────────
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,     # deterministic → faster
            "num_predict": 512,     # JSON fits in ~200 tokens → stop early
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
            wait = 2 ** attempt  # 2s, 4s
            logger.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    return _FALLBACK_JSON
