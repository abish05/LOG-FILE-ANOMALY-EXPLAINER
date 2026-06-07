# Architecture & Team Layout

This document explains the team-aligned repository layout introduced to make parallel work easier.

Top-level team folders

- `frontend` — UI-facing work. The Streamlit app entry remains runnable via the repo root `app.py` shim, but primary UI development should live under `backend` (see below) or a future `frontend` subpackage if the UI grows.
- `backend` — Backend application code and the Streamlit app implementation now live here: `backend/app.py`. Subpackages:
  - `backend/database` — DB init and access (`db.py`, `schema.sql`).
  - `backend/parser` — log parsing logic.
  - `backend/reports` — PDF/CSV report generation.
- `ai_engine` — AI engine and agent implementations. Replaces the old `agent` implementation location. Main code under `ai_engine/agent/` (LLM clients, prompts, analyzer).
- `deployment` — Deployment manifests and scripts (Docker, VPS scripts, CI/hosting manifests). Copies of root-level deploy files were placed here to centralize infra work.

Compatibility and shims

To avoid breaking existing workflows, lightweight shims remain at the original import paths:

- `agent/` shims re-export `ai_engine.agent` implementations.
- `database/db.py`, `parser/log_parser.py`, and `reports/report_generator.py` at the repo root re-export `backend.*` implementations.

How to run (unchanged)

- Run the app (same as before):

  ```bash
  streamlit run app.py
  ```

- Run tests:

  ```bash
  pytest -q
  ```

Developer notes

- Team owners:
  - Frontend engineers: collaborate on UI changes, but edit `backend/app.py` for the Streamlit app.
  - Backend engineers: work in `backend/*` for DB, parsing, and reports.
  - AI engineers: work in `ai_engine/agent/*` for LLM clients, prompts, and the analyzer.
  - Deployment: work in `deployment/` for infra, scripts, and manifests.
- If you plan to move root-level CI files into `deployment/`, run the full test suite and check CI configuration paths (some CI systems expect files in the repo root).

This layout keeps the public import surface stable while making team ownership explicit.
