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
