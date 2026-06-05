"""
Streamlit frontend for LogSage AI.
Provides UI for log upload, incident history, and report downloads.
"""

# pyrefly: ignore [missing-import]
import streamlit as st
import os
import json
import tempfile
# pyrefly: ignore [missing-import]
import plotly.graph_objects as go
from datetime import datetime
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

from database.db import init_db, save_incident, get_incident_history, get_incident_by_id, delete_incident
from parser.log_parser import parse_log_file
from agent.analyzer import run_agent_loop
from agent.ollama_client import is_ollama_available
from reports.report_generator import generate_pdf, generate_csv

# Load env variables
load_dotenv()

# Initialize DB at module level
try:
    init_db()
except Exception as e:
    st.error(f"Failed to initialize database: {e}")

# Page config
st.set_page_config(
    page_title="LogSage AI",
    page_icon="🔍",
    layout="wide"
)

# --- Sidebar ---
with st.sidebar:
    st.title("🔍 LogSage AI")
    
    nav_selection = st.radio("Navigation", ["🏠 Analyze Logs", "📜 Incident History", "ℹ️ About"])
    
    st.markdown("---")
    st.subheader("Agent Settings")
    
    # Allow dynamic URL override for cloud deployments
    current_host = st.session_state.get("ollama_host", os.getenv("OLLAMA_HOST", "http://localhost:11434"))
    new_host = st.text_input("Ollama URL (e.g., localtunnel)", value=current_host, help="If running on Render, paste your localtunnel URL here.")
    
    if new_host != current_host:
        os.environ["OLLAMA_HOST"] = new_host
        st.session_state["ollama_host"] = new_host
        st.session_state["ollama_online"] = is_ollama_available()
    
    # Check Ollama status
    if "ollama_online" not in st.session_state:
        st.session_state["ollama_online"] = is_ollama_available()
        
    if st.session_state["ollama_online"]:
        st.success("🟢 Ollama Online")
    else:
        st.error("🔴 Ollama Offline")
        if st.button("Check Again"):
            st.session_state["ollama_online"] = is_ollama_available()
            st.rerun()
            
    model_name = st.selectbox("Model", ["llama3", "llama2", "mistral"], index=0)
    # Update env var to affect analyzer
    os.environ["MODEL_NAME"] = model_name

# --- Helper Functions ---
def render_dashboard(report):
    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Lines", report.get("total_lines", 0))
    c2.metric("Errors Found", report.get("errors_found", 0))
    c3.metric("Max Severity", f'{report.get("max_severity", 0)}/10')
    c4.metric("Avg Severity", report.get("avg_severity", 0.0))
    
    # Exec Summary
    st.info(f"**Executive Summary:**\n\n{report.get('executive_summary', 'N/A')}")
    
    # Charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Category Distribution")
        cat_counts = report.get("category_counts", {})
        if cat_counts:
            fig1 = go.Figure(data=[go.Pie(labels=list(cat_counts.keys()), values=list(cat_counts.values()), hole=.3)])
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.write("No category data available.")
            
    with col2:
        st.subheader("Severity Distribution")
        sev_counts = report.get("severity_distribution", {})
        # Ensure order
        ordered_sevs = ["Low", "Medium", "High", "Critical"]
        vals = [sev_counts.get(s, 0) for s in ordered_sevs]
        
        fig2 = go.Figure(data=[go.Bar(x=ordered_sevs, y=vals, marker_color=['#2ca02c', '#ff7f0e', '#d62728', '#9467bd'])])
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig2, use_container_width=True)

def render_anomalies(report):
    anomalies = report.get("anomaly_analyses", [])
    if not anomalies:
        st.info("No anomalies found.")
        return
        
    for anomaly in anomalies:
        line_no = anomaly.get("line_number", "?")
        kw = anomaly.get("matched_keyword", "")
        cat = anomaly.get("category", "")
        sev_label = anomaly.get("severity_label", "")
        sev_score = anomaly.get("severity_score", 0)
        
        with st.expander(f"Line {line_no} — {kw} — {cat}"):
            st.markdown(f"**Severity:** {sev_score}/10 ({sev_label})")
            st.markdown(f"**Root Cause:** {anomaly.get('root_cause', 'N/A')}")
            
            st.markdown("**Remediation Steps:**")
            for i, step in enumerate(anomaly.get("remediation_steps", []), 1):
                st.markdown(f"{i}. {step}")
                
            st.markdown("**Context:**")
            context_lines = anomaly.get("context_before", []) + [anomaly.get("line_text", "")] + anomaly.get("context_after", [])
            st.code("\n".join(context_lines), language="log")

def render_report_tab(report):
    c1, c2 = st.columns(2)
    
    # Generate files in temp dir
    temp_dir = os.getenv("REPORT_OUTPUT_DIR", tempfile.mkdtemp())
    os.makedirs(temp_dir, exist_ok=True)
    pdf_path = os.path.join(temp_dir, "incident_report.pdf")
    csv_path = os.path.join(temp_dir, "anomalies.csv")
    
    try:
        generate_pdf(report, pdf_path)
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        with c1:
            st.download_button("⬇️ Download PDF Report", data=pdf_bytes, file_name="incident_report.pdf", mime="application/pdf")
    except Exception as e:
        c1.error(f"Failed to generate PDF: {e}")
        
    try:
        generate_csv(report, csv_path)
        with open(csv_path, "rb") as f:
            csv_bytes = f.read()
        with c2:
            st.download_button("⬇️ Download CSV", data=csv_bytes, file_name="anomalies.csv", mime="text/csv")
    except Exception as e:
        c2.error(f"Failed to generate CSV: {e}")
        
    with st.expander("View Raw JSON"):
        st.json(report)

# --- Main App ---
if nav_selection == "🏠 Analyze Logs":
    st.header("Analyze Log File")
    uploaded_file = st.file_uploader("Upload a log file", type=["log", "txt"])
    
    if uploaded_file is not None:
        if st.button("🚀 Run Analysis"):
            if not st.session_state["ollama_online"]:
                st.error("Cannot run analysis while Ollama is offline. Please start it and check again.")
            else:
                try:
                    file_content = uploaded_file.getvalue().decode("utf-8")
                    filename = uploaded_file.name
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Agent Steps 1-2
                    status_text.text("Parsing log file...")
                    parsed_data = parse_log_file(file_content)
                    progress_bar.progress(20)
                    
                    # Agent Steps 3-7
                    status_text.text("Running Agent Loop for AI Analysis...")
                    report = run_agent_loop(parsed_data, filename)
                    progress_bar.progress(80)
                    
                    status_text.text("Saving incident to database...")
                    incident_id = save_incident(report)
                    progress_bar.progress(100)
                    status_text.text("Analysis complete!")
                    
                    st.session_state["last_report"] = report
                    
                except Exception as e:
                    st.error(f"An error occurred during analysis: {e}")

    if "last_report" in st.session_state:
        st.markdown("---")
        report = st.session_state["last_report"]
        t1, t2, t3 = st.tabs(["📊 Dashboard", "🔍 Anomalies", "📄 Report"])
        
        with t1:
            render_dashboard(report)
        with t2:
            render_anomalies(report)
        with t3:
            render_report_tab(report)

elif nav_selection == "📜 Incident History":
    st.header("Incident History")
    
    try:
        history = get_incident_history()
        if not history:
            st.info("No incidents analyzed yet.")
        else:
            search_term = st.text_input("Search by filename")
            
            for incident in history:
                filename = incident["log_filename"]
                if search_term and search_term.lower() not in filename.lower():
                    continue
                    
                with st.container(border=True):
                    cols = st.columns([3, 2, 2])
                    with cols[0]:
                        st.markdown(f"**{filename}**")
                        st.caption(incident["analysis_timestamp"])
                    with cols[1]:
                        st.write(f"Errors: {incident['errors_found']} | Max Sev: {incident['max_severity']}")
                    with cols[2]:
                        c1, c2 = st.columns(2)
                        if c1.button("View Full Report", key=f"view_{incident['id']}"):
                            full_report = get_incident_by_id(incident['id'])
                            if full_report:
                                st.session_state["last_report"] = full_report
                                st.success("Loaded into session. Go to 'Analyze Logs' to view.")
                            else:
                                st.error("Failed to load full report.")
                        if c2.button("Delete", key=f"del_{incident['id']}"):
                            delete_incident(incident['id'])
                            st.rerun()
                            
    except Exception as e:
        st.error(f"Failed to load history: {e}")

elif nav_selection == "ℹ️ About":
    st.header("About LogSage AI")
    st.write("LogSage AI is an intelligent log file analyzer that uses local LLMs to interpret errors, find root causes, and suggest remediations.")
    
    st.subheader("Team")
    st.write("Built by a 4-member team for the Infinite Computer Solutions AI Prototype Challenge.")
    
    st.subheader("Tech Stack")
    st.table({
        "Component": ["Frontend", "Backend", "AI Model", "Database"],
        "Technology": ["Streamlit", "Python 3.10", "Ollama (llama3)", "SQLite3"]
    })
    
    st.subheader("Agent Workflow")
    st.markdown("""
    1. **Read**: Parse the raw log file.
    2. **Detect**: Extract anomalies based on keywords.
    3. **Extract Context**: Capture surrounding log lines.
    4. **Analyze**: Query LLM for root cause and remediation.
    5. **Severity**: Calculate impact metrics.
    6. **Recommendations**: Generate executive summary.
    7. **Report**: Compile and save final incident data.
    """)
    
    st.markdown("[GitHub Repository Placeholder](#)")
