-- Schema for LogSage AI incidents and anomalies
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_filename TEXT,
    analysis_timestamp TEXT,
    total_lines INTEGER,
    errors_found INTEGER,
    max_severity INTEGER,
    avg_severity REAL,
    category_counts TEXT,
    severity_distribution TEXT,
    executive_summary TEXT,
    full_report TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER,
    line_number INTEGER,
    matched_keyword TEXT,
    category TEXT,
    severity_score INTEGER,
    severity_label TEXT,
    root_cause TEXT,
    remediation_steps TEXT,
    summary TEXT,
    FOREIGN KEY (incident_id) REFERENCES incidents(id) ON DELETE CASCADE
);
