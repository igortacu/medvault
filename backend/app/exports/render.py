"""Render an export bundle as PDF (in the requester's language) or JSON.

Neither format carries internal ids: no document UUIDs, storage keys or
institutional record references, only what the patient would read on the record.
"""
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

log = logging.getLogger("medvault.exports")

LANGUAGES = ("ro", "en", "ru")
DEFAULT_LANGUAGE = "ro"
# Times in the PDF are shown on the patient's clock, not in UTC.
TIMEZONE = ZoneInfo(os.getenv("EXPORT_TIMEZONE", "Europe/Chisinau"))
_LABELS = json.loads((Path(__file__).parent / "labels.json").read_text(encoding="utf-8"))

# A Unicode TrueType pair is needed for ă/ș/ț and Cyrillic. The backend image installs
# DejaVu (fonts-dejavu-core); EXPORT_FONT_PATH / EXPORT_FONT_BOLD_PATH override it, and
# common desktop fonts cover local runs.
_FONT_CANDIDATES = (
    (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
)


@dataclass
class ExportRecord:
    category: str
    type: str
    title: str | None
    date: date | None
    source: str
    self_uploaded: bool
    specialty: str | None = None
    practitioner: str | None = None
    issuer: str | None = None


@dataclass
class Measurements:
    weight_kg: float | None
    height_cm: float | None
    updated_at: datetime | None


@dataclass
class ExportBundle:
    generated_at: datetime
    patient_name: str
    birth_date: date | None
    categories: list[str]
    records: list[ExportRecord] = field(default_factory=list)
    measurements: Measurements | None = None
    # (institution name, status) for sources that couldn't be read at export time.
    missing_sources: list[tuple[str, str]] = field(default_factory=list)
    single_record: bool = False


def labels(lang: str) -> dict:
    return _LABELS.get(lang) or _LABELS[DEFAULT_LANGUAGE]


def type_label(lang: str, code: str) -> str:
    return labels(lang)["docType"].get(code, code)


@lru_cache
def _fonts() -> tuple[str, str]:
    """(regular, bold) font names, registering the first TrueType pair found."""
    configured = os.getenv("EXPORT_FONT_PATH")
    candidates = list(_FONT_CANDIDATES)
    if configured:
        candidates.insert(0, (configured, os.getenv("EXPORT_FONT_BOLD_PATH", configured)))
    for regular, bold in candidates:
        if os.path.isfile(regular) and os.path.isfile(bold):
            pdfmetrics.registerFont(TTFont("ExportSans", regular))
            pdfmetrics.registerFont(TTFont("ExportSans-Bold", bold))
            return "ExportSans", "ExportSans-Bold"
    # Latin-only fallback: Romanian/Russian letters would not render. Loud, not silent.
    log.error("No Unicode font found for exports; set EXPORT_FONT_PATH")
    return "Helvetica", "Helvetica-Bold"


def _date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(TIMEZONE)
        return value.strftime("%d.%m.%Y %H:%M")
    return value.strftime("%d.%m.%Y")


def render_pdf(bundle: ExportBundle, lang: str) -> bytes:
    text = labels(lang)
    t = text["export"]
    regular, bold = _fonts()
    body = ParagraphStyle("body", fontName=regular, fontSize=9, leading=12)
    small = ParagraphStyle("small", parent=body, fontSize=8, leading=10, textColor=colors.HexColor("#555555"))
    cell = ParagraphStyle("cell", parent=body, fontSize=8.5, leading=11)
    head_cell = ParagraphStyle("head", parent=cell, fontName=bold)
    title = ParagraphStyle("title", fontName=bold, fontSize=16, leading=20, spaceAfter=4)
    heading = ParagraphStyle("heading", fontName=bold, fontSize=12, leading=16, spaceBefore=10, spaceAfter=4)

    def p(value: str | None, style=cell) -> Paragraph:
        return Paragraph(escape(value or "—"), style)

    story = [
        Paragraph(escape(f"MedVault — {t['title']}"), title),
        p(f"{t['patient']}: {bundle.patient_name}", body),
        p(f"{t['born']}: {_date(bundle.birth_date)}", body),
        p(f"{t['generated']}: {_date(bundle.generated_at)}", body),
        p(
            f"{t['categories']}: "
            + (
                t["single_record"]
                if bundle.single_record
                else ", ".join(text["category"].get(c, c) for c in bundle.categories)
            ),
            body,
        ),
    ]
    for institution, status in bundle.missing_sources:
        reason = t["status"].get(status, status)
        story.append(p(t["source_missing"].format(institution=institution, status=reason), small))

    for category in bundle.categories:
        if category == "patient_info":
            if bundle.single_record:
                continue
            story.append(Paragraph(escape(text["category"].get(category, category)), heading))
            m = bundle.measurements
            rows = [
                [p(t["weight"], head_cell), p(f"{m.weight_kg:g} kg" if m and m.weight_kg else None)],
                [p(t["height"], head_cell), p(f"{m.height_cm:g} cm" if m and m.height_cm else None)],
                [p(t["measured"], head_cell), p(_date(m.updated_at) if m else None)],
            ]
            table = Table(rows, colWidths=[45 * mm, 120 * mm], hAlign="LEFT")
            table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
            story.append(table)
            continue

        records = [r for r in bundle.records if r.category == category]
        if not bundle.single_record:
            story.append(Paragraph(escape(text["category"].get(category, category)), heading))
        if not records:
            story.append(p(t["no_records"], body))
            continue
        rows = [[p(t[k], head_cell) for k in ("date", "type", "record", "source", "doctor")]]
        for r in records:
            source = t["self_uploaded"] if r.self_uploaded else r.source
            details = r.title or type_label(lang, r.type)
            if r.specialty:
                details += f" · {r.specialty}"
            doctor = r.practitioner
            if r.self_uploaded and r.issuer:
                source += "\n" + t["declared_issuer"].format(issuer=r.issuer)
            rows.append(
                [
                    p(_date(r.date)),
                    p(type_label(lang, r.type)),
                    p(details),
                    Paragraph(escape(source).replace("\n", "<br/>"), cell),
                    p(doctor),
                ]
            )
        table = Table(
            rows,
            colWidths=[23 * mm, 32 * mm, 55 * mm, 40 * mm, 30 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF4F2")),
                    ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#CCCCCC")),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    story.append(Spacer(1, 6 * mm))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(colors.HexColor("#666666"))
        page = t["page"].format(page=doc.page)
        canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, page)
        # Wrap the notice so it never runs into the page number.
        width = A4[0] - 30 * mm - pdfmetrics.stringWidth(page, regular, 7) - 6 * mm
        lines = simpleSplit(t["footer"], regular, 7, width)
        for index, line in enumerate(lines[:2]):
            canvas.drawString(15 * mm, 10 * mm + (len(lines[:2]) - 1 - index) * 9, line)
        canvas.restoreState()

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title=f"MedVault — {t['title']}",
        author="MedVault",
        lang=lang,
    )
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


def render_json(bundle: ExportBundle, lang: str) -> bytes:
    """Machine-readable export: codes plus their label in `lang`, no internal ids."""
    def record(r: ExportRecord) -> dict:
        data = asdict(r)
        data["type_label"] = type_label(lang, r.type)
        data["date"] = r.date.isoformat() if r.date else None
        return data

    payload = {
        "format": "medvault-export/1",
        "language": lang,
        "generated_at": bundle.generated_at.isoformat(),
        "patient": {
            "name": bundle.patient_name,
            "date_of_birth": bundle.birth_date.isoformat() if bundle.birth_date else None,
        },
        "categories": bundle.categories,
        "single_record": bundle.single_record,
        "records": [record(r) for r in bundle.records],
        "measurements": (
            {
                "weight_kg": bundle.measurements.weight_kg,
                "height_cm": bundle.measurements.height_cm,
                "updated_at": bundle.measurements.updated_at.isoformat()
                if bundle.measurements.updated_at
                else None,
            }
            if bundle.measurements
            else None
        ),
        "sources_not_included": [
            {"institution": name, "status": status} for name, status in bundle.missing_sources
        ],
    }
    return (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode()
