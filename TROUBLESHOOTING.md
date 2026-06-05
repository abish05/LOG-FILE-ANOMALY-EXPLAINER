# LogSage AI Troubleshooting Guide

## Problem: "Ollama Offline" in sidebar
**Fix:**
*   **Local** → run `ollama serve` in a new terminal
*   **Docker** → run `docker compose logs ollama` to check startup errors
*   **VPS** → run `sudo systemctl restart ollama && sleep 5 && ollama list`

## Problem: llama3 model not found
**Fix:** 
Run `ollama pull llama3` (requires ~4.7GB disk space).
*   **On Docker:** `docker exec logsage_ollama ollama pull llama3`

## Problem: SQLite "unable to open database"
**Fix:**
*   Ensure the `data/` directory exists: `mkdir -p data`
*   Check that the `DB_PATH` environment variable points to a writable location.
*   **VPS:** `chown -R logsage:logsage /opt/logsage-ai/data`

## Problem: Streamlit page blank / 502 Bad Gateway (VPS)
**Fix:**
*   Check app status: `sudo systemctl status logsage`
*   View live logs: `sudo journalctl -u logsage -n 50`
*   Check Nginx config: `sudo nginx -t && sudo systemctl restart nginx`

## Problem: PDF generation fails
**Fix:**
*   Ensure you have the latest reportlab: `pip install reportlab --upgrade`
*   Check `REPORT_OUTPUT_DIR` is writable.
*   **On Docker:** the `/tmp` directory is always writable.

## Problem: GitHub Actions deploy fails
**Fix:**
*   Verify all 3 repository secrets are set correctly (`VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY`).
*   The SSH key must be the **PRIVATE** key, not the public one.
*   Test SSH connection manually: `ssh -i your_key logsage@your_ip`

## Problem: Port 8501 already in use
**Fix:**
*   Find the conflicting process: `lsof -i :8501 | grep LISTEN`
*   Kill it: `kill -9 <PID>`
*   Or change Streamlit port: `streamlit run app.py --server.port 8502`
