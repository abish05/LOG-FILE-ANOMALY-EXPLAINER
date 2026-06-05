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
    try:
        response = requests.get(url, timeout=5)
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
    url = f"{host}/api/generate"
    
    payload = {
        "model": model_name,
        "prompt": prompt,
        "stream": False
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            logger.info(f"Calling Ollama model {model} (Attempt {attempt + 1}/{max_retries})")
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data.get("response", "")
        except requests.exceptions.RequestException as e:
            logger.warning(f"Ollama request failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2) # wait before retrying
            else:
                logger.error("All retries to Ollama failed.")
                return "AI analysis unavailable. Please ensure Ollama is running: `ollama serve` and `ollama pull llama3`"
    
    return "AI analysis unavailable."
