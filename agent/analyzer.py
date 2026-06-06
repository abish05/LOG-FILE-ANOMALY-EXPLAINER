import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from agent.llm_client import call_llm, is_groq_available
from agent.ollama_client import is_ollama_available
from agent.prompt_templates import (
    build_analysis_prompt,
    build_incident_summary_prompt,
    get_severity_label,
)

logger = logging.getLogger(__name__)

# JSON extraction patterns
_JSON_RE = re.compile(r'\{[\s\S]+\}', re.MULTILINE)
_FENCE_RE = re.compile(r'```(?:json)?\s*([\s\S]+?)\s*```', re.IGNORECASE)

# Parallel LLM workers
_MAX_WORKERS = 4

# ── Rule-based fallback analysis ───────────────────────────────────────────────
_RULE_BASED: Dict[str, Dict[str, Any]] = {
    "Database Error": {
        "root_cause": "Database connection or query failure detected in the application log.",
        "severity_score": 7,
        "remediation_steps": [
            "Check database server status and network connectivity",
            "Verify connection string, credentials, and pool settings",
            "Review database server error logs for OOM or lock contention",
        ],
        "summary": (
            "A database error was detected. The application may be unable to connect "
            "to or query the database, potentially causing data read/write failures."
        ),
    },
    "Authentication Error": {
        "root_cause": "Authentication or authorisation failure — invalid token, expired session, or wrong credentials.",
        "severity_score": 6,
        "remediation_steps": [
            "Verify user credentials, API keys, and token expiry",
            "Check authentication service availability (OAuth provider, LDAP, etc.)",
            "Review access control policies and 401/403 response payloads",
        ],
        "summary": (
            "An authentication error was detected. Users or services may be unable "
            "to log in or access protected resources."
        ),
    },
    "Network Error": {
        "root_cause": "Network connectivity or service reachability issue — timeout, DNS failure, or refused connection.",
        "severity_score": 6,
        "remediation_steps": [
            "Verify network connectivity between services and DNS resolution",
            "Check firewall rules and security group settings",
            "Implement or tune retry logic and circuit breakers",
        ],
        "summary": (
            "A network error was detected. Services may be unable to communicate "
            "with each other or external dependencies."
        ),
    },
    "Memory Error": {
        "root_cause": "Memory allocation failure or out-of-memory condition — heap exhausted or GC overhead limit exceeded.",
        "severity_score": 8,
        "remediation_steps": [
            "Increase heap size (e.g. -Xmx for JVM) or container memory limits",
            "Profile memory usage to identify leaks (heapdump, MAT, memray)",
            "Tune GC settings or switch to a more memory-efficient data structure",
        ],
        "summary": (
            "A memory error was detected. The application is likely running low on "
            "available heap or system memory, risking crashes and data loss."
        ),
    },
    "API Error": {
        "root_cause": "API request failure — unexpected HTTP status code, malformed payload, or rate-limit exceeded.",
        "severity_score": 5,
        "remediation_steps": [
            "Check API endpoint URL, authentication headers, and payload format",
            "Review HTTP response codes (4xx = client error, 5xx = server error)",
            "Implement exponential back-off and respect rate-limit headers",
        ],
        "summary": (
            "An API error was detected. External or internal HTTP/REST calls "
            "are failing, which may degrade application functionality."
        ),
    },
    "Unknown Error": {
        "root_cause": "An unclassified application error was detected. Manual review of the log context is required.",
        "severity_score": 5,
        "remediation_steps": [
            "Examine the full log context (±20 lines) around this error",
            "Search the stack trace or error code in the project issue tracker",
            "Enable DEBUG logging temporarily to capture more detail",
        ],
        "summary": (
            "An unclassified error was detected. The root cause could not be "
            "determined automatically — manual investigation is recommended."
        ),
    },
}


def _rule_based_analysis(anomaly: Dict[str, Any]) -> Dict[str, Any]:
    """Generate meaningful analysis from rules when no LLM is available."""
    category = anomaly.get("category", "Unknown Error")
    template = _RULE_BASED.get(category, _RULE_BASED["Unknown Error"]).copy()
    keyword = anomaly.get("matched_keyword", "ERROR")
    line_text = anomaly.get("line_text", "")
    snippet = line_text[:120].strip() if line_text else ""
    template["root_cause"] = (
        f"[{keyword}] {template['root_cause']}"
        + (f" Detected in: \"{snippet}\"" if snippet else "")
    )
    score = template["severity_score"]
    return {
        "root_cause": template["root_cause"],
        "category": category,
        "severity_score": score,
        "severity_label": get_severity_label(score),
        "remediation_steps": template["remediation_steps"],
        "summary": template["summary"],
    }


def _extract_json(raw: str) -> dict:
    """Robustly extract JSON from LLM response (handles fences, prose, plain JSON)."""
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass
    fence_match = _FENCE_RE.search(stripped)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass
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
    offline: bool,
) -> Dict[str, Any]:
    """Analyze one anomaly — LLM (Groq/Ollama) or rule-based fallback."""
    logger.info(
        f"  Analyzing anomaly {index + 1}/{total} "
        f"(line {anomaly.get('line_number')}) "
        f"[{'offline/rule-based' if offline else 'LLM'}]"
    )

    if offline:
        analysis = _rule_based_analysis(anomaly)
    else:
        prompt = build_analysis_prompt(anomaly, log_filename)
        raw_response = call_llm(prompt)
        try:
            analysis = _extract_json(raw_response)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"JSON parse failed for anomaly {index + 1}: {e}. Falling back to rule-based.")
            analysis = _rule_based_analysis(anomaly)

    analysis["line_number"] = anomaly.get("line_number")
    analysis["matched_keyword"] = anomaly.get("matched_keyword")
    analysis["line_text"] = anomaly.get("line_text")
    analysis["context_before"] = anomaly.get("context_before", [])
    analysis["context_after"] = anomaly.get("context_after", [])
    analysis["severity_score"] = max(1, min(10, int(analysis.get("severity_score", 5))))
    analysis["severity_label"] = get_severity_label(analysis["severity_score"])
    return analysis


def run_agent_loop(
    parsed_data: Dict[str, Any],
    log_filename: str,
    progress_cb: Optional[Callable[[int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Execute the 7-step LogSage AI agent loop.
    Uses Groq Cloud → Ollama → Rule-based in that priority order.
    """
    def _progress(pct: int, msg: str) -> None:
        logger.info(f"[{pct}%] {msg}")
        if progress_cb:
            progress_cb(pct, msg)

    _progress(5, "Step 1 — Validating parsed log data...")
    logger.info("=== Agent Loop START ===")

    if "anomalies" not in parsed_data:
        raise ValueError("parsed_data missing 'anomalies' key.")

    _progress(15, "Step 2 — Extracting anomalies...")
    anomalies: List[Dict[str, Any]] = parsed_data["anomalies"]
    total_lines: int = parsed_data.get("total_lines", 0)
    category_counts: Dict[str, int] = parsed_data.get("category_counts", {})
    logger.info(f"Found {len(anomalies)} anomalies to analyze")

    _progress(25, "Step 3 — Building context windows...")
    for anomaly in anomalies:
        lines = (
            anomaly.get("context_before", [])
            + [anomaly.get("line_text", "")]
            + anomaly.get("context_after", [])
        )
        anomaly["full_context"] = "\n".join(lines)

    # Determine AI mode — Groq takes priority over Ollama
    groq_on = is_groq_available()
    ollama_on = is_ollama_available()
    offline = not (groq_on or ollama_on)

    if groq_on:
        mode_label = "Groq Cloud API · llama-3.1-8b-instant"
        analysis_mode = "groq"
    elif ollama_on:
        mode_label = "Ollama (local LLM)"
        analysis_mode = "ollama"
    else:
        mode_label = "rule-based (no LLM configured)"
        analysis_mode = "rule-based"

    _progress(35, f"Step 4 — Analyzing {len(anomalies)} anomalies via {mode_label}...")

    anomaly_analyses: List[Optional[Dict[str, Any]]] = [None] * len(anomalies)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {
            pool.submit(_analyze_single, i, anomaly, log_filename, len(anomalies), offline): i
            for i, anomaly in enumerate(anomalies)
        }
        done_count = 0
        for future in as_completed(futures):
            idx = futures[future]
            try:
                anomaly_analyses[idx] = future.result()
            except Exception as exc:
                logger.error(f"Anomaly {idx + 1} analysis raised: {exc}")
                anomaly = anomalies[idx]
                anomaly_analyses[idx] = {
                    **_rule_based_analysis(anomaly),
                    "line_number": anomaly.get("line_number"),
                    "matched_keyword": anomaly.get("matched_keyword"),
                    "line_text": anomaly.get("line_text"),
                    "context_before": anomaly.get("context_before", []),
                    "context_after": anomaly.get("context_after", []),
                }
            done_count += 1
            pct = 35 + int(done_count / max(len(anomalies), 1) * 35)
            _progress(pct, f"Step 4 — Analyzed {done_count}/{len(anomalies)} anomalies...")

    _progress(75, "Step 5 — Computing severity distribution...")
    severity_dist: Dict[str, int] = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    scores = [a.get("severity_score", 5) for a in anomaly_analyses if a]
    for a in anomaly_analyses:
        if a:
            label = a.get("severity_label", "Medium")
            severity_dist[label] = severity_dist.get(label, 0) + 1

    max_severity = max(scores) if scores else 0
    avg_severity = round(sum(scores) / len(scores), 1) if scores else 0.0

    _progress(85, "Step 6 — Generating executive summary...")
    if offline:
        top_cats = list({a.get("category", "Unknown") for a in anomaly_analyses if a})
        executive_summary = (
            f"Rule-based incident summary: {len(anomaly_analyses)} anomalies detected "
            f"in '{log_filename}'. "
            f"Error categories: {', '.join(top_cats) if top_cats else 'Unknown'}. "
            f"Max severity: {max_severity}/10. "
            f"Set GROQ_API_KEY in Render environment for full AI-powered analysis."
        )
    else:
        valid_analyses = [a for a in anomaly_analyses if a is not None]
        summary_prompt = build_incident_summary_prompt(valid_analyses, log_filename)
        executive_summary = call_llm(summary_prompt)
        if executive_summary.strip().startswith("{"):
            executive_summary = "See individual anomaly analyses for details."

    _progress(95, "Step 7 — Assembling final incident report...")
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
        "analysis_mode": analysis_mode,
    }
    _progress(100, "Analysis complete!")
    logger.info("=== Agent Loop COMPLETE ===")
    return final_report
