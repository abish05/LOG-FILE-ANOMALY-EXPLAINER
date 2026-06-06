import os
import time
import logging
import requests

logger = logging.getLogger(__name__)

OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
TIMEOUT = 120
MAX_RETRIES = 3


def _get_model() -> str:
    """Read MODEL_NAME fresh from env each call so sidebar selector works."""
    return os.getenv("MODEL_NAME", "llama3")


def is_ollama_available() -> bool:
    """Check if Ollama service is reachable."""
    try:
        resp = requests.get(
            f"{OLLAMA_HOST}/api/tags", timeout=5
        )
        return resp.status_code == 200
    except Exception:
        return False


def call_ollama(prompt: str, model: str | None = None) -> str:
    """
    Send prompt to Ollama and return response text.

    - model defaults to MODEL_NAME env var so the sidebar selector is honoured.
    - Retries up to MAX_RETRIES with exponential back-off.
    - Never raises — returns a safe fallback JSON string on total failure.
    """
    if model is None:
        model = _get_model()

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            # Encourage terse, structured responses — faster generation
            "temperature": 0.2,
            "num_predict": 512,
        },
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info(
                f"Ollama request attempt {attempt}/{MAX_RETRIES} "
                f"(model={model})"
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

    # Total failure fallback — valid JSON so the caller can parse it
    return (
        '{"root_cause": "AI analysis unavailable", '
        '"category": "Unknown Error", '
        '"severity_score": 5, '
        '"severity_label": "Medium", '
        '"remediation_steps": ['
        '"Ensure Ollama is running: ollama serve", '
        '"Pull the model: ollama pull llama3", '
        '"Check OLLAMA_HOST env var"], '
        '"summary": "AI analysis could not be completed. '
        'Please ensure Ollama is running and llama3 is pulled."}'
    )
