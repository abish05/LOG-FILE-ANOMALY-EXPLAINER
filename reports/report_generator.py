"""
Report generation module for LogSage AI.
Handles export to PDF and CSV formats.
"""

import csv
import logging
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

def generate_pdf(report: Dict[str, Any], output_path: str) -> str:
    """
    Generates a PDF incident report.

    Args:
        report (dict): The complete incident report dictionary.
        output_path (str): The file path where the PDF will be saved.

    Returns:
        str: The output_path on success.
    """
    logger.info(f"Generating PDF report at {output_path}")
    doc = SimpleDocTemplate(output_path, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = styles['Title']
    story.append(Paragraph("LogSage AI — Incident Report", title_style))
    story.append(Spacer(1, 12))

    # Meta Info
    normal_style = styles['Normal']
    story.append(Paragraph(f"<b>File:</b> {report.get('log_filename', 'Unknown')}", normal_style))
    story.append(Paragraph(f"<b>Date:</b> {report.get('analysis_timestamp', 'Unknown')}", normal_style))
    story.append(Spacer(1, 12))

    # Summary Table
    story.append(Paragraph("<b>Overview</b>", styles['Heading2']))
    summary_data = [
        ["Total Lines", "Errors Found", "Max Severity", "Avg Severity"],
        [
            str(report.get("total_lines", 0)),
            str(report.get("errors_found", 0)),
            str(report.get("max_severity", 0)),
            str(report.get("avg_severity", 0.0))
        ]
    ]
    t_summary = Table(summary_data)
    t_summary.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t_summary)
    story.append(Spacer(1, 12))

    # Executive Summary
    story.append(Paragraph("<b>Executive Summary</b>", styles['Heading2']))
    story.append(Paragraph(report.get("executive_summary", "N/A"), normal_style))
    story.append(Spacer(1, 12))

    # Category Breakdown
    story.append(Paragraph("<b>Category Breakdown</b>", styles['Heading2']))
    cat_data = [["Category", "Count"]]
    for cat, count in report.get("category_counts", {}).items():
        cat_data.append([cat, str(count)])
    if len(cat_data) > 1:
        t_cat = Table(cat_data)
        t_cat.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        story.append(t_cat)
    else:
        story.append(Paragraph("No category data.", normal_style))
    story.append(Spacer(1, 12))

    # Severity Distribution
    story.append(Paragraph("<b>Severity Distribution</b>", styles['Heading2']))
    sev_data = [["Severity", "Count"]]
    for sev, count in report.get("severity_distribution", {}).items():
        sev_data.append([sev, str(count)])
    t_sev = Table(sev_data)
    t_sev.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t_sev)
    story.append(Spacer(1, 12))

    # Anomalies
    story.append(Paragraph("<b>Anomalies Details</b>", styles['Heading2']))
    for idx, anomaly in enumerate(report.get("anomaly_analyses", []), 1):
        story.append(Paragraph(f"<b>Anomaly {idx} (Line {anomaly.get('line_number', '?')})</b>", styles['Heading3']))
        story.append(Paragraph(f"<b>Keyword:</b> {anomaly.get('matched_keyword', '')}", normal_style))
        story.append(Paragraph(f"<b>Category:</b> {anomaly.get('category', '')}", normal_style))
        story.append(Paragraph(f"<b>Severity:</b> {anomaly.get('severity_score', '')}/10 ({anomaly.get('severity_label', '')})", normal_style))
        story.append(Spacer(1, 6))
        story.append(Paragraph(f"<b>Root Cause:</b> {anomaly.get('root_cause', '')}", normal_style))
        story.append(Spacer(1, 6))
        
        story.append(Paragraph("<b>Remediation Steps:</b>", normal_style))
        for step_idx, step in enumerate(anomaly.get("remediation_steps", []), 1):
            story.append(Paragraph(f"{step_idx}. {step}", normal_style))
            
        story.append(Spacer(1, 12))

    doc.build(story)
    logger.info("PDF generation complete")
    return output_path

def generate_csv(report: Dict[str, Any], output_path: str) -> str:
    """
    Generates a CSV incident report of all anomalies.

    Args:
        report (dict): The complete incident report dictionary.
        output_path (str): The file path where the CSV will be saved.

    Returns:
        str: The output_path on success.
    """
    logger.info(f"Generating CSV report at {output_path}")
    
    headers = ["line_number", "keyword", "category", "severity_score", "severity_label", "root_cause", "summary"]
    
    with open(output_path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        
        for anomaly in report.get("anomaly_analyses", []):
            writer.writerow({
                "line_number": anomaly.get("line_number", ""),
                "keyword": anomaly.get("matched_keyword", ""),
                "category": anomaly.get("category", ""),
                "severity_score": anomaly.get("severity_score", ""),
                "severity_label": anomaly.get("severity_label", ""),
                "root_cause": anomaly.get("root_cause", ""),
                "summary": anomaly.get("summary", "")
            })
            
    logger.info("CSV generation complete")
    return output_path
