"""カバレッジ表を PDF 化(日本語対応)。大橋さんの COVERAGE PDF の簡易再現。"""
from __future__ import annotations
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/fonts-japanese-gothic.ttf",
]


def _register_font() -> str:
    for p in _FONT_CANDIDATES:
        if os.path.exists(p):
            pdfmetrics.registerFont(TTFont("JP", p))
            return "JP"
    return "Helvetica"


def render_coverage_pdf(rows: list[dict], columns: list[tuple[str, str]],
                        out_path: str, title: str, intro: str = "") -> None:
    """rows: 各行 dict。columns: [(key, 表示ヘッダ), ...]。"""
    font = _register_font()
    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Title"], fontName=font, fontSize=15)
    p = ParagraphStyle("p", parent=styles["Normal"], fontName=font, fontSize=8, leading=11)
    cell = ParagraphStyle("c", parent=styles["Normal"], fontName=font, fontSize=7.5, leading=9.5)

    doc = SimpleDocTemplate(out_path, pagesize=landscape(A4),
                            leftMargin=10 * mm, rightMargin=10 * mm,
                            topMargin=10 * mm, bottomMargin=10 * mm)
    story = [Paragraph(title, h), Spacer(1, 4)]
    if intro:
        story += [Paragraph(intro, p), Spacer(1, 6)]

    header = [Paragraph(f"<b>{lbl}</b>", cell) for _, lbl in columns]
    data = [header]
    for r in rows:
        data.append([Paragraph(str(r.get(k, "")), cell) for k, _ in columns])

    tbl = Table(data, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f5597")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0b0b0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f9")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(tbl)
    doc.build(story)
