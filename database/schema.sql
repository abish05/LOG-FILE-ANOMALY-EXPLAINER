CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    log_filename TEXT NOT NULL,
    analysis_timestamp TEXT NOT NULL,
    total_lines INTEGER,
    errors_found INTEGER,
    max_severity INTEGER,
    avg_severity REAL,
    category_counts TEXT,         -- JSON string
    severity_distribution TEXT,   -- JSON string
    executive_summary TEXT,
    full_report TEXT,             -- complete JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL,
    line_number INTEGER,
    matched_keyword TEXT,
    category TEXT,
    severity_score INTEGER,
    severity_label TEXT,
    root_cause TEXT,
    remediation_steps TEXT,       -- JSON string
    summary TEXT,
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);
