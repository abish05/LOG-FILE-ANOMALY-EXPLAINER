# Prompts Documentation

This document records the exact prompts used during runtime by the LogSage AI agent.

## 1. Analysis Prompt

**Template (`build_analysis_prompt`):**
```python
f"""You are an expert DevOps and Site Reliability Engineer analyzing log files.
Analyze the following error anomaly from the log file: {log_filename}

--- LOG CONTEXT ---
{context_block}
-------------------

Based on the context above, provide a detailed analysis.
You MUST output ONLY valid JSON format. Do not include any markdown formatting, backticks, or other text outside the JSON object.

The JSON object must have exactly these keys:
- "root_cause": A clear, concise explanation of the root cause (string).
- "category": Choose exactly one of ["Database Error", "Authentication Error", "Network Error", "Memory Error", "API Error", "Unknown Error"] (string).
- "severity_score": An integer between 1 and 10, where 10 is the most critical service outage (int).
- "severity_label": Based on the score, use "Low" (1-3), "Medium" (4-6), "High" (7-8), or "Critical" (9-10) (string).
- "remediation_steps": A list of 3-5 concrete, actionable steps to fix the issue (list of strings).
- "summary": A 2-3 sentence executive summary of the anomaly (string).

Output pure JSON:
"""
```

### Explanation of Sections:
- **Role Designation:** "You are an expert DevOps..." sets the persona, ensuring the LLM uses appropriate technical terminology and prioritizes system stability.
- **Context Injection:** Surrounding log lines (up to 20 before and after) are injected to provide the LLM with the sequence of events leading up to the error.
- **Strict Output Constraints:** Emphasizes "ONLY valid JSON format" and lists the exact keys required. This prevents the LLM from adding conversational text.

## 2. Incident Summary Prompt

**Template (`build_incident_summary_prompt`):**
```python
f"""You are a Senior Engineering Manager reporting on a recent production incident.
Based on the following parsed anomalies from {log_filename}, provide a brief executive incident summary.

--- ANOMALIES ---
{analyses_text}
-----------------

Write a plain text executive summary covering:
1. What happened (the overall incident)
2. Potential business impact
3. Immediate actions taken or required
4. Preventive measures for the future

Keep it concise, professional, and to the point. Maximum 200 words.
Do not use markdown formatting.
"""
```

## 3. JSON Output Enforcement Technique
Ollama (especially LLaMA 3) can sometimes wrap JSON in markdown block ticks (` ```json `). To enforce pure JSON, the prompt ends exactly at `Output pure JSON:\n`. 
In the Python code (`analyzer.py`), we safely parse this by explicitly stripping any markdown backticks that the model might stubbornly add, before passing it to `json.loads()`.

## 4. Retry/Fallback Strategy
If the LLM hallucinates an invalid JSON structure, or if the local Ollama instance times out, the `analyzer.py` catches the `JSONDecodeError`. It then constructs a fallback dictionary:
```python
{
    "root_cause": "AI parse error...",
    "category": "Unknown Error",
    "severity_score": 5,
    "severity_label": "Medium",
    "remediation_steps": [],
    "summary": "N/A"
}
```
This guarantees the Streamlit UI and the PDF report generator never crash due to a bad LLM response.
