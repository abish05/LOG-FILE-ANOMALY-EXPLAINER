import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List

from agent.ollama_client import call_ollama
from agent.prompt_templates import (
    build_analysis_prompt,
    build_incident_summary_prompt,
    get_severity_label,
)

logger = logging.getLogger(__name__)

# JSON extraction: match the first {...} block (handles markdown fences gracefully)
_JSON_RE = re.compile(r'\{[\s\S]+\}', re.MULTILINE)

# Capture the body between ``` fences (optional "json" language tag)
_FENCE_RE = re.compile(r'```(?:json)?\s*([\s\S]+?)\s*```', re.IGNORECASE)

# Maximum parallel LLM workers — keeps Ollama responsive without flooding it
_MAX_WORKERS = 4


def _extract_json(raw: str) -> dict:
    """
    Robustly extract a JSON object from an LLM response.
    Handles: plain JSON, ```json fences, partial markdown, whitespace noise.
    Returns a dict or raises ValueError / JSONDecodeError.
    """
    stripped = raw.strip()

    # Fast-path: already clean JSON
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Strip markdown code fences and try the inner content
    fence_match = _FENCE_RE.search(stripped)
    if fence_match:
        inner = fence_match.group(1).strip()
        try:
            return json.loads(inner)
        except json.JSONDecodeError:
            pass

    # Try to grab the first {...} block anywhere in the response
    block_match = _JSON_RE.search(stripped)
    if block_match:
        try:
            return json.loads(block_match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON found in LLM response: {stripped[:200]}")


def _analyze_single(
    index: int,
    anomaly: Dict[str, Any],
    log_filename: str,
    total: int,
) -> Dict[str, Any]:
    """Analyze one anomaly via LLM. Called in a thread."""
    logger.info(
        f"  Analyzing anomaly {index + 1}/{total} "
        f"(line {anomaly.get('line_number')})"
    )
    prompt = build_analysis_prompt(anomaly, log_filename)
    raw_response = call_ollama(prompt)

    try:
        analysis = _extract_json(raw_response)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(
            f"JSON parse failed for anomaly {index + 1}: {e}. Using fallback."
        )
        analysis = {
            "root_cause": "AI parse error — check Ollama logs",
            "category": anomaly.get("category", "Unknown Error"),
            "severity_score": 5,
            "severity_label": "Medium",
            "remediation_steps": [
                "Review error manually",
                "Check Ollama model response",
                "Re-run analysis",
            ],
            "summary": "Analysis could not be parsed from LLM response.",
        }

    # Normalize and annotate
    analysis["line_number"] = anomaly.get("line_number")
    analysis["matched_keyword"] = anomaly.get("matched_keyword")
    analysis["line_text"] = anomaly.get("line_text")
    analysis["context_before"] = anomaly.get("context_before", [])
    analysis["context_after"] = anomaly.get("context_after", [])
    analysis["severity_score"] = max(
        1, min(10, int(analysis.get("severity_score", 5)))
    )
    analysis["severity_label"] = get_severity_label(analysis["severity_score"])
    return analysis


def run_agent_loop(
    parsed_data: Dict[str, Any],
    log_filename: str,
) -> Dict[str, Any]:
    """
    Execute the 7-step LogSage AI agent loop.

    Steps:
        1. Read & validate parsed data
        2. Detect anomalies
        3. Extract context windows
        4. Analyze each anomaly with LLM  ← now runs in parallel
        5. Classify severity distribution
        6. Generate executive summary
        7. Assemble final incident report

    Returns:
        Complete incident report dict
    """
    logger.info("=== Agent Loop START ===")

    # Step 1 — Validate
    logger.info("Step 1: Validating parsed log data")
    if "anomalies" not in parsed_data:
        raise ValueError(
            "parsed_data missing 'anomalies' key. "
            "Ensure parse_log_file() ran successfully."
        )

    # Step 2 — Extract
    logger.info("Step 2: Extracting anomalies")
    anomalies: List[Dict[str, Any]] = parsed_data["anomalies"]
    total_lines: int = parsed_data.get("total_lines", 0)
    category_counts: Dict[str, int] = parsed_data.get("category_counts", {})
    logger.info(f"Found {len(anomalies)} anomalies to analyze")

    # Step 3 — Build full context windows
    logger.info("Step 3: Building context windows for each anomaly")
    for anomaly in anomalies:
        lines = (
            anomaly.get("context_before", [])
            + [anomaly.get("line_text", "")]
            + anomaly.get("context_after", [])
        )
        anomaly["full_context"] = "\n".join(lines)

    # Step 4 — Parallel LLM analysis
    logger.info(
        f"Step 4: Running parallel LLM analysis on {len(anomalies)} anomalies "
        f"(workers={_MAX_WORKERS})"
    )
    anomaly_analyses: List[Dict[str, Any]] = [None] * len(anomalies)  # type: ignore

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(
                _analyze_single, i, anomaly, log_filename, len(anomalies)
            ): i
            for i, anomaly in enumerate(anomalies)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                anomaly_analyses[idx] = future.result()
            except Exception as exc:
                logger.error(f"Anomaly {idx + 1} analysis raised: {exc}")
                anomaly = anomalies[idx]
                anomaly_analyses[idx] = {
                    "root_cause": f"Analysis error: {exc}",
                    "category": anomaly.get("category", "Unknown Error"),
                    "severity_score": 5,
                    "severity_label": "Medium",
                    "remediation_steps": ["Review error manually"],
                    "summary": "Analysis failed due to an unexpected error.",
                    "line_number": anomaly.get("line_number"),
                    "matched_keyword": anomaly.get("matched_keyword"),
                    "line_text": anomaly.get("line_text"),
                    "context_before": anomaly.get("context_before", []),
                    "context_after": anomaly.get("context_after", []),
                }

    # Step 5 — Severity classification
    logger.info("Step 5: Computing severity distribution")
    severity_dist: Dict[str, int] = {
        "Critical": 0, "High": 0, "Medium": 0, "Low": 0
    }
    scores = [a.get("severity_score", 5) for a in anomaly_analyses]
    for a in anomaly_analyses:
        label = a.get("severity_label", "Medium")
        severity_dist[label] = severity_dist.get(label, 0) + 1

    max_severity = max(scores) if scores else 0
    avg_severity = round(sum(scores) / len(scores), 1) if scores else 0.0

    # Step 6 — Executive summary (single sequential call)
    logger.info("Step 6: Generating executive summary")
    summary_prompt = build_incident_summary_prompt(anomaly_analyses, log_filename)
    executive_summary = call_ollama(summary_prompt)
    # If Ollama returned JSON instead of prose, replace it gracefully
    if executive_summary.strip().startswith("{"):
        executive_summary = "See individual anomaly analyses for details."

    # Step 7 — Assemble final report
    logger.info("Step 7: Assembling final incident report")
    final_report: Dict[str, Any] = {
        "log_filename": log_filename,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_lines": total_lines,
        "errors_found": len(anomaly_analyses),
        "category_counts": category_counts,
        "severity_distribution": severity_dist,
        "max_severity": max_severity,
        "avg_severity": avg_severity,
        "anomaly_analyses": anomaly_analyses,
        "executive_summary": executive_summary,
        "agent_steps_completed": 7,
    }
    logger.info("=== Agent Loop COMPLETE ===")
    return final_report
