"""
Database operations for LogSage AI.
Handles storing and retrieving incident reports and anomalies.
"""

import sqlite3
import json
import logging
import os
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("DB_PATH", "./data/logsage.db")

def init_db(db_path: str = None) -> None:
    """
    Initializes the database by executing the schema.sql file.

    Args:
        db_path (str): The path to the SQLite database file.
    """
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
    except FileNotFoundError:
        logger.error(f"Schema file not found at {schema_path}")
        raise

    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema_sql)
        conn.commit()
    logger.info(f"Database initialized at {db_path}")

def save_incident(report: Dict[str, Any], db_path: str = None) -> int:
    """
    Saves an incident and its associated anomalies to the database.

    Args:
        report (dict): The complete incident report dictionary.
        db_path (str): The path to the SQLite database file.

    Returns:
        int: The incident_id of the newly saved incident.
    """
    db_path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Insert incident
        cursor.execute(
            '''
            INSERT INTO incidents (
                log_filename, analysis_timestamp, total_lines, errors_found,
                max_severity, avg_severity, category_counts, severity_distribution,
                executive_summary, full_report
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                report.get("log_filename", "unknown"),
                report.get("analysis_timestamp", ""),
                report.get("total_lines", 0),
                report.get("errors_found", 0),
                report.get("max_severity", 0),
                report.get("avg_severity", 0.0),
                json.dumps(report.get("category_counts", {})),
                json.dumps(report.get("severity_distribution", {})),
                report.get("executive_summary", ""),
                json.dumps(report)
            )
        )
        incident_id = cursor.lastrowid
        
        # Insert anomalies
        anomalies = report.get("anomaly_analyses", [])
        for anomaly in anomalies:
            cursor.execute(
                '''
                INSERT INTO anomalies (
                    incident_id, line_number, matched_keyword, category,
                    severity_score, severity_label, root_cause,
                    remediation_steps, summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    incident_id,
                    anomaly.get("line_number"),
                    anomaly.get("matched_keyword"),
                    anomaly.get("category"),
                    anomaly.get("severity_score"),
                    anomaly.get("severity_label"),
                    anomaly.get("root_cause"),
                    json.dumps(anomaly.get("remediation_steps", [])),
                    anomaly.get("summary")
                )
            )
            
        conn.commit()
        logger.info(f"Saved incident {incident_id} with {len(anomalies)} anomalies")
        return incident_id

def get_incident_history(db_path: str = None) -> List[Dict[str, Any]]:
    """
    Retrieves the history of all incidents, ordered by creation date descending.

    Args:
        db_path (str): The path to the SQLite database file.

    Returns:
        list[dict]: A list of dictionary records representing incidents.
    """
    db_path = db_path or DEFAULT_DB_PATH
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT id, log_filename, analysis_timestamp, total_lines, errors_found,
                   max_severity, avg_severity, category_counts, severity_distribution,
                   executive_summary, created_at
            FROM incidents
            ORDER BY id DESC
            '''
        )
        rows = cursor.fetchall()
        
        history = []
        for row in rows:
            record = dict(row)
            record["category_counts"] = json.loads(record["category_counts"] or "{}")
            record["severity_distribution"] = json.loads(record["severity_distribution"] or "{}")
            history.append(record)
            
        return history

def get_incident_by_id(incident_id: int, db_path: str = None) -> Optional[Dict[str, Any]]:
    """
    Retrieves the full report dictionary for a given incident ID.

    Args:
        incident_id (int): The ID of the incident.
        db_path (str): The path to the SQLite database file.

    Returns:
        dict | None: The full report parsed from JSON, or None if not found.
    """
    db_path = db_path or DEFAULT_DB_PATH
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT full_report FROM incidents WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        
        if row and row["full_report"]:
            return json.loads(row["full_report"])
        return None

def delete_incident(incident_id: int, db_path: str = None) -> None:
    """
    Deletes an incident and its associated anomalies from the database.

    Args:
        incident_id (int): The ID of the incident to delete.
        db_path (str): The path to the SQLite database file.
    """
    db_path = db_path or DEFAULT_DB_PATH
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM anomalies WHERE incident_id = ?", (incident_id,))
        cursor.execute("DELETE FROM incidents WHERE id = ?", (incident_id,))
        conn.commit()
        logger.info(f"Deleted incident {incident_id}")
