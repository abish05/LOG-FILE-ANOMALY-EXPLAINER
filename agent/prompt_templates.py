"""Thin re-export shim — real implementation lives in ai_engine.agent.prompt_templates."""
from ai_engine.agent.prompt_templates import (
    build_analysis_prompt,
    build_incident_summary_prompt,
    get_severity_label,
    SEVERITY_LABELS,
)

__all__ = [
    "build_analysis_prompt",
    "build_incident_summary_prompt",
    "get_severity_label",
    "SEVERITY_LABELS",
]
