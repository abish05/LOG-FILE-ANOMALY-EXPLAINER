# AI Usage Notes for Development

This document outlines how AI and prompt engineering were used to develop the LogSage AI prototype.

## Prompts Used for Generation

### Core Architecture Prompt
**Prompt sent to AI:**
"Design a 7-step agent loop in Python that takes parsed log anomalies, extracts context, queries a local Ollama model to find root cause and remediation, calculates severity metrics, generates an executive summary, and returns a JSON report."

**Reasoning:**
This prompt enforces a structured processing pipeline. By explicitly demanding 7 steps, the AI understands the need for a separation of concerns (parsing, context gathering, LLM querying, metrics, and aggregation).

### LLM Output Constraining
**Prompt sent to AI:**
"Write an f-string template that forces the LLaMA 3 model to output *only* valid JSON. It must contain the keys: root_cause, category, severity_score, severity_label, remediation_steps, and summary. Give an example of how to parse this safely in Python, accounting for markdown blocks."

**Reasoning:**
Local models like LLaMA 3 often output conversational padding ("Here is your JSON: ..."). The prompt explicitly asks for a defense mechanism (safe JSON parsing with markdown stripping).

## Techniques Used

1. **Few-Shot Prompting (Implicit):** The structure of the `build_incident_summary_prompt` implicitly guides the LLM by formatting the anomalies clearly into a text block, acting as context shots for the final summary generation.
2. **Output Constraints:** Using `json.loads` combined with `strip()` and markdown code block removal enforces structural integrity.
3. **Fallback Engineering:** The agent loop is designed with a try-except block that yields a "safe" default dictionary if the AI hallucinates, ensuring the application remains robust.
