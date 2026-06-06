AI Usage Notes for LogSage AI
=================================

This document describes the prompts, JSON-only constraint enforcement, chain-of-thought handling, and retry/fallback rationale used by LogSage AI.

Prompts used
-----------
- Per-anomaly analysis prompt (used by `agent.prompt_templates.build_analysis_prompt`):
  - Instructs the model to produce ONLY valid JSON describing `root_cause`, `category`, `severity_score`, `severity_label`, `remediation_steps`, and `summary`.
  - Includes context before/after the error and the error line.

- Incident summary prompt (used by `agent.prompt_templates.build_incident_summary_prompt`):
  - Requests a concise executive summary (plain text) describing what happened, impact, action, and preventive measures.

How JSON-only output was enforced
-------------------------------
- Prompts explicitly say: "Respond with ONLY the JSON object. No markdown, no code fences, no explanation." This reduces likelihood of extra content.
- The analyzer implements robust cleaning:
  - Strips leading/trailing whitespace and common code-fence markers (```json / ```).
  - Wraps `json.loads()` in try/except and falls back to a safe default analysis dict when parsing fails.
- The UI and DB only accept parsed JSON. If parsing fails, a human-readable fallback is stored and the system continues safely.

Chain-of-thought rationale
--------------------------
- We avoid exposing chain-of-thought to the LLM output because it can produce non-JSON text. Instead, we embed structured context and explicit instructions.
- The prompt supplies the error line and ±20 lines of context, enabling the LLM to reason locally without revealing internal chain-of-thought.

Retry and fallback strategy
--------------------------
- Local Ollama is preferred. The client retries network errors with exponential backoff.
- If local Ollama is unreachable, the code tries a Hugging Face Inference fallback when `HF_API_TOKEN` and `HF_MODEL` are provided.
- All LLM calls are guarded: streaming and non-streaming helpers never raise; they return a controlled string or yield fallback tokens.
- The analyzer enforces numeric bounds for `severity_score` and maps to labels with `get_severity_label()`.

Operational guidance
--------------------
- Ensure `OLLAMA_HOST` points to your running Ollama instance or set `HF_API_TOKEN` for cloud fallback.
- For best JSON compliance, prefer deterministic, low-temperature model settings.

Support and debugging
---------------------
- When JSON parsing fails, check the raw LLM response in logs and consider lowering temperature or rephrasing prompts.
- If streaming shows truncated tokens, verify network stability and that the Ollama service supports streaming on `/api/generate`.

End of AI usage notes.
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
