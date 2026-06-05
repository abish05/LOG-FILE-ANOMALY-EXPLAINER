import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from parser.log_parser import parse_log_file, classify_error

def test_empty_file_returns_zero_errors():
    res = parse_log_file("")
    assert res["total_lines"] == 0
    assert res["errors_found"] == 0
    assert len(res["anomalies"]) == 0

def test_detects_error_keyword():
    res = parse_log_file("INFO line\nERROR something failed")
    assert res["errors_found"] == 1
    assert res["anomalies"][0]["matched_keyword"] == "ERROR"

def test_detects_critical_keyword():
    res = parse_log_file("CRITICAL node went down")
    assert res["errors_found"] == 1
    assert res["anomalies"][0]["matched_keyword"] == "CRITICAL"

def test_detects_exception_keyword():
    res = parse_log_file("EXCEPTION raised here")
    assert res["errors_found"] == 1
    assert res["anomalies"][0]["matched_keyword"] == "EXCEPTION"

def test_context_window_is_max_20_lines():
    # Create 50 lines
    lines = [f"INFO line {i}" for i in range(50)]
    lines[25] = "ERROR something bad"
    content = "\n".join(lines)
    
    res = parse_log_file(content)
    anomaly = res["anomalies"][0]
    
    assert len(anomaly["context_before"]) <= 20
    assert len(anomaly["context_after"]) <= 20
    assert anomaly["context_before"][0] == "INFO line 5"  # 25 - 20 = 5

def test_category_database_error_classification():
    assert classify_error("ERROR connection refused to postgres", []) == "Database Error"

def test_category_auth_error_classification():
    assert classify_error("FAILED login attempt 401", []) == "Authentication Error"

def test_category_network_error_classification():
    assert classify_error("TIMEOUT reaching api 502", []) == "Network Error"

def test_category_memory_error_classification():
    assert classify_error("FATAL out of memory heap space", []) == "Memory Error"

def test_category_api_error_classification():
    assert classify_error("ERROR endpoint 404 not found", []) == "API Error"

def test_category_unknown_error_fallback():
    assert classify_error("ERROR just a random glitch", []) == "Unknown Error"

def test_parse_returns_correct_total_lines():
    res = parse_log_file("1\n2\n3\n4\n5")
    assert res["total_lines"] == 5

def test_multiline_file_with_multiple_errors():
    content = "INFO 1\nERROR 1\nINFO 2\nTIMEOUT 1\nFATAL 1"
    res = parse_log_file(content)
    assert res["errors_found"] == 3
    keywords = [a["matched_keyword"] for a in res["anomalies"]]
    assert "ERROR" in keywords
    assert "TIMEOUT" in keywords
    assert "FATAL" in keywords
