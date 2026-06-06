SHELL := /bin/bash
.PHONY: setup test run fmt

setup:
	bash scripts/setup_dev.sh

test:
	set -euo pipefail; . venv/bin/activate; python -m pytest tests/ -q

run:
	set -euo pipefail; . venv/bin/activate; streamlit run app.py
