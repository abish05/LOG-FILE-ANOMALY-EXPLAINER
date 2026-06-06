import os
import logging
from pathlib import Path

# pyrefly: ignore [missing-import]
import streamlit as st
# pyrefly: ignore [missing-import]
import plotly.graph_objects as go
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

from database.db import init_db, save_incident, get_incident_history, \
    get_incident_by_id, delete_incident
from parser.log_parser import parse_log_file
from agent.analyzer import run_agent_loop
from agent.ollama_client import is_ollama_available
from reports.report_generator import generate_pdf, generate_csv

st.set_page_config(
    page_title="LogSage AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── inject custom CSS ──────────────────────────────────────────────────────────
st.markdown("""<style>
#MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
[data-testid="stSidebar"]{background:#F1EFE8}
[data-testid="metric-container"]{background:#F1EFE8;border-radius:8px;padding:14px!important}
[data-testid="metric-container"] label{font-size:11px!important;text-transform:uppercase;letter-spacing:.06em;color:#888780!important}
[data-testid="stFileUploader"]{border:1.5px dashed rgba(0,0,0,.2)!important;border-radius:12px!important;background:#F1EFE8!important}
[data-testid="stExpander"]{border:0.5px solid rgba(0,0,0,.1)!important;border-radius:8px!important;overflow:hidden}
[data-testid="stExpander"] summary{background:#F1EFE8!important;font-size:13px!important;font-weight:500!important}
.stButton>button[kind="primary"]{background:#E24B4A!important;color:#fff!important;border:none!important;border-radius:8px!important;font-weight:500!important}
.stButton>button[kind="primary"]:hover{opacity:.88!important}
.stTabs [data-baseweb="tab"]{font-size:13px!important;font-weight:500!important}
.stTabs [aria-selected="true"]{color:#E24B4A!important;border-bottom-color:#E24B4A!important}
div[data-testid="stAlert"]{border-radius:8px!important;font-size:13px!important}
</style>""", unsafe_allow_html=True)

# ── init DB ────────────────────────────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    st.error(f"Database init failed: {e}")

# ── session state defaults ─────────────────────────────────────────────────────
if "last_report" not in st.session_state:
    st.session_state["last_report"] = None
if "ollama_status" not in st.session_state:
    st.session_state["ollama_status"] = is_ollama_available()

# ── sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔍 LogSage AI")
    st.caption("v3.2.1 — AI Log Analyzer")
    st.divider()
    page = st.radio(
        "Navigation",
        ["🏠 Analyze Logs", "📜 Incident History", "ℹ️ About"],
        label_visibility="collapsed"
    )
    st.divider()
    ollama_ok = st.session_state["ollama_status"]
    if ollama_ok:
        st.success("🟢 Ollama online")
    else:
        st.error("🔴 Ollama offline")
        st.caption("Run: `ollama serve`\nThen: `ollama pull llama3`")
    if st.button("↻ Refresh status", use_container_width=True):
        st.session_state["ollama_status"] = is_ollama_available()
        st.rerun()
    st.divider()
    model = st.selectbox(
        "Model", ["llama3", "llama3:8b", "mistral"], index=0
    )
    os.environ["MODEL_NAME"] = model or "llama3"  # guard: selectbox returns str | None

# ── severity helpers ───────────────────────────────────────────────────────────
def sev_badge(score: int) -> str:
    if score >= 9: return "🔴 Critical"
    elif score >= 7: return "🟠 High"
    elif score >= 4: return "🔵 Medium"
    return "🟢 Low"

def sev_color(score: int) -> str:
    if score >= 9: return "#A32D2D"
    elif score >= 7: return "#854F0B"
    elif score >= 4: return "#185FA5"
    return "#3B6D11"

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYZE LOGS
# ══════════════════════════════════════════════════════════════════════════════
if page == "🏠 Analyze Logs":
    st.title("Analyze log file")
    st.caption("Upload a .log or .txt file to begin AI-powered anomaly analysis")

    uploaded = st.file_uploader(
        "Drop your log file here",
        type=["log", "txt"],
        help="Max 200MB"
    )

    if uploaded:
        file_content = uploaded.read().decode("utf-8", errors="replace")
        st.success(
            f"**{uploaded.name}** — {len(file_content.splitlines())} lines "
            f"({round(len(file_content)/1024, 1)} KB)"
        )

        if st.button("🚀 Run AI Analysis", type="primary",
                     use_container_width=False):
            progress = st.progress(0, text="Starting analysis...")

            # Show offline warning before starting
            ollama_online = st.session_state.get("ollama_status", False)
            if not ollama_online:
                st.warning(
                    "⚡ **Offline mode** — Ollama is not running. "
                    "Using fast rule-based analysis (no LLM required). "
                    "Start Ollama locally for full AI-powered explanations."
                )

            try:
                progress.progress(10, text="Step 1 — Reading log file...")
                parsed = parse_log_file(file_content)

                progress.progress(20, text="Step 2 — Detecting anomalies...")
                if parsed["errors_found"] == 0:
                    st.info("No anomalies detected in this log file.")
                    progress.empty()
                    st.stop()

                def _on_progress(pct: int, msg: str) -> None:
                    """Callback wired into run_agent_loop for live progress."""
                    progress.progress(min(pct, 99), text=msg)

                report = run_agent_loop(
                    parsed, uploaded.name, progress_cb=_on_progress
                )
                incident_id = save_incident(report)
                report["_incident_id"] = incident_id
                st.session_state["last_report"] = report
                progress.progress(100, text="Done!")
                progress.empty()

                mode = report.get("analysis_mode", "llm")
                mode_label = "rule-based (Ollama offline)" if mode == "rule-based" else "AI (Ollama LLM)"
                st.success(
                    f"✅ Analysis complete — **{report['errors_found']} anomalies** found "
                    f"via {mode_label}. Incident saved (ID: {incident_id})"
                )
                st.rerun()
            except Exception as e:
                progress.empty()
                st.error(f"Analysis failed: {e}")
                logger.exception("Analysis error")

    report = st.session_state.get("last_report")
    if report:
        # Show analysis mode badge
        mode = report.get("analysis_mode", "llm")
        if mode == "rule-based":
            st.info(
                "⚡ This report was generated using **rule-based analysis** "
                "(Ollama was offline). Start Ollama and re-run for full AI explanations."
            )
        tab1, tab2, tab3 = st.tabs(
            ["📊 Dashboard", "🔍 Anomalies", "📄 Report"]
        )

        # ── DASHBOARD TAB ──────────────────────────────────────────────────────
        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total lines", report["total_lines"])
            c2.metric("Errors found", report["errors_found"])
            c3.metric("Max severity", f"{report['max_severity']}/10")
            c4.metric("Avg severity", report["avg_severity"])

            st.divider()
            col_a, col_b = st.columns(2)

            with col_a:
                cat = report.get("category_counts", {})
                if cat:
                    fig = go.Figure(go.Pie(
                        labels=list(cat.keys()),
                        values=list(cat.values()),
                        hole=0.45,
                        marker=dict(colors=[
                            "#E24B4A","#EF9F27","#378ADD",
                            "#639922","#7F77DD","#888780"
                        ])
                    ))
                    fig.update_layout(
                        title="Error categories",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=True,
                        height=320,
                        margin=dict(t=40,b=20,l=20,r=20),
                        font=dict(size=12)
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with col_b:
                sev = report.get("severity_distribution", {})
                if sev:
                    sev_colors = {
                        "Critical":"#E24B4A","High":"#EF9F27",
                        "Medium":"#378ADD","Low":"#639922"
                    }
                    fig2 = go.Figure(go.Bar(
                        x=list(sev.keys()),
                        y=list(sev.values()),
                        marker_color=[
                            sev_colors.get(k,"#888780")
                            for k in sev.keys()
                        ]
                    ))
                    fig2.update_layout(
                        title="Severity distribution",
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=320,
                        margin=dict(t=40,b=20,l=20,r=20),
                        yaxis=dict(
                            gridcolor="rgba(0,0,0,0.05)",
                            title="Count"
                        ),
                        font=dict(size=12)
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            st.divider()
            st.subheader("Executive summary")
            st.info(report.get("executive_summary", "N/A"))

        # ── ANOMALIES TAB ──────────────────────────────────────────────────────
        with tab2:
            analyses = report.get("anomaly_analyses", [])
            st.caption(
                f"{len(analyses)} anomalies — sorted by severity desc"
            )
            sorted_analyses = sorted(
                analyses,
                key=lambda x: x.get("severity_score", 0),
                reverse=True
            )
            for a in sorted_analyses:
                score = a.get("severity_score", 5)
                label = a.get("severity_label", "Medium")
                color = sev_color(score)
                header = (
                    f"{sev_badge(score)} &nbsp;|&nbsp; "
                    f"Line {a.get('line_number')} — "
                    f"**{a.get('matched_keyword')}** — "
                    f"{a.get('category')}"
                )
                with st.expander(
                    f"Line {a.get('line_number')} | "
                    f"{a.get('matched_keyword')} | "
                    f"{a.get('category')} | "
                    f"Severity {score}/10"
                ):
                    s1, s2 = st.columns([1, 3])
                    with s1:
                        st.markdown(
                            f"<span style='color:{color};font-weight:500;"
                            f"font-size:22px'>{score}/10</span><br>"
                            f"<span style='color:{color};font-size:12px'>"
                            f"{label}</span>",
                            unsafe_allow_html=True
                        )
                    with s2:
                        st.markdown(f"**Root cause:** {a.get('root_cause','N/A')}")
                        st.markdown(f"**Summary:** {a.get('summary','N/A')}")

                    st.markdown("**Remediation steps:**")
                    for j, step in enumerate(
                        a.get("remediation_steps", []), 1
                    ):
                        st.markdown(f"{j}. {step}")

                    st.markdown("**Log line:**")
                    st.code(a.get("line_text", ""), language="text")

                    ctx_before = a.get("context_before", [])
                    ctx_after = a.get("context_after", [])
                    if ctx_before or ctx_after:
                        with st.expander("View full context (±20 lines)"):
                            full_ctx = (
                                ctx_before
                                + [">>> " + a.get("line_text","")]
                                + ctx_after
                            )
                            st.code(
                                "\n".join(full_ctx),
                                language="text"
                            )

        # ── REPORT TAB ─────────────────────────────────────────────────────────
        with tab3:
            st.subheader("Download reports")
            col1, col2 = st.columns(2)

            with col1:
                if st.button("⬇️ Generate PDF", use_container_width=True):
                    with st.spinner("Generating PDF..."):
                        try:
                            pdf_path = generate_pdf(report)
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    "📄 Download PDF",
                                    f.read(),
                                    file_name=Path(pdf_path).name,
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"PDF generation failed: {e}")

            with col2:
                if st.button("⬇️ Generate CSV", use_container_width=True):
                    with st.spinner("Generating CSV..."):
                        try:
                            csv_path = generate_csv(report)
                            with open(csv_path, "rb") as f:
                                st.download_button(
                                    "📊 Download CSV",
                                    f.read(),
                                    file_name=Path(csv_path).name,
                                    mime="text/csv",
                                    use_container_width=True
                                )
                        except Exception as e:
                            st.error(f"CSV generation failed: {e}")

            st.divider()
            st.subheader("Raw report JSON")
            st.json(report, expanded=False)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INCIDENT HISTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📜 Incident History":
    st.title("Incident history")
    search = st.text_input(
        "Search by filename", placeholder="e.g. database_error"
    )
    history = get_incident_history()
    if search:
        history = [
            h for h in history
            if search.lower() in h.get("log_filename","").lower()
        ]
    if not history:
        st.info("No incidents analyzed yet. Upload a log file to begin.")
    else:
        st.caption(f"{len(history)} incidents found")
        for h in history:
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3,2,1,1,2])
                c1.markdown(f"**{h['log_filename']}**")
                c2.caption(h.get("analysis_timestamp","")[:16])
                c3.metric("Errors", h.get("errors_found",0))
                c4.metric("Max sev", h.get("max_severity",0))
                with c5:
                    b1, b2 = st.columns(2)
                    if b1.button("View", key=f"view_{h['id']}"):
                        full = get_incident_by_id(h["id"])
                        if full:
                            st.session_state["last_report"] = full
                            st.rerun()
                    if b2.button("🗑", key=f"del_{h['id']}"):
                        delete_incident(h["id"])
                        st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ABOUT
# ══════════════════════════════════════════════════════════════════════════════
elif page == "ℹ️ About":
    st.title("About LogSage AI")
    st.markdown("""
LogSage AI is an AI-powered log file anomaly explainer built for the
**Infinite Computer Solutions AI Prototype Challenge**.

### Tech stack
| Component | Technology |
|-----------|-----------|
| Frontend | Streamlit |
| Backend | Python 3.10+ |
| AI Engine | Ollama + Llama3 |
| Database | SQLite |
| Reports | ReportLab + CSV |
| Charts | Plotly |

### Agent workflow
The 7-step agent loop automatically:
1. Reads and validates the uploaded log
2. Detects anomalies using keyword matching
3. Extracts ±20 lines of context per error
4. Analyzes each anomaly using Llama3 via Ollama
5. Classifies severity on a 1–10 scale
6. Generates remediation recommendations
7. Produces a full incident report

### Team
Built in 1–2 days using only free and open source tools.
    """)
