import json
from typing import List, Dict, Any

SEVERITY_LABELS = {
    (1, 3): "Low",
    (4, 6): "Medium",
    (7, 8): "High",
    (9, 10): "Critical",
}

def get_severity_label(score: int) -> str:
    """Map numeric score to severity label."""
    for (low, high), label in SEVERITY_LABELS.items():
        if low <= score <= high:
            return label
    return "Medium"

def build_analysis_prompt(anomaly: Dict[str, Any],
                          log_filename: str) -> str:
    """Build per-anomaly analysis prompt for the LLM."""
    context_before = "\n".join(anomaly.get("context_before", []))
    context_after = "\n".join(anomaly.get("context_after", []))
    error_line = anomaly.get("line_text", "")
    keyword = anomaly.get("matched_keyword", "ERROR")
    category = anomaly.get("category", "Unknown Error")

    return f"""You are an expert Site Reliability Engineer analyzing production logs.

Log file: {log_filename}
Detected keyword: {keyword}
Pre-classified category: {category}

=== CONTEXT BEFORE ERROR ===
{context_before}

=== ERROR LINE ===
{error_line}

=== CONTEXT AFTER ERROR ===
{context_after}

Analyze this log error and respond with ONLY a valid JSON object.
No markdown, no code fences, no explanation — pure JSON only.

Required JSON structure:
{{
  "root_cause": "One clear sentence explaining the root cause",
  "category": "One of: Database Error, Authentication Error, Network Error, Memory Error, API Error, Unknown Error",
  "severity_score": <integer 1-10>,
  "severity_label": "One of: Low, Medium, High, Critical",
  "remediation_steps": [
    "Step 1: specific actionable fix",
    "Step 2: specific actionable fix",
    "Step 3: specific actionable fix"
  ],
  "summary": "2-3 sentence incident summary for an on-call engineer"
}}

Severity scoring guide:
1-3 = Low (warnings, minor issues, no user impact)
4-6 = Medium (degraded performance, partial failures)
7-8 = High (service disruption, data at risk)
9-10 = Critical (complete outage, data loss, security breach)

Respond with ONLY the JSON object. Nothing else."""

def build_incident_summary_prompt(all_analyses: List[Dict[str, Any]],
                                  log_filename: str) -> str:
    """Build executive summary prompt for the full incident."""
    error_count = len(all_analyses)
    max_sev = max((a.get("severity_score", 0) for a in all_analyses),
                  default=0)
    categories = list({a.get("category", "") for a in all_analyses})
    root_causes = [a.get("root_cause", "") for a in all_analyses[:5]]

    return f"""You are a senior SRE writing an executive incident summary.

Log file: {log_filename}
Total anomalies detected: {error_count}
Highest severity: {max_sev}/10
Error categories involved: {', '.join(categories)}
Key root causes identified:
{json.dumps(root_causes, indent=2)}

Write a concise executive incident summary (maximum 150 words) covering:
1. What happened (the main failure)
2. Estimated business impact
3. Immediate actions taken or required
4. Top 2 preventive measures

Write in plain text. No JSON, no bullet points, no headers.
Professional engineering tone. Maximum 150 words."""
