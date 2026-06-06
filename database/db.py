import sqlite3
import json
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv("DB_PATH", "./data/logsage.db")

def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Initialize SQLite database using schema.sql."""
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    schema_path = Path(__file__).parent / "schema.sql"
    with open(schema_path, "r") as f:
        schema = f.read()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(schema)
        conn.commit()
    logger.info(f"Database initialized at {db_path}")

def save_incident(report: dict, db_path: str = DEFAULT_DB_PATH) -> int:
    """Save full incident report. Returns incident_id."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO incidents
            (log_filename, analysis_timestamp, total_lines, errors_found,
             max_severity, avg_severity, category_counts,
             severity_distribution, executive_summary, full_report)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
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
        ))
        incident_id = cursor.lastrowid or 0  # lastrowid is int|None; always set after INSERT
        for anomaly in report.get("anomaly_analyses", []):
            cursor.execute("""
                INSERT INTO anomalies
                (incident_id, line_number, matched_keyword, category,
                 severity_score, severity_label, root_cause,
                 remediation_steps, summary)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (
                incident_id,
                anomaly.get("line_number", 0),
                anomaly.get("matched_keyword", ""),
                anomaly.get("category", "Unknown Error"),
                anomaly.get("severity_score", 5),
                anomaly.get("severity_label", "Medium"),
                anomaly.get("root_cause", ""),
                json.dumps(anomaly.get("remediation_steps", [])),
                anomaly.get("summary", "")
            ))
        conn.commit()
    logger.info(f"Saved incident_id={incident_id}")
    return incident_id

def get_incident_history(db_path: str = DEFAULT_DB_PATH) -> list:
    """Return all incidents ordered by created_at DESC."""
    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, log_filename, analysis_timestamp,
                       total_lines, errors_found, max_severity,
                       avg_severity, category_counts, executive_summary,
                       created_at
                FROM incidents ORDER BY created_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"get_incident_history error: {e}")
        return []

def get_incident_by_id(incident_id: int,
                       db_path: str = DEFAULT_DB_PATH) -> dict | None:
    """Return full_report JSON for one incident."""
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT full_report FROM incidents WHERE id=?",
                (incident_id,)
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row[0])
            return None
    except Exception as e:
        logger.error(f"get_incident_by_id error: {e}")
        return None

def delete_incident(incident_id: int,
                    db_path: str = DEFAULT_DB_PATH) -> None:
    """Delete incident and its anomalies (CASCADE)."""
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "DELETE FROM incidents WHERE id=?", (incident_id,)
        )
        conn.commit()
    logger.info(f"Deleted incident_id={incident_id}")
