import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT / "docs" / "data" / "baltic_dashboard.json"
REPORT_DIR = ROOT / "docs" / "reports"
ARCHIVE_DIR = REPORT_DIR / "archive"
LATEST_REPORT = REPORT_DIR / "latest-baltic-hybrid-threat-report.pdf"


def load_dashboard_data():
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Missing dashboard data: {DATA_PATH}")

    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def safe(value, default="—"):
    if value is None:
        return default
    return value


def fmt(value, digits=0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "—"

    if digits == 0:
        return f"{int(round(number)):,}".replace(",", " ")

    return f"{number:,.{digits}f}".replace(",", " ")


def paragraph(text, style):
    return Paragraph(str(text).replace("&", "&amp;"), style)


def build_table(rows, col_widths=None):
    table = Table(rows, colWidths=col_widths, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def make_report():
    data = load_dashboard_data()
    summary = data.get("summary", {})
    generated_at = data.get("latest_update") or data.get("generated_at") or datetime.now(timezone.utc).isoformat()
    report_date = generated_at[:10]

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

    archive_report = ARCHIVE_DIR / f"baltic-hybrid-threat-report-{report_date}.pdf"

    doc = SimpleDocTemplate(
        str(archive_report),
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.4 * cm,
        title=f"Baltic Hybrid Threat Daily Report - {report_date}",
        author="Törésvonalak Monitor Network",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=colors.HexColor("#0f172a"),
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#0284c7"),
        spaceBefore=12,
        spaceAfter=8,
    )
    body = ParagraphStyle(
        "Body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=9,
        leading=13,
        textColor=colors.HexColor("#334155"),
        spaceAfter=7,
    )

    story = []

    story.append(paragraph("Baltic Hybrid Threat Daily Report", title_style))
    story.append(paragraph(f"Report date: {report_date}", body))
    story.append(paragraph(f"Region: {data.get('region', 'Baltic states and Poland')}", body))
    story.append(paragraph("This report is generated automatically from open-source monitoring data.", body))

    story.append(paragraph("Executive summary", h2))
    story.append(
        build_table(
            [
                ["Metric", "Value"],
                ["Threat Index", fmt(summary.get("threat_index"), 2)],
                ["Threat Level", str(summary.get("threat_level", "—")).upper()],
                ["Events", fmt(summary.get("event_count"))],
                ["Incidents", fmt(summary.get("incident_count"))],
                ["Activity", fmt(summary.get("activity_count"))],
                ["Indicators", fmt(summary.get("indicator_count"))],
                ["Assessments", fmt(summary.get("assessment_count"))],
                ["Highest event score", fmt(summary.get("highest_score"))],
            ],
            [7 * cm, 8 * cm],
        )
    )

    story.append(paragraph("Subtype breakdown", h2))
    subtype_rows = [["Subtype", "Events", "Score total", "Average score"]]
    for item in data.get("subtype_cards", []):
        subtype_rows.append(
            [
                safe(item.get("label")),
                fmt(item.get("event_count")),
                fmt(item.get("score_total")),
                fmt(item.get("average_score"), 2),
            ]
        )
    story.append(build_table(subtype_rows, [4.5 * cm, 3 * cm, 3.5 * cm, 3.5 * cm]))

    story.append(paragraph("Country overview", h2))
    country_rows = [["Country", "Events", "Incidents", "Average score", "Highest", "Level"]]
    for country in data.get("country_cards", []):
        country_rows.append(
            [
                country.get("country", "—"),
                fmt(country.get("event_count")),
                fmt(country.get("incident_count")),
                fmt(country.get("average_score"), 2),
                fmt(country.get("highest_score")),
                str(country.get("level", "—")).upper(),
            ]
        )
    story.append(build_table(country_rows, [3.2 * cm, 2.3 * cm, 2.3 * cm, 3 * cm, 2.3 * cm, 2.5 * cm]))

    story.append(PageBreak())
    story.append(paragraph("Top threat drivers", h2))
    driver_rows = [["Category", "Events", "Score total", "Average score", "Highest"]]
    for item in data.get("category_drivers", [])[:10]:
        driver_rows.append(
            [
                str(item.get("category", "—")).replace("_", " ").title(),
                fmt(item.get("event_count")),
                fmt(item.get("score_total")),
                fmt(item.get("average_score"), 2),
                fmt(item.get("highest_score")),
            ]
        )
    story.append(build_table(driver_rows, [5 * cm, 2.5 * cm, 3 * cm, 3 * cm, 2.5 * cm]))

    story.append(paragraph("Actor exposure", h2))
    actor_rows = [["Actor", "Events", "Score total", "Average score", "Highest"]]
    for item in data.get("actor_drivers", [])[:10]:
        actor_rows.append(
            [
                item.get("actor", "—"),
                fmt(item.get("event_count")),
                fmt(item.get("score_total")),
                fmt(item.get("average_score"), 2),
                fmt(item.get("highest_score")),
            ]
        )
    story.append(build_table(actor_rows, [5 * cm, 2.5 * cm, 3 * cm, 3 * cm, 2.5 * cm]))

    story.append(PageBreak())
    story.append(paragraph("Critical events", h2))
    event_rows = [["Score", "Event", "Country", "Subtype", "Sources", "Confidence"]]
    for event in data.get("top_events", [])[:12]:
        event_rows.append(
            [
                fmt(event.get("hybrid_threat_score")),
                paragraph(event.get("title", "Untitled event"), body),
                event.get("primary_country", "—"),
                str(event.get("event_subtype", "—")).title(),
                fmt(event.get("source_count")),
                fmt(event.get("confidence_score")),
            ]
        )
    story.append(build_table(event_rows, [1.5 * cm, 8 * cm, 2.2 * cm, 2.2 * cm, 1.7 * cm, 2 * cm]))

    story.append(PageBreak())
    story.append(paragraph("Methodology", h2))
    methodology = data.get("methodology", {})
    story.append(paragraph(methodology.get("model", "Event-based rule-driven OSINT threat intelligence model."), body))

    story.append(paragraph("Pipeline", h2))
    for step in methodology.get("pipeline", []):
        story.append(paragraph(f"- {step}", body))

    story.append(paragraph("Event ontology", h2))
    for key, value in methodology.get("event_subtypes", {}).items():
        story.append(paragraph(f"<b>{key.title()}</b>: {value}", body))

    story.append(paragraph("Warning", h2))
    story.append(paragraph(methodology.get("warning", "This dashboard is an OSINT monitoring aid and not an official threat assessment."), body))

    doc.build(story)

    shutil.copyfile(archive_report, LATEST_REPORT)

    print(f"Saved archived report: {archive_report}")
    print(f"Saved latest report: {LATEST_REPORT}")


if __name__ == "__main__":
    make_report()
