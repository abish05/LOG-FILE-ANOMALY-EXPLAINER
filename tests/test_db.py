import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import sqlite3
from database.db import init_db, save_incident, get_incident_history, get_incident_by_id, delete_incident

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_logsage.db"
    db_path_str = str(db_file)
    init_db(db_path_str)
    return db_path_str

@pytest.fixture
def sample_report():
    return {
        "log_filename": "test.log",
        "analysis_timestamp": "2024-05-10T10:00:00Z",
        "total_lines": 100,
        "errors_found": 1,
        "max_severity": 8,
        "avg_severity": 8.0,
        "category_counts": {"Database Error": 1},
        "severity_distribution": {"High": 1},
        "executive_summary": "Test summary",
        "anomaly_analyses": [
            {
                "line_number": 10,
                "matched_keyword": "ERROR",
                "category": "Database Error",
                "severity_score": 8,
                "severity_label": "High",
                "root_cause": "Connection failed",
                "remediation_steps": ["Restart DB"],
                "summary": "DB is down"
            }
        ]
    }

def test_init_db_creates_tables(temp_db):
    assert os.path.exists(temp_db)
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        assert "incidents" in tables
        assert "anomalies" in tables

def test_save_and_retrieve_incident(temp_db, sample_report):
    incident_id = save_incident(sample_report, temp_db)
    assert incident_id == 1
    
    retrieved = get_incident_by_id(incident_id, temp_db)
    assert retrieved is not None
    assert retrieved["log_filename"] == "test.log"
    assert len(retrieved["anomaly_analyses"]) == 1

def test_get_history_returns_list(temp_db, sample_report):
    id1 = save_incident(sample_report, temp_db)
    sample_report["log_filename"] = "test2.log"
    id2 = save_incident(sample_report, temp_db)
    
    # Update created_at for id1 to be in the past to ensure deterministic DESC ordering by created_at
    with sqlite3.connect(temp_db) as conn:
        conn.execute("UPDATE incidents SET created_at = '2020-01-01 00:00:00' WHERE id = ?", (id1,))
        conn.commit()
    
    history = get_incident_history(temp_db)
    assert len(history) == 2
    # Ensure ordered DESC by created_at
    assert history[0]["log_filename"] == "test2.log"
    assert history[1]["log_filename"] == "test.log"

def test_delete_incident_removes_record(temp_db, sample_report):
    incident_id = save_incident(sample_report, temp_db)
    delete_incident(incident_id, temp_db)
    
    assert get_incident_by_id(incident_id, temp_db) is None
    
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM anomalies WHERE incident_id = ?", (incident_id,))
        count = cursor.fetchone()[0]
        assert count == 0

def test_get_incident_by_id_returns_none_for_missing(temp_db):
    assert get_incident_by_id(999, temp_db) is None
