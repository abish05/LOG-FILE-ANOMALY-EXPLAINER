import re
import time
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

KEYWORDS = ["CRITICAL", "FATAL", "ERROR", "EXCEPTION", "FAILED", "TIMEOUT"]

# Compile once at module load — never re-compile on each call
_KEYWORD_PATTERN = re.compile(
    r'\b(CRITICAL|FATAL|ERROR|EXCEPTION|FAILED|TIMEOUT)\b',
    re.IGNORECASE
)

CATEGORY_RULES = [
    (["sql", "database", "db", "postgres", "mysql", "mongo",
      "connection refused", "5432", "3306", "ora-"], "Database Error"),
    (["auth", "login", "password", "token", "jwt", "oauth",
      "401", "403", "unauthorized", "forbidden", "credential"], "Authentication Error"),
    (["timeout", "connection", "network", "dns", "socket",
      "502", "503", "504", "unreachable", "refused", "gateway"], "Network Error"),
    (["memory", "heap", "oom", "out of memory", "gc overhead",
      "outofmemory", "malloc", "segfault", "stack overflow"], "Memory Error"),
    (["api", "endpoint", "request", "response", "http", "rest",
      "graphql", "webhook", "404", "500", "rate limit"], "API Error"),
]


def classify_error(line_text: str, context: List[str]) -> str:
    """Classify error into one of 6 categories using keyword rules."""
    combined = (line_text + " ".join(context)).lower()
    for keywords, category in CATEGORY_RULES:
        if any(kw in combined for kw in keywords):
            return category
    return "Unknown Error"


def parse_log_file(file_content: str) -> Dict[str, Any]:
    """
    Parse log file content and extract anomalies.

    Returns:
        dict with keys: total_lines, errors_found, anomalies,
        category_counts, parse_duration_ms
    """
    start = time.perf_counter()  # perf_counter is more precise than time.time()
    lines = file_content.splitlines()
    total_lines = len(lines)
    anomalies: List[Dict[str, Any]] = []

    for i, line in enumerate(lines):
        match = _KEYWORD_PATTERN.search(line)
        if match:
            keyword = match.group(1).upper()
            before_start = max(0, i - 20)
            after_end = min(total_lines, i + 21)
            context_before = lines[before_start:i]
            context_after = lines[i + 1:after_end]
            category = classify_error(line, context_before + context_after)
            anomalies.append({
                "line_number": i + 1,
                "matched_keyword": keyword,
                "line_text": line.strip(),
                "context_before": context_before,
                "context_after": context_after,
                "category": category,
            })

    category_counts: Dict[str, int] = {}
    for a in anomalies:
        cat = a["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    logger.info(
        f"Parsed {total_lines} lines, found {len(anomalies)} anomalies "
        f"in {duration_ms}ms"
    )
    return {
        "total_lines": total_lines,
        "errors_found": len(anomalies),
        "anomalies": anomalies,
        "category_counts": category_counts,
        "parse_duration_ms": duration_ms,
    }
