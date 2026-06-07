# LogSage AI

![status](https://img.shields.io/badge/status-ready-brightgreen)

LogSage AI is an AI-powered log file anomaly explainer that analyzes logs, identifies anomalies, and generates actionable remediation steps and executive summaries.

Quick Start (exactly 5 commands)
--------------------------------
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -c "from database.db import init_db; init_db()"
streamlit run app.py
```

Folder structure
----------------
```
LogSage-AI/
├─ agent/
├─ database/
├─ parser/
├─ reports/
├─ sample_logs/
├─ tests/
├─ docs/
└─ app.py
```

Features
--------
| Feature | Description |
|---|---|
| AI analysis | Per-anomaly LLM diagnosis and remediation |
| Streaming | Optional live token streaming of LLM output |
| Reports | PDF and CSV generation |
| Persistence | SQLite incident history |

Troubleshooting (5 common issues)
-------------------------------
1. Ollama not running — run `ollama serve` and `ollama pull llama3`.
2. Tests failing — ensure virtualenv activated and `pip install -r requirements.txt` succeeded.
3. PDF generation errors — ensure `reportlab` installed and `REPORT_OUTPUT_DIR` writable.
4. AI offline — set `HF_API_TOKEN` for cloud fallback.
5. Large logs time out — analyze smaller samples or increase timeouts.

Architecture — 7-step agent loop
--------------------------------
1. Read parsed data
2. Detect anomalies
3. Extract ±20 lines context
4. Analyze with LLM (per anomaly)
5. Classify severity
6. Generate executive summary
7. Assemble final report

Tech stack
----------
| Component | Technology |
|---|---|
| Frontend | Streamlit |
| AI | Ollama (local) / Hugging Face fallback |
| DB | SQLite |
| Reports | ReportLab |

Contributing
------------
Contributions welcome via pull requests. Please run tests before submitting.

License
-------
MIT
 
Team layout
-----------
We introduced a team-aligned layout to make parallel work easier. See `ARCHITECTURE.md` for full details. In short:

- UI/Frontend work: `frontend/` (note: Streamlit app implementation is under `backend/app.py`)
- Backend: `backend/` (DB, parser, reports, app implementation)
- AI engine: `ai_engine/` (agent, LLM clients, prompts)
- Deployment/infra: `deployment/` (scripts, Docker, CI manifests)

Backward compatibility: top-level shims keep `agent`, `database`, `parser`, and `reports` import paths working.
# LogSage AI — Incident Report Generator

LogSage AI is an intelligent log file analyzer designed to assist on-call engineers by automating the interpretation of production logs. It leverages local Large Language Models (Ollama) to pinpoint anomalies, identify root causes, calculate severities, and prescribe concrete remediation steps.

## Architecture

The system operates using a 7-step Agent Loop:
```
[ Log File ] --> 1. Read
                  |
                  v
             2. Detect Anomalies (Parser)
                  |
                  v
             3. Extract Context
                  |
                  v
             4. AI Analysis (Ollama llama3)
                  |
                  v
             5. Severity Scoring
                  |
                  v
             6. Exec Summary Gen
                  |
                  v
[ PDF/CSV ] <-- 7. Report Assembly --> [ SQLite DB ]
```

## Prerequisites

- Python 3.10+
- [Ollama](https://ollama.com/download) installed
- Git

## Quick Start (5 commands)

```bash
git clone <repo-url> && cd LogSage-AI
python -m venv venv && source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
ollama pull llama3
streamlit run app.py
```

## Running Tests

```bash
pytest tests/ -v --tb=short
```

## Troubleshooting

- **"Ollama Offline"**: Run `ollama serve` in a separate terminal before starting the app.
- **"llama3 not found"**: Run `ollama pull llama3`.
- **SQLite errors**: Delete the `logsage.db` file and restart the application; it will be recreated.
- **Port 8501 in use**: Run `streamlit run app.py --server.port 8502`.
