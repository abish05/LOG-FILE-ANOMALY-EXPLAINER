"""
Agent orchestrator for LogSage AI.
Runs the 7-step agent loop to analyze log anomalies.
"""

import json
import logging
from datetime import datetime, timezone
import os
from typing import Dict, Any, Callable, Optional

from .ollama_client import call_ollama, call_ollama_stream
from .prompt_templates import build_analysis_prompt, build_incident_summary_prompt

logger = logging.getLogger(__name__)

def run_agent_loop(parsed_data: Dict[str, Any],
                   log_filename: str,
                   progress_callback: Optional[Callable[[int], None]] = None,
                   status_callback: Optional[Callable[[str], None]] = None,
                   token_callback: Optional[Callable[[int, str], None]] = None,
                   stream: bool = False
                   ) -> Dict[str, Any]:
    """
    Executes the 7-step agent loop to process parsed log data into a final report.

    Args:
        parsed_data (dict): The output from parse_log_file.
        log_filename (str): The name of the analyzed log file.
        progress_callback (callable, optional): Callback to update progress bar.
        status_callback (callable, optional): Callback to update status text.

    Returns:
        dict: The complete incident report.
    """
    logger.info("Starting Agent Loop")
    model_name = os.getenv("MODEL_NAME", "llama3")

    # Step 1 - Read
    logger.info("Step 1: Read parsed data")
    if "anomalies" not in parsed_data:
        raise ValueError("Parsed data is missing the 'anomalies' key.")
        
    # Step 2 - Detect
    logger.info("Step 2: Detect anomalies")
    
    # Cap to top 5 anomalies to prevent massive wait times and timeout freezes
    all_anomalies = parsed_data["anomalies"]
    anomalies = all_anomalies[:5] 
    
    if not anomalies:
        logger.info("No anomalies detected.")
    elif len(all_anomalies) > 5:
        logger.info(f"Capped analysis to first 5 anomalies out of {len(all_anomalies)}")
    
    anomaly_analyses = []
    
    # Steps 3 & 4 - Context Extract & Analyze
    logger.info(f"Step 3 & 4: Extract context and analyze {len(anomalies)} anomalies")
    for idx, anomaly in enumerate(anomalies):
        logger.info(f"Analyzing anomaly {idx + 1}/{len(anomalies)}")
        if status_callback:
            status_callback(f"Analyzing anomaly {idx + 1}/{len(anomalies)}: {anomaly.get('category', 'Unknown')}")
        if progress_callback:
            progress_callback(20 + int((idx / max(len(anomalies), 1)) * 60))
            
        prompt = build_analysis_prompt(anomaly, log_filename)

        # If streaming is requested and a token_callback is provided, stream tokens
        raw_response = ""
        if stream and token_callback:
            try:
                parts = []
                for chunk in call_ollama_stream(prompt, model=model_name):
                    # forward token to UI callback
                    try:
                        token_callback(idx, chunk)
                    except Exception:
                        # UI callback must not break analysis
                        logger.debug("token_callback raised; continuing")
                    parts.append(chunk)
                raw_response = "".join(parts)
            except Exception as e:
                logger.warning(f"Streaming LLM failed: {e}")
                raw_response = ""
        else:
            raw_response = call_ollama(prompt, model=model_name)

        # Safely parse JSON
        try:
            # Strip potential markdown code blocks like ```json ... ```
            clean_response = raw_response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            elif clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]

            analysis_dict = json.loads(clean_response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Failed to parse LLM JSON response: {e}. Using fallback.")
            analysis_dict = {
                "root_cause": "AI parse error. Raw response trimmed.",
                "category": anomaly.get("category", "Unknown Error"),
                "severity_score": 5,
                "severity_label": "Medium",
                "remediation_steps": [],
                "summary": "Analysis unavailable."
            }
            
        # Merge analysis with original anomaly data
        combined = {**anomaly, **analysis_dict}
        anomaly_analyses.append(combined)

    # Step 5 - Severity metrics
    logger.info("Step 5: Compute severity metrics")
    max_severity = 0
    total_severity = 0
    severity_distribution = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    
    for analysis in anomaly_analyses:
        score = int(analysis.get("severity_score", 0))
        max_severity = max(max_severity, score)
        total_severity += score
        
        if score >= 9:
            severity_distribution["Critical"] += 1
        elif score >= 7:
            severity_distribution["High"] += 1
        elif score >= 4:
            severity_distribution["Medium"] += 1
        else:
            severity_distribution["Low"] += 1
            
    avg_severity = total_severity / len(anomaly_analyses) if anomaly_analyses else 0.0

    # Step 6 - Recommendations (Executive Summary)
    logger.info("Step 6: Generate executive summary")
    if anomaly_analyses:
        summary_prompt = build_incident_summary_prompt(anomaly_analyses, log_filename)
        executive_summary = call_ollama(summary_prompt, model=model_name)
    else:
        executive_summary = "No anomalies were detected in the log file."

    # Step 7 - Report
    logger.info("Step 7: Assemble final report")
    final_report = {
        "log_filename": log_filename,
        "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        "total_lines": parsed_data.get("total_lines", 0),
        "errors_found": parsed_data.get("errors_found", 0),
        "category_counts": parsed_data.get("category_counts", {}),
        "severity_distribution": severity_distribution,
        "max_severity": max_severity,
        "avg_severity": round(avg_severity, 2),
        "anomaly_analyses": anomaly_analyses,
        "executive_summary": executive_summary.strip(),
        "agent_steps_completed": 7
    }

    logger.info("Agent Loop Completed")
    return final_report
