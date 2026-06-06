import pytest
from parser.log_parser import parse_log_file

@pytest.fixture
def sample_db_log():
    return """2024-01-01 10:00:00 INFO  App starting
2024-01-01 10:00:01 INFO  Connecting to postgres:5432
2024-01-01 10:00:02 ERROR connection refused to postgres:5432
2024-01-01 10:00:03 INFO  Retrying"""

@pytest.fixture
def sample_auth_log():
    return """2024-01-01 10:00:00 INFO  App starting
2024-01-01 10:00:01 FAILED login attempt for user admin - unauthorized
2024-01-01 10:00:02 INFO  Retrying"""

def test_empty_file_returns_zero_errors():
    result = parse_log_file("")
    assert result["errors_found"] == 0
    assert result["total_lines"] == 0

def test_parse_returns_correct_total_lines():
    content = "line1\nline2\nline3"
    result = parse_log_file(content)
    assert result["total_lines"] == 3

def test_detects_error_keyword():
    result = parse_log_file("2024-01-01 ERROR something went wrong")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "ERROR"

def test_detects_critical_keyword():
    result = parse_log_file("2024-01-01 CRITICAL system failure")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "CRITICAL"

def test_detects_fatal_keyword():
    result = parse_log_file("2024-01-01 FATAL disk full")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "FATAL"

def test_detects_exception_keyword():
    result = parse_log_file("2024-01-01 EXCEPTION NullPointerException")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "EXCEPTION"

def test_detects_failed_keyword():
    result = parse_log_file("2024-01-01 FAILED to bind port")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "FAILED"

def test_detects_timeout_keyword():
    result = parse_log_file("2024-01-01 TIMEOUT connection to gateway")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["matched_keyword"] == "TIMEOUT"

def test_context_window_is_max_20_lines():
    # Generate 50 lines of logs with an error at line 26
    lines = [f"line {i}" for i in range(1, 51)]
    lines[25] = "ERROR something failed"
    content = "\n".join(lines)
    result = parse_log_file(content)
    anomaly = result["anomalies"][0]
    
    assert len(anomaly["context_before"]) == 20
    assert len(anomaly["context_after"]) == 20
    assert anomaly["context_before"][0] == "line 6"
    assert anomaly["context_after"][-1] == "line 46"

def test_category_classification_database(sample_db_log):
    result = parse_log_file(sample_db_log)
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["category"] == "Database Error"

def test_category_classification_auth(sample_auth_log):
    result = parse_log_file(sample_auth_log)
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["category"] == "Authentication Error"

def test_category_classification_network():
    result = parse_log_file("2024-01-01 TIMEOUT network unreachable socket")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["category"] == "Network Error"

def test_category_classification_memory():
    result = parse_log_file("2024-01-01 FATAL out of memory heap")
    assert result["errors_found"] == 1
    assert result["anomalies"][0]["category"] == "Memory Error"
