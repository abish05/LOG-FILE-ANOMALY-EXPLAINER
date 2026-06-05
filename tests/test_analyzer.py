import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from unittest.mock import patch
from agent.analyzer import run_agent_loop

@pytest.fixture
def sample_parsed_data():
    return {
        "total_lines": 100,
        "errors_found": 2,
        "anomalies": [
            {
                "line_number": 10,
                "matched_keyword": "ERROR",
                "line_text": "ERROR db connection refused",
                "context_before": [],
                "context_after": [],
                "category": "Database Error"
            },
            {
                "line_number": 20,
                "matched_keyword": "CRITICAL",
                "line_text": "CRITICAL service timeout",
                "context_before": [],
                "context_after": [],
                "category": "Network Error"
            }
        ],
        "category_counts": {"Database Error": 1, "Network Error": 1}
    }

@patch("agent.analyzer.call_ollama")
def test_run_agent_loop_returns_required_keys(mock_call_ollama, sample_parsed_data):
    mock_call_ollama.side_effect = [
        json.dumps({"root_cause": "c1", "category": "Database Error", "severity_score": 8, "severity_label": "High", "remediation_steps": ["1"], "summary": "s1"}),
        json.dumps({"root_cause": "c2", "category": "Network Error", "severity_score": 5, "severity_label": "Medium", "remediation_steps": ["2"], "summary": "s2"}),
        "Exec summary here"
    ]
    
    report = run_agent_loop(sample_parsed_data, "test.log")
    
    assert "log_filename" in report
    assert "analysis_timestamp" in report
    assert "total_lines" in report
    assert "errors_found" in report
    assert "category_counts" in report
    assert "severity_distribution" in report
    assert "max_severity" in report
    assert "avg_severity" in report
    assert "anomaly_analyses" in report
    assert "executive_summary" in report
    assert "agent_steps_completed" in report

@patch("agent.analyzer.call_ollama")
def test_severity_distribution_calculation(mock_call_ollama, sample_parsed_data):
    mock_call_ollama.side_effect = [
        json.dumps({"severity_score": 9}), # Critical
        json.dumps({"severity_score": 5}), # Medium
        "Exec summary"
    ]
    
    report = run_agent_loop(sample_parsed_data, "test.log")
    
    dist = report["severity_distribution"]
    assert dist["Critical"] == 1
    assert dist["High"] == 0
    assert dist["Medium"] == 1
    assert dist["Low"] == 0
    
    assert report["max_severity"] == 9
    assert report["avg_severity"] == 7.0

@patch("agent.analyzer.call_ollama")
def test_fallback_on_invalid_json_from_llm(mock_call_ollama, sample_parsed_data):
    # Pass an invalid JSON string
    mock_call_ollama.side_effect = [
        "This is not JSON",
        json.dumps({"severity_score": 5}),
        "Exec summary"
    ]
    
    report = run_agent_loop(sample_parsed_data, "test.log")
    
    # First anomaly should use fallback
    anomaly1 = report["anomaly_analyses"][0]
    assert anomaly1["severity_score"] == 5
    assert anomaly1["category"] == "Unknown Error"
    assert "AI parse error" in anomaly1["root_cause"]

def test_agent_loop_raises_on_missing_anomalies_key():
    with pytest.raises(ValueError):
        run_agent_loop({}, "test.log")
