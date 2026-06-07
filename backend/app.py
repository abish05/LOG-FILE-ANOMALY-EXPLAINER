import os
import logging
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)

from backend.database.db import (
    init_db, save_incident, get_incident_history,
    get_incident_by_id, delete_incident,
)
from backend.parser.log_parser import parse_log_file
from ai_engine.agent.analyzer import run_agent_loop
from ai_engine.agent.ollama_client import is_ollama_available
from ai_engine.agent.llm_client import get_ai_status
from backend.reports.report_generator import generate_pdf, generate_csv

# ── page config ────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="LogSage AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom dark theme CSS ──────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── base ──────────────────────────────────────────────────────────────────── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
.main {
    background-color: #0f1117 !important;
    color: #e2e8f0 !important;
}
[data-testid="stHeader"] { background: transparent !important; }

/* ── sidebar ────────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1d27 0%, #161923 100%) !important;
    border-right: 1px solid #2d3748 !important;
}
[data-testid="stSidebar"] * { color: #cbd5e0 !important; }
[data-testid="stSidebar"] .stRadio label { font-size: 14px !important; }

/* ── block container ─────────────────────────────────────────────────────────── */
.main .block-container {
    padding: 1.5rem 2rem !important;
    max-width: 1400px !important;
}

/* ── headings ────────────────────────────────────────────────────────────────── */
h1, h2, h3, h4 { color: #f7fafc !important; font-weight: 700 !important; }
h1 { font-size: 2rem !important; letter-spacing: -0.5px; }

/* ── metric cards ────────────────────────────────────────────────────────────── */
[data-testid="metric-container"] {
    background: linear-gradient(135deg, #1e2433 0%, #252d3d 100%) !important;
    border: 1px solid #2d3748 !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
    transition: border-color .2s;
}
[data-testid="metric-container"]:hover { border-color: #e24b4a !important; }
[data-testid="metric-container"] label {
    font-size: 11px !important;
    text-transform: uppercase;
    letter-spacing: .07em;
    color: #718096 !important;
}
[data-testid="metric-container"] [data-testid="stMetricValue"] {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #f7fafc !important;
}

/* ── file uploader ───────────────────────────────────────────────────────────── */
[data-testid="stFileUploader"] {
    border: 2px dashed #3d4a5c !important;
    border-radius: 16px !important;
    background: #1a1d27 !important;
    padding: 2.5rem !important;
    transition: border-color .2s;
}
[data-testid="stFileUploader"]:hover { border-color: #e24b4a !important; }
[data-testid="stFileUploader"] label,
[data-testid="stFileUploader"] span { color: #718096 !important; }

/* ── tabs ────────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #1a1d27 !important;
    border-radius: 10px 10px 0 0 !important;
    padding: 4px 8px 0 !important;
    gap: 4px;
    border-bottom: 2px solid #2d3748 !important;
}
.stTabs [data-baseweb="tab"] {
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #718096 !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 18px !important;
}
.stTabs [aria-selected="true"] {
    color: #e24b4a !important;
    background: #252d3d !important;
    border-bottom: 2px solid #e24b4a !important;
}

/* ── expanders ───────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #2d3748 !important;
    border-radius: 10px !important;
    background: #1a1d27 !important;
    margin-bottom: 8px !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary {
    background: #1e2433 !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: #e2e8f0 !important;
    padding: 10px 16px !important;
}
[data-testid="stExpander"] summary:hover { background: #252d3d !important; }

/* ── buttons ─────────────────────────────────────────────────────────────────── */
.stButton > button {
    background: #1e2433 !important;
    color: #cbd5e0 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: all .2s !important;
}
.stButton > button:hover {
    background: #252d3d !important;
    border-color: #4a5568 !important;
    color: #f7fafc !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #e24b4a, #c0392b) !important;
    color: #fff !important;
    border: none !important;
    box-shadow: 0 4px 14px rgba(226,75,74,.35) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #c0392b, #a93226) !important;
    box-shadow: 0 4px 20px rgba(226,75,74,.5) !important;
    transform: translateY(-1px) !important;
}

/* ── alerts ──────────────────────────────────────────────────────────────────── */
.stSuccess, .stInfo, .stWarning, .stError {
    border-radius: 10px !important;
}
[data-testid="stNotificationContentSuccess"] {
    background: rgba(39,174,96,.12) !important;
    border-left: 4px solid #27ae60 !important;
    color: #a3e4bc !important;
}
[data-testid="stNotificationContentInfo"] {
    background: rgba(55,138,221,.12) !important;
    border-left: 4px solid #378add !important;
    color: #90c8f8 !important;
}
[data-testid="stNotificationContentWarning"] {
    background: rgba(239,159,39,.12) !important;
    border-left: 4px solid #ef9f27 !important;
    color: #fbd38d !important;
}
[data-testid="stNotificationContentError"] {
    background: rgba(226,75,74,.12) !important;
    border-left: 4px solid #e24b4a !important;
    color: #feb2b2 !important;
}

/* ── inputs ──────────────────────────────────────────────────────────────────── */
input, textarea,
[data-testid="stTextInput"] input,
[data-baseweb="input"] input {
    background: #1a1d27 !important;
    color: #e2e8f0 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
}
input:focus, textarea:focus {
    border-color: #e24b4a !important;
    box-shadow: 0 0 0 2px rgba(226,75,74,.2) !important;
}
input::placeholder { color: #4a5568 !important; }

/* ── selectbox ───────────────────────────────────────────────────────────────── */
[data-baseweb="select"] > div:first-child {
    background: #1a1d27 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
    color: #e2e8f0 !important;
}

/* ── code blocks ─────────────────────────────────────────────────────────────── */
pre, code {
    background: #131720 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px !important;
    color: #a8d8a8 !important;
}

/* ── dividers ────────────────────────────────────────────────────────────────── */
hr, [data-testid="stDivider"] { border-color: #2d3748 !important; }

/* ── containers (border) ─────────────────────────────────────────────────────── */
[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid #2d3748 !important;
    border-radius: 12px !important;
    background: #1a1d27 !important;
    padding: 12px !important;
}

/* ── progress bar ────────────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div {
    background: linear-gradient(90deg, #e24b4a, #ff6b6b) !important;
    border-radius: 4px !important;
}

/* ── scrollbars ──────────────────────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #1a1d27; }
::-webkit-scrollbar-thumb { background: #3d4a5c; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #4a5568; }

/* ── caption / small text ────────────────────────────────────────────────────── */
.stCaption, [data-testid="stCaptionContainer"] { color: #718096 !important; }

/* ── logo area ───────────────────────────────────────────────────────────────── */
.logo-title {
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    color: #f7fafc;
}
.logo-badge {
    display: inline-block;
    background: linear-gradient(135deg, #e24b4a, #c0392b);
    color: white;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 7px;
    border-radius: 10px;
    letter-spacing: .06em;
    vertical-align: middle;
    margin-left: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── init DB ────────────────────────────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    st.error(f"Database init failed: {e}")

# ── session state defaults ─────────────────────────────────────────────────────
for key, default in [
    ("last_report", None),
    ("ollama_status", None),
]:
    if key not in st.session_state:
        st.session_state[key] = default

if st.session_state["ollama_status"] is None:
    st.session_state["ollama_status"] = is_ollama_available()

# ── sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="logo-title">🔍 LogSage AI<span class="logo-badge">v3</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("AI-powered log anomaly analysis")
    st.divider()

    page = st.radio(
        "Navigation",
        ["🔬 Analyze logs", "📋 Incident history", "📊 Analytics", "📄 Reports", "⚙️ Settings"],
        label_visibility="collapsed",
    )
    st.divider()

    # AI status
    ai = get_ai_status()
    provider = ai["provider"]
    if provider in ("Groq", "Ollama"):
        st.success(f"🟢 {provider} online")
        st.caption(f"Model: `{ai['model']}`")
    else:
        st.info("🔵 Rule-based mode")
        st.caption("Set `GROQ_API_KEY` for full AI analysis")

    if st.button("↻ Refresh status", use_container_width=True):
        st.session_state["ollama_status"] = None
        st.rerun()

    st.divider()
    model = st.selectbox("Model", ["llama3", "llama3:8b", "mistral"], index=0)
    os.environ["MODEL_NAME"] = model or "llama3"

# ── helpers ────────────────────────────────────────────────────────────────────
def sev_badge(score: int) -> str:
    if score >= 9: return "🔴 Critical"
    elif score >= 7: return "🟠 High"
    elif score >= 4: return "🔵 Medium"
    return "🟢 Low"

def sev_color(score: int) -> str:
    if score >= 9: return "#fc8181"
    elif score >= 7: return "#f6ad55"
    elif score >= 4: return "#63b3ed"
    return "# 68d391"

def _sev_color(score: int) -> str:
    if score >= 9: return "#fc8181"
    elif score >= 7: return "#f6ad55"
    elif score >= 4: return "#63b3ed"
    return "#68d391"

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: ANALYZE LOGS
# ══════════════════════════════════════════════════════════════════════════════
if page == "🔬 Analyze logs":
    st.title("Analyze Log File")
    st.caption("Upload a `.log` or `.txt` file for AI-powered anomaly detection and root-cause analysis.")

    uploaded = st.file_uploader(
        "Drop your log file here, or click to browse",
        type=["log", "txt"],
        help="Max file size: 200 MB",
    )

    if uploaded:
        file_content = uploaded.read().decode("utf-8", errors="replace")
        line_count = len(file_content.splitlines())
        kb_size = round(len(file_content) / 1024, 1)
        st.success(f"📂 **{uploaded.name}** loaded — {line_count:,} lines · {kb_size} KB")

        if st.button("🚀 Run AI Analysis", type="primary", use_container_width=True):
            progress = st.progress(0, text="Initialising analysis engine...")

            if not st.session_state.get("ollama_status"):
                st.warning(
                    "⚡ **Offline mode** — No local LLM detected. "
                    "Using fast rule-based analysis. Set `GROQ_API_KEY` for full AI insights."
                )

            try:
                progress.progress(10, text="Parsing log file...")
                parsed = parse_log_file(file_content)

                if parsed["errors_found"] == 0:
                    progress.empty()
                    st.info("✅ No anomalies detected in this log file — everything looks clean!")
                    st.stop()

                def _on_progress(pct: int, msg: str) -> None:
                    progress.progress(min(pct, 99), text=msg)

                report = run_agent_loop(parsed, uploaded.name, progress_cb=_on_progress)
                incident_id = save_incident(report)
                report["_incident_id"] = incident_id
                st.session_state["last_report"] = report
                progress.progress(100, text="Done!")
                progress.empty()

                mode = report.get("analysis_mode", "rule-based")
                mode_labels = {
                    "groq": "Groq AI (llama-3.1-8b-instant)",
                    "ollama": "Ollama (local LLM)",
                }
                mode_label = mode_labels.get(mode, "rule-based analysis")
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
        mode = report.get("analysis_mode", "rule-based")
        if mode == "rule-based":
            st.info("🔵 Report generated via **rule-based analysis**. Add `GROQ_API_KEY` for full AI explanations.")
        elif mode == "groq":
            st.success("🟢 Report generated by **Groq AI** (llama-3.1-8b-instant).")

        tab1, tab2, tab3 = st.tabs(["📊 Dashboard", "🔍 Anomalies", "📄 Export"])

        # ── DASHBOARD ─────────────────────────────────────────────────────────
        with tab1:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Total Lines", f"{report['total_lines']:,}")
            c2.metric("Anomalies Found", report["errors_found"])
            c3.metric("Max Severity", f"{report['max_severity']}/10")
            c4.metric("Avg Severity", f"{report['avg_severity']}/10")

            st.divider()
            col_a, col_b = st.columns(2)

            with col_a:
                cat = report.get("category_counts", {})
                if cat:
                    fig = go.Figure(go.Pie(
                        labels=list(cat.keys()),
                        values=list(cat.values()),
                        hole=0.48,
                        marker=dict(colors=[
                            "#e24b4a", "#ef9f27", "#378add",
                            "#27ae60", "#9b59b6", "#718096"
                        ]),
                        textfont=dict(color="#e2e8f0", size=12),
                    ))
                    fig.update_layout(
                        title=dict(text="Error Categories", font=dict(color="#e2e8f0", size=15)),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        showlegend=True,
                        legend=dict(font=dict(color="#a0aec0"), bgcolor="rgba(0,0,0,0)"),
                        height=320,
                        margin=dict(t=50, b=20, l=10, r=10),
                    )
                    st.plotly_chart(fig, use_container_width=True)

            with col_b:
                sev = report.get("severity_distribution", {})
                if sev:
                    sev_colors_map = {
                        "Critical": "#fc8181", "High": "#f6ad55",
                        "Medium": "#63b3ed", "Low": "#68d391",
                    }
                    fig2 = go.Figure(go.Bar(
                        x=list(sev.keys()),
                        y=list(sev.values()),
                        marker_color=[sev_colors_map.get(k, "#718096") for k in sev.keys()],
                        marker_line_width=0,
                        text=list(sev.values()),
                        textposition="outside",
                        textfont=dict(color="#e2e8f0"),
                    ))
                    fig2.update_layout(
                        title=dict(text="Severity Distribution", font=dict(color="#e2e8f0", size=15)),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        height=320,
                        margin=dict(t=50, b=20, l=10, r=10),
                        xaxis=dict(
                            tickfont=dict(color="#a0aec0"),
                            gridcolor="rgba(255,255,255,0.05)",
                        ),
                        yaxis=dict(
                            tickfont=dict(color="#a0aec0"),
                            gridcolor="rgba(255,255,255,0.05)",
                            title=dict(text="Count", font=dict(color="#718096")),
                        ),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

            st.divider()
            st.subheader("Executive Summary")
            st.info(report.get("executive_summary", "N/A"))

        # ── ANOMALIES ──────────────────────────────────────────────────────────
        with tab2:
            analyses = report.get("anomaly_analyses", [])
            st.caption(f"{len(analyses)} anomalies · sorted by severity (highest first)")
            sorted_analyses = sorted(
                analyses,
                key=lambda x: x.get("severity_score", 0),
                reverse=True,
            )
            for a in sorted_analyses:
                score = a.get("severity_score", 5)
                label = a.get("severity_label", "Medium")
                color = _sev_color(score)
                with st.expander(
                    f"{sev_badge(score)}  ·  Line {a.get('line_number')}  ·  "
                    f"{a.get('matched_keyword')}  ·  {a.get('category')}  ·  {score}/10"
                ):
                    s1, s2 = st.columns([1, 4])
                    with s1:
                        st.markdown(
                            f"<div style='text-align:center'>"
                            f"<span style='color:{color};font-weight:800;font-size:32px'>{score}</span>"
                            f"<span style='color:#718096;font-size:14px'>/10</span><br>"
                            f"<span style='color:{color};font-size:12px;font-weight:600'>{label}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    with s2:
                        st.markdown(f"**Root Cause:** {a.get('root_cause', 'N/A')}")
                        st.markdown(f"**Summary:** {a.get('summary', 'N/A')}")

                    st.markdown("**Remediation Steps:**")
                    for j, step in enumerate(a.get("remediation_steps", []), 1):
                        st.markdown(f"{j}. {step}")

                    st.markdown("**Log Line:**")
                    st.code(a.get("line_text", ""), language="text")

                    ctx_before = a.get("context_before", [])
                    ctx_after = a.get("context_after", [])
                    if ctx_before or ctx_after:
                        with st.expander("📎 View context (±20 lines)"):
                            full_ctx = (
                                ctx_before
                                + [">>> " + a.get("line_text", "")]
                                + ctx_after
                            )
                            st.code("\n".join(full_ctx), language="text")

        # ── EXPORT ────────────────────────────────────────────────────────────
        with tab3:
            st.subheader("Download Report")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬇️ Generate PDF", use_container_width=True):
                    with st.spinner("Building PDF..."):
                        try:
                            pdf_path = generate_pdf(report)
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    "📄 Download PDF",
                                    f.read(),
                                    file_name=Path(pdf_path).name,
                                    mime="application/pdf",
                                    use_container_width=True,
                                )
                        except Exception as e:
                            st.error(f"PDF generation failed: {e}")

            with col2:
                if st.button("⬇️ Generate CSV", use_container_width=True):
                    with st.spinner("Building CSV..."):
                        try:
                            csv_path = generate_csv(report)
                            with open(csv_path, "rb") as f:
                                st.download_button(
                                    "📊 Download CSV",
                                    f.read(),
                                    file_name=Path(csv_path).name,
                                    mime="text/csv",
                                    use_container_width=True,
                                )
                        except Exception as e:
                            st.error(f"CSV generation failed: {e}")

            st.divider()
            st.subheader("Raw JSON Report")
            st.json(report, expanded=False)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: INCIDENT HISTORY
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📋 Incident history":
    st.title("Incident History")
    search = st.text_input("🔎 Search by filename", placeholder="e.g. database_error")
    history = get_incident_history()
    if search:
        history = [h for h in history if search.lower() in h.get("log_filename", "").lower()]

    if not history:
        st.info("No incidents yet. Upload a log file on the **Analyze logs** page to get started.")
    else:
        st.caption(f"{len(history)} incident{'s' if len(history) != 1 else ''} found")
        for h in history:
            with st.container(border=True):
                c1, c2, c3, c4, c5 = st.columns([3, 2, 1, 1, 2])
                c1.markdown(f"**{h['log_filename']}**")
                c2.caption(str(h.get("analysis_timestamp", ""))[:16])
                c3.metric("Errors", h.get("errors_found", 0))
                c4.metric("Max Sev", h.get("max_severity", 0))
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
# PAGE: ANALYTICS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Analytics":
    st.title("Analytics")
    history = get_incident_history()
    if not history:
        st.info("No data yet. Analyze some log files to see analytics here.")
    else:
        total_incidents = len(history)
        total_errors = sum(h.get("errors_found", 0) for h in history)
        avg_max_sev = round(
            sum(h.get("max_severity", 0) for h in history) / total_incidents, 1
        )
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Incidents", total_incidents)
        c2.metric("Total Errors Found", total_errors)
        c3.metric("Avg Max Severity", f"{avg_max_sev}/10")

        st.divider()
        # Errors over time
        timestamps = [str(h.get("analysis_timestamp", ""))[:10] for h in history]
        errors = [h.get("errors_found", 0) for h in history]
        fig = go.Figure(go.Scatter(
            x=timestamps, y=errors,
            mode="lines+markers",
            line=dict(color="#e24b4a", width=2),
            marker=dict(color="#e24b4a", size=7),
            fill="tozeroy",
            fillcolor="rgba(226,75,74,0.1)",
        ))
        fig.update_layout(
            title=dict(text="Errors Found per Incident", font=dict(color="#e2e8f0", size=15)),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(tickfont=dict(color="#a0aec0"), gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(tickfont=dict(color="#a0aec0"), gridcolor="rgba(255,255,255,0.05)"),
            height=300,
            margin=dict(t=50, b=20, l=10, r=10),
        )
        st.plotly_chart(fig, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: REPORTS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📄 Reports":
    st.title("Reports")
    report = st.session_state.get("last_report")
    if not report:
        st.info("No report loaded. Analyze a log file first, or load one from **Incident history**.")
    else:
        st.caption(f"Current report: **{report.get('log_filename', 'N/A')}**")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("⬇️ Generate PDF", use_container_width=True):
                with st.spinner("Building PDF..."):
                    try:
                        pdf_path = generate_pdf(report)
                        with open(pdf_path, "rb") as f:
                            st.download_button(
                                "📄 Download PDF",
                                f.read(),
                                file_name=Path(pdf_path).name,
                                mime="application/pdf",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error(f"PDF generation failed: {e}")
        with col2:
            if st.button("⬇️ Generate CSV", use_container_width=True):
                with st.spinner("Building CSV..."):
                    try:
                        csv_path = generate_csv(report)
                        with open(csv_path, "rb") as f:
                            st.download_button(
                                "📊 Download CSV",
                                f.read(),
                                file_name=Path(csv_path).name,
                                mime="text/csv",
                                use_container_width=True,
                            )
                    except Exception as e:
                        st.error(f"CSV generation failed: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# PAGE: SETTINGS
# ══════════════════════════════════════════════════════════════════════════════
elif page == "⚙️ Settings":
    st.title("Settings")
    st.subheader("AI Provider")
    ai = get_ai_status()
    st.json(ai, expanded=True)

    st.divider()
    st.subheader("Environment")
    groq_key = os.getenv("GROQ_API_KEY", "")
    st.markdown(f"**GROQ_API_KEY:** `{'✅ Set' if groq_key else '❌ Not set'}`")
    st.markdown(f"**GROQ_MODEL:** `{os.getenv('GROQ_MODEL', 'llama-3.1-8b-instant')}`")
    st.markdown(f"**OLLAMA_HOST:** `{os.getenv('OLLAMA_HOST', 'http://localhost:11434')}`")
    st.markdown(f"**DB_PATH:** `{os.getenv('DB_PATH', './data/logsage.db')}`")

    st.divider()
    st.subheader("Sample Logs")
    st.caption("Download a sample log file to test the analyzer:")
    sample_dir = Path(__file__).parent.parent / "sample_logs"
    if sample_dir.exists():
        for f in sorted(sample_dir.glob("*.log")):
            st.download_button(
                f"📥 {f.name}",
                f.read_bytes(),
                file_name=f.name,
                mime="text/plain",
                use_container_width=True,
                key=f"sample_{f.name}",
            )
    else:
        st.info("No sample logs found.")
