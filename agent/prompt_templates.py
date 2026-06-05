"""
Prompt templates for LogSage AI.
Defines instructions for the Ollama LLM to analyze anomalies and generate summaries.
"""

from typing import List, Dict, Any

SEVERITY_LABELS = {
    range(1, 4): "Low",
    range(4, 7): "Medium",
    range(7, 9): "High",
    range(9, 11): "Critical"
}

def build_analysis_prompt(anomaly: Dict[str, Any], log_filename: str) -> str:
    """
    Returns a prompt that instructs the LLM to:
    - Read the error context (inject context_before + line + context_after)
    - Identify root cause
    - Determine category from the 6 defined categories
    - Assign severity 1-10 with justification
    - List 3-5 concrete remediation steps
    - Output ONLY valid JSON
    """
    context_lines = []
    if "context_before" in anomaly:
        context_lines.extend(anomaly["context_before"])
    context_lines.append(f">>> {anomaly.get('line_text', '')} <<<")
    if "context_after" in anomaly:
        context_lines.extend(anomaly["context_after"])
        
    context_block = "\n".join(context_lines)
    
    return f"""You are an expert DevOps and Site Reliability Engineer analyzing log files.
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

def build_incident_summary_prompt(all_analyses: List[Dict[str, Any]], log_filename: str) -> str:
    """
    Returns a prompt that instructs the LLM to produce an executive
    incident summary covering: what happened, business impact, immediate
    actions, preventive measures. Output plain text, max 200 words.
    """
    analyses_text = ""
    for idx, analysis in enumerate(all_analyses, 1):
        analyses_text += f"Anomaly {idx}:\n"
        analyses_text += f"- Category: {analysis.get('category', 'Unknown')}\n"
        analyses_text += f"- Severity: {analysis.get('severity_score', 0)}/10\n"
        analyses_text += f"- Root Cause: {analysis.get('root_cause', 'N/A')}\n"
        analyses_text += f"- Summary: {analysis.get('summary', 'N/A')}\n\n"
        
    return f"""You are a Senior Engineering Manager reporting on a recent production incident.
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
