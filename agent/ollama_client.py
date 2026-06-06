"""
Ollama client for LogSage AI.
Handles API requests to the local Ollama instance with retry logic and timeout.
"""

import requests
import logging
import os
import time

logger = logging.getLogger(__name__)

def is_ollama_available() -> bool:
    """
    Checks if the local Ollama instance is running and accessible.

    Returns:
        bool: True if available, False otherwise.
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    url = f"{host}/api/tags"
    headers = {"Bypass-Tunnel-Reminder": "true"}
    try:
        response = requests.get(url, headers=headers, timeout=5)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def call_ollama(prompt: str, model: str = None) -> str:
    """
    Sends a prompt to the Ollama model and returns the generated text.
    Retries up to 3 times on connection error or timeout.

    Args:
        prompt (str): The prompt string.
        model (str): The name of the Ollama model.

    Returns:
        str: The response text or an error message if unavailable.
    """
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model_name = model or os.getenv("MODEL_NAME", "llama3")

    # First try local Ollama if available
    url = f"{host}/api/generate"
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0
        }
    }
    headers = {"Bypass-Tunnel-Reminder": "true"}

    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling Ollama model {model_name} (Attempt {attempt + 1}/{max_retries})")
            response = requests.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except (requests.exceptions.RequestException, ValueError) as e:
            logger.debug(f"Ollama request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                logger.info("Local Ollama unavailable or failed after retries, falling back to hosted API if configured.")

    # Fallback: Hugging Face Inference API (useful for free hosting like Spaces)
    hf_token = os.getenv("HF_API_TOKEN")
    hf_model = os.getenv("HF_MODEL")
    if not hf_model:
        # Map common Ollama names to valid HF model repo IDs
        if "llama3" in model_name.lower():
            hf_model = "meta-llama/Meta-Llama-3-8B-Instruct"
        elif "mistral" in model_name.lower():
            hf_model = "mistralai/Mistral-7B-Instruct-v0.2"
        else:
            hf_model = model_name
            
    if hf_token:
        try:
            return call_huggingface_inference(prompt, hf_model, hf_token)
        except Exception as e:
            logger.error(f"Hugging Face fallback failed: {e}")

    return "AI analysis unavailable. Please ensure Ollama is running locally or set `HF_API_TOKEN` for hosted inference."

def call_ollama_stream(prompt: str,
                       model: str = MODEL_NAME):
    """
    Generator that yields token chunks from Ollama streaming API.
    Never raises; yields at least one fallback string on failure.
    """
    try:
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True,
        }
        with requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json=payload,
            timeout=TIMEOUT,
            stream=True,
        ) as response:
            try:
                response.raise_for_status()
            except Exception:
                yield (
                    "AI stream unavailable: non-200 response from Ollama"
                )
                return

            # Stream lines/chunks as they arrive
            for raw in response.iter_lines(decode_unicode=True):
                if raw:
                    # yield decoded chunk
                    yield raw
            return
    except Exception as e:
        logger.error(f"call_ollama_stream error: {e}")
        yield (
            "AI analysis streaming unavailable. Ensure Ollama is running and model is pulled."
        )
        return

def call_huggingface_inference(prompt: str, model: str, token: str) -> str:
    """Call the Hugging Face Inference API (simple POST /models/{model}).

    Uses the generic Inference API which works for many text-generation models.
    Returns a best-effort string result.
    """
    api_url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.01,
            "max_new_tokens": 150
        }
    }

    # HuggingFace often returns 503 if the model is loading. Retry a few times.
    for attempt in range(5):
        response = requests.post(api_url, headers=headers, json=payload, timeout=120)
        if response.status_code == 503:
            time.sleep(5)
            continue
        response.raise_for_status()
        data = response.json()
        break
    else:
        raise Exception("HuggingFace API timed out or model failed to load after 5 retries.")

    # The HF Inference API may return a list of generations or a dict depending on model.
    if isinstance(data, list) and len(data) > 0:
        # common format: [{"generated_text": "..."}]
        first = data[0]
        if isinstance(first, dict):
            return first.get("generated_text") or first.get("text") or str(first)
        return str(first)

    if isinstance(data, dict):
        # try common keys
        if "generated_text" in data:
            return data["generated_text"]
        if "text" in data:
            return data["text"]
        # some models return {'error': ...}
        return str(data)

    return str(data)
