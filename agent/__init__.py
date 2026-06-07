"""Agent package (shim re-exporting ai_engine.agent).

This package keeps the original `agent.*` import paths working while the
actual implementations live under `ai_engine.agent` for team alignment.
"""

from .analyzer import run_agent_loop
from .llm_client import call_llm, get_ai_status
from .ollama_client import call_ollama, is_ollama_available
from .prompt_templates import build_analysis_prompt, build_incident_summary_prompt

__all__ = [
	"run_agent_loop",
	"call_llm",
	"get_ai_status",
	"call_ollama",
	"is_ollama_available",
	"build_analysis_prompt",
	"build_incident_summary_prompt",
]
