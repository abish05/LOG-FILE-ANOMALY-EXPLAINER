import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import json
from unittest.mock import patch
from ai_engine.agent.analyzer import run_agent_loop

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

# Patch call_llm + is_groq_available + is_ollama_available so tests always use LLM mode
@patch("ai_engine.agent.analyzer.is_ollama_available", return_value=False)
@patch("ai_engine.agent.analyzer.is_groq_available", return_value=True)
@patch("ai_engine.agent.analyzer.call_llm")
def test_run_agent_loop_returns_required_keys(mock_llm, mock_groq, mock_ollama, sample_parsed_data):
    mock_llm.side_effect = [
        json.dumps({"root_cause": "c1", "category": "Database Error", "severity_score": 8, "severity_label": "High", "remediation_steps": ["1"], "summary": "s1"}),
        json.dumps({"root_cause": "c2", "category": "Network Error", "severity_score": 5, "severity_label": "Medium", "remediation_steps": ["2"], "summary": "s2"}),
        "Executive summary here"
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

@patch("ai_engine.agent.analyzer.is_ollama_available", return_value=False)
@patch("ai_engine.agent.analyzer.is_groq_available", return_value=True)
@patch("ai_engine.agent.analyzer.call_llm")
def test_severity_distribution_calculation(mock_llm, mock_groq, mock_ollama, sample_parsed_data):
    mock_llm.side_effect = [
        json.dumps({"severity_score": 9}),   # Critical
        json.dumps({"severity_score": 5}),   # Medium
        "Executive summary"
    ]

    report = run_agent_loop(sample_parsed_data, "test.log")

    dist = report["severity_distribution"]
    assert dist["Critical"] == 1
    assert dist["High"] == 0
    assert dist["Medium"] == 1
    assert dist["Low"] == 0
    assert report["max_severity"] == 9
    assert report["avg_severity"] == 7.0

@patch("ai_engine.agent.analyzer.is_ollama_available", return_value=False)
@patch("ai_engine.agent.analyzer.is_groq_available", return_value=True)
@patch("ai_engine.agent.analyzer.call_llm")
def test_fallback_on_invalid_json_from_llm(mock_llm, mock_groq, mock_ollama, sample_parsed_data):
    """When LLM returns unparseable text, rule-based fallback is used for that anomaly."""
    mock_llm.side_effect = [
        "This is not JSON",                    # anomaly 1 → rule-based fallback
        json.dumps({"severity_score": 5}),     # anomaly 2 → parsed OK
        "Executive summary"
    ]

    report = run_agent_loop(sample_parsed_data, "test.log")

    anomaly1 = report["anomaly_analyses"][0]
    assert anomaly1["category"] == "Database Error"
    assert anomaly1["root_cause"] != ""
    assert 1 <= anomaly1["severity_score"] <= 10
    assert len(anomaly1["remediation_steps"]) >= 1

@patch("ai_engine.agent.analyzer.is_groq_available", return_value=False)
@patch("ai_engine.agent.analyzer.is_ollama_available", return_value=False)
def test_offline_mode_uses_rule_based_analysis(mock_ollama, mock_groq, sample_parsed_data):
    """When no LLM is available, analysis completes with rule-based results."""
    report = run_agent_loop(sample_parsed_data, "test.log")

    assert report["errors_found"] == 2
    assert report["analysis_mode"] == "rule-based"
    for anomaly in report["anomaly_analyses"]:
        assert 1 <= anomaly["severity_score"] <= 10
        assert len(anomaly["remediation_steps"]) >= 1
        assert anomaly["root_cause"] != ""

def test_agent_loop_raises_on_missing_anomalies_key():
    with pytest.raises(ValueError):
        run_agent_loop({}, "test.log")
