"""
合规留痕 PDF（由 JSON 报告渲染；需 fpdf2，见 requirements/enterprise.txt）。
"""
from __future__ import annotations

from typing import Any, Dict


def render_compliance_pdf(report: Dict[str, Any]) -> bytes:
    try:
        from fpdf import FPDF
    except ImportError as exc:
        raise RuntimeError("fpdf2 not installed; pip install -r requirements/enterprise.txt") from exc

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(0, 10, "Perilla Compliance Trace Report", ln=True)
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, f"Type: {report.get('report_type', '')}", ln=True)
    pdf.cell(0, 6, f"Generated: {report.get('generated_at', '')}", ln=True)
    pdf.cell(0, 6, f"Workflow: {report.get('workflow_id', '')}", ln=True)
    pdf.cell(0, 6, f"Execution: {report.get('execution_id', '')}", ln=True)
    pdf.ln(4)

    ex = report.get("execution") or {}
    pdf.cell(0, 6, f"State: {ex.get('state', '')}", ln=True)
    pdf.cell(0, 6, f"Trigger: {ex.get('trigger_type', '')}", ln=True)

    collab = report.get("collaboration") or {}
    pdf.ln(2)
    pdf.cell(0, 6, f"Correlation: {collab.get('correlation_id', '')}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", style="B", size=9)
    pdf.cell(0, 6, "Approval tasks", ln=True)
    pdf.set_font("Helvetica", size=8)
    for t in report.get("approval_tasks") or []:
        line = f"- {t.get('node_id')}: {t.get('status')} ({t.get('id', '')[:8]})"
        pdf.cell(0, 5, line[:120], ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", style="B", size=9)
    pdf.cell(0, 6, "Node timeline", ln=True)
    pdf.set_font("Helvetica", size=8)
    for n in report.get("node_timeline") or []:
        pdf.cell(
            0,
            5,
            f"- {n.get('node_id')}: {n.get('status')}",
            ln=True,
        )

    pdf.ln(6)
    pdf.set_font("Helvetica", style="I", size=8)
    disc = str(report.get("disclaimer") or "")
    pdf.multi_cell(0, 4, disc[:500])

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1", errors="replace")
    return bytes(out)
