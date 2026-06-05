"""
Log parsing module for LogSage AI.
Scans log content for error keywords, extracts surrounding context, and classifies errors.
"""

import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

ERROR_KEYWORDS = ["ERROR", "EXCEPTION", "FAILED", "TIMEOUT", "CRITICAL", "FATAL"]

def classify_error(line_text: str, context: List[str]) -> str:
    """
    Classifies a given log error line into a known category based on keywords.

    Args:
        line_text (str): The specific line containing the error.
        context (list[str]): The lines surrounding the error for additional context.

    Returns:
        str: The determined category string.
    """
    # Combine line and context to increase the chance of finding a matching keyword
    full_text = ("\n".join(context) + "\n" + line_text).lower()
    
    # 1. Database Error
    if any(kw in full_text for kw in ["sql", "database", "db", "connection refused", "5432", "3306"]):
        return "Database Error"
        
    # 2. Authentication Error
    if any(kw in full_text for kw in ["auth", "login", "password", "token", "401", "403", "unauthorized"]):
        return "Authentication Error"
        
    # 3. Network Error
    if any(kw in full_text for kw in ["timeout", "connection", "network", "dns", "socket", "502", "503"]):
        return "Network Error"
        
    # 4. Memory Error
    if any(kw in full_text for kw in ["memory", "heap", "oom", "out of memory", "gc overhead"]):
        return "Memory Error"
        
    # 5. API Error
    if any(kw in full_text for kw in ["api", "endpoint", "request", "response", "http", "404", "500"]):
        return "API Error"
        
    # 6. Fallback
    return "Unknown Error"

def parse_log_file(file_content: str) -> Dict[str, Any]:
    """
    Parses raw log file content to identify anomalies, context, and categories.

    Args:
        file_content (str): The full content of the log file.

    Returns:
        dict: A dictionary containing parsing results and metrics.
    """
    start_time = time.time()
    
    lines = file_content.splitlines()
    total_lines = len(lines)
    anomalies = []
    category_counts = {}
    
    for i, line in enumerate(lines):
        line_upper = line.upper()
        
        # Check if line contains any of the target error keywords
        matched_keyword = None
        for kw in ERROR_KEYWORDS:
            if kw in line_upper:
                matched_keyword = kw
                break
                
        if matched_keyword:
            # Extract context (up to 20 lines before and after)
            start_idx = max(0, i - 20)
            end_idx = min(total_lines, i + 21) # +21 because we want 20 lines AFTER the current line
            
            context_before = lines[start_idx:i]
            context_after = lines[i+1:end_idx]
            
            category = classify_error(line, context_before + context_after)
            
            # Update category counts
            category_counts[category] = category_counts.get(category, 0) + 1
            
            anomaly = {
                "line_number": i + 1, # 1-indexed line number
                "matched_keyword": matched_keyword,
                "line_text": line,
                "context_before": context_before,
                "context_after": context_after,
                "category": category
            }
            anomalies.append(anomaly)
            
    end_time = time.time()
    parse_duration_ms = (end_time - start_time) * 1000.0
    
    logger.info(f"Parsed {total_lines} lines, found {len(anomalies)} errors in {parse_duration_ms:.2f}ms")
    
    return {
        "total_lines": total_lines,
        "errors_found": len(anomalies),
        "anomalies": anomalies,
        "category_counts": category_counts,
        "parse_duration_ms": parse_duration_ms
    }
