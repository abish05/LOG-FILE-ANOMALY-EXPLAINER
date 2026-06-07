import os
import csv
import logging
import tempfile
from datetime import datetime
from typing import Dict, Any

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)

logger = logging.getLogger(__name__)

REPORT_DIR = os.getenv(
    "REPORT_OUTPUT_DIR",
    os.path.join(tempfile.gettempdir(), "logsage_reports")
)

def _ensure_dir() -> str:
    os.makedirs(REPORT_DIR, exist_ok=True)
    return REPORT_DIR

_SEV_HEX = {
    "Critical": "A32D2D",
    "High":     "854F0B",
    "Medium":   "185FA5",
    "Low":      "3B6D11",
}

def _severity_color(label: str):
    """Return a ReportLab HexColor for the given severity label."""
    hex_val = _SEV_HEX.get(label, "000000")
    return colors.HexColor(f"#{hex_val}")

def _severity_hex(label: str) -> str:
    """Return the raw 6-char hex string (no #) for inline font tags."""
    return _SEV_HEX.get(label, "000000")

def generate_pdf(report: Dict[str, Any],
                 output_path: str = None) -> str:
    """Generate PDF incident report. Returns output path."""
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"logsage_report_{ts}.pdf"
        output_path = os.path.join(_ensure_dir(), fname)

    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        rightMargin=2*cm, leftMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm
    )
    styles = getSampleStyleSheet()
    RED = colors.HexColor("#E24B4A")
    DARK = colors.HexColor("#2C2C2A")
    GRAY_BG = colors.HexColor("#F1EFE8")

    title_style = ParagraphStyle(
        "Title", parent=styles["Heading1"],
        textColor=RED, fontSize=22, spaceAfter=4
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"],
        textColor=DARK, fontSize=14, spaceBefore=16, spaceAfter=6
    )
    body_style = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=10, leading=14, textColor=DARK
    )
    mono_style = ParagraphStyle(
        "Mono", parent=styles["Code"],
        fontSize=8, leading=11,
        backColor=GRAY_BG, textColor=DARK
    )

    story = []

    story.append(Paragraph("LogSage AI — Incident Report", title_style))
    story.append(Paragraph(
        f"File: {report.get('log_filename', 'N/A')} &nbsp;|&nbsp; "
        f"Generated: {report.get('analysis_timestamp', 'N/A')[:19]}",
        body_style
    ))
    story.append(Spacer(1, 0.4*cm))

    summary_data = [
        ["Metric", "Value"],
        ["Total log lines", str(report.get("total_lines", 0))],
        ["Anomalies detected", str(report.get("errors_found", 0))],
        ["Max severity", f"{report.get('max_severity', 0)}/10"],
        ["Avg severity", str(report.get("avg_severity", 0))],
        ["Agent steps completed", str(report.get("agent_steps_completed", 0))],
    ]
    summary_table = Table(summary_data, colWidths=[8*cm, 8*cm])
    summary_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), RED),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("BACKGROUND", (0, 1), (-1, -1), GRAY_BG),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.white),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, GRAY_BG]),
    ]))
    story.append(summary_table)

    story.append(Paragraph("Severity distribution", h2_style))
    sev_dist = report.get("severity_distribution", {})
    sev_data = [["Severity", "Count"]] + [
        [k, str(v)] for k, v in sev_dist.items()
    ]
    sev_table = Table(sev_data, colWidths=[8*cm, 8*cm])
    sev_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), RED),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, GRAY_BG]),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.white),
    ]))
    story.append(sev_table)

    story.append(Paragraph("Executive summary", h2_style))
    story.append(Paragraph(
        report.get("executive_summary", "N/A"), body_style
    ))

    story.append(PageBreak())
    story.append(Paragraph("Anomaly analysis", h2_style))

    for i, a in enumerate(report.get("anomaly_analyses", []), 1):
        sev_label = a.get("severity_label", "Medium")
        story.append(Paragraph(
            f"<font color='#{_severity_hex(sev_label)}'>"
            f"[{sev_label}]</font> &nbsp; "
            f"Line {a.get('line_number')} — "
            f"{a.get('matched_keyword')} — {a.get('category')}",
            h2_style
        ))
        story.append(Paragraph(
            f"Severity: {a.get('severity_score')}/10", body_style
        ))
        story.append(Paragraph(
            f"Root cause: {a.get('root_cause', 'N/A')}", body_style
        ))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Log line:", body_style))
        story.append(Paragraph(
            a.get("line_text", "")[:200], mono_style
        ))
        story.append(Spacer(1, 0.2*cm))
        story.append(Paragraph("Remediation steps:", body_style))
        for j, step in enumerate(
            a.get("remediation_steps", []), 1
        ):
            story.append(Paragraph(f"{j}. {step}", body_style))
        story.append(Paragraph(
            f"Summary: {a.get('summary', '')}", body_style
        ))
        story.append(Spacer(1, 0.4*cm))

    doc.build(story)
    logger.info(f"PDF generated: {output_path}")
    return output_path

def generate_csv(report: Dict[str, Any],
                 output_path: str = None) -> str:
    """Generate CSV of anomalies. Returns output path."""
    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"logsage_report_{ts}.csv"
        output_path = os.path.join(_ensure_dir(), fname)

    fieldnames = [
        "line_number", "matched_keyword", "category",
        "severity_score", "severity_label",
        "root_cause", "summary"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in report.get("anomaly_analyses", []):
            writer.writerow({
                "line_number": a.get("line_number", ""),
                "matched_keyword": a.get("matched_keyword", ""),
                "category": a.get("category", ""),
                "severity_score": a.get("severity_score", ""),
                "severity_label": a.get("severity_label", ""),
                "root_cause": a.get("root_cause", ""),
                "summary": a.get("summary", ""),
            })
    logger.info(f"CSV generated: {output_path}")
    return output_path
