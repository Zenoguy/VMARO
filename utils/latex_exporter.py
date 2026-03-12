"""
utils/latex_exporter.py

Convert a grant-proposal JSON (Agent 5 output) into:
  • A compilable LaTeX (.tex) source document
  • A professional PDF (reportlab) with LaTeX-style academic formatting
"""

import io
from datetime import datetime

# ──────────────────────────────────────────────────────────────────────────────
#  Shared constants
# ──────────────────────────────────────────────────────────────────────────────

_CORE_SECTIONS = [
    ("problem_statement",   "Problem Statement"),
    ("proposed_solution",   "Proposed Solution"),
    ("methodology_summary", "Methodology Summary"),
    ("expected_outcomes",   "Expected Outcomes"),
    ("broader_impacts",     "Broader Impacts"),
    ("budget_justification","Budget Justification"),
]

_SKIP_KEYS = {"title", "format_used", "sections"} | {k for k, _ in _CORE_SECTIONS}


# ══════════════════════════════════════════════════════════════════════════════
#  LaTeX source generator
# ══════════════════════════════════════════════════════════════════════════════

_LATEX_SPECIAL = {
    "\\": "\\textbackslash{}",
    "&":  "\\&",
    "%":  "\\%",
    "$":  "\\$",
    "#":  "\\#",
    "_":  "\\_",
    "{":  "\\{",
    "}":  "\\}",
    "~":  "\\textasciitilde{}",
    "^":  "\\textasciicircum{}",
}


def _esc(text: str) -> str:
    """Escape LaTeX special characters (backslash must be processed first)."""
    if not isinstance(text, str):
        text = str(text)
    # Process backslash first so we don't double-escape later replacements
    result = []
    for ch in text:
        result.append(_LATEX_SPECIAL.get(ch, ch))
    return "".join(result)


def _section_body_latex(content) -> str:
    """Render grant content (str / list / dict) as LaTeX body markup."""
    lines = []
    if isinstance(content, list):
        lines.append("\\begin{itemize}[noitemsep,topsep=4pt]")
        for item in content:
            lines.append(f"  \\item {_esc(str(item))}")
        lines.append("\\end{itemize}")
    elif isinstance(content, dict):
        for k, v in content.items():
            lines.append(f"\\subsection{{{_esc(k)}}}")
            lines.append(_section_body_latex(v))
            lines.append("")
    else:
        raw = str(content).replace("\\n", "\n")
        for para in raw.split("\n\n"):
            para = para.strip()
            if para:
                lines.append(_esc(para))
                lines.append("")
    return "\n".join(lines)


def generate_latex_source(grant_data: dict, topic: str, format_name: str = "") -> str:
    """Return a complete, compilable LaTeX document for the grant proposal."""

    title = _esc(grant_data.get("title", topic))
    fmt   = _esc(format_name or grant_data.get("format_used", ""))
    now   = datetime.now().strftime("%B %d, %Y")

    # ── Preamble ──────────────────────────────────────────────────────────────
    doc = (
        "\\documentclass[12pt,a4paper]{article}\n"
        "\n"
        "% --- Encoding & fonts ---\n"
        "\\usepackage[T1]{fontenc}\n"
        "\\usepackage[utf8]{inputenc}\n"
        "\\usepackage{lmodern}\n"
        "\n"
        "% --- Layout ---\n"
        "\\usepackage[top=2.5cm,bottom=2.5cm,left=3cm,right=3cm]{geometry}\n"
        "\\usepackage{setspace}\n"
        "\\usepackage{parskip}\n"
        "\n"
        "% --- Section formatting ---\n"
        "\\usepackage[explicit]{titlesec}\n"
        "\\usepackage{xcolor}\n"
        "\\definecolor{sectionblue}{RGB}{26,58,110}\n"
        "\\titleformat{\\section}{\\large\\bfseries\\color{sectionblue}}"
        "{\\thesection}{1em}{#1\\enspace\\leaders\\hrule height 0.4pt\\hfill\\kern0pt}\n"
        "\\titleformat{\\subsection}{\\normalsize\\bfseries\\color{sectionblue!80}}"
        "{\\thesubsection}{1em}{#1}\n"
        "\n"
        "% --- Math & science ---\n"
        "\\usepackage{amsmath,amssymb,amsthm}\n"
        "\\usepackage{booktabs}\n"
        "\\usepackage{array}\n"
        "\n"
        "% --- Lists ---\n"
        "\\usepackage{enumitem}\n"
        "\n"
        "% --- Headers/footers ---\n"
        "\\usepackage{fancyhdr}\n"
        "\\pagestyle{fancy}\n"
        "\\fancyhf{}\n"
        "\\lhead{\\small\\textit{Grant Proposal}}\n"
        "\\rhead{\\small\\textit{" + fmt + "}}\n"
        "\\cfoot{\\thepage}\n"
        "\n"
        "% --- Hyperlinks ---\n"
        "\\usepackage[colorlinks=true,linkcolor=sectionblue,urlcolor=sectionblue]{hyperref}\n"
        "\n"
        "\\onehalfspacing\n"
        "\n"
        "% =============================================================================\n"
        "\\begin{document}\n"
        "\n"
        "% --- Title page ---\n"
        "\\begin{titlepage}\n"
        "  \\centering\n"
        "  \\vspace*{3cm}\n"
        "  \\rule{\\linewidth}{1pt}\\\\[0.5cm]\n"
        "  {\\Huge\\bfseries\\color{sectionblue} " + title + " \\\\[0.4cm]}\n"
        "  \\rule{\\linewidth}{1pt}\\\\[1.5cm]\n"
        "  {\\large\\textit{Grant Proposal}}\\\\[0.4cm]\n"
        "  {\\large Format:\\;\\textbf{" + fmt + "}}\\\\[0.4cm]\n"
        "  {\\large " + now + "}\n"
        "  \\vfill\n"
        "\\end{titlepage}\n"
        "\n"
        "\\tableofcontents\n"
        "\\clearpage\n"
        "\n"
    )

    # ── Core sections (ordered) ───────────────────────────────────────────────
    for key, display in _CORE_SECTIONS:
        val = grant_data.get(key)
        if not val:
            continue
        doc += f"\\section{{{_esc(display)}}}\n"
        doc += _section_body_latex(val) + "\n\n"

    # ── Any unexpected top-level keys ─────────────────────────────────────────
    for key, val in grant_data.items():
        if key in _SKIP_KEYS:
            continue
        display = key.replace("_", " ").title()
        doc += f"\\section{{{_esc(display)}}}\n"
        doc += _section_body_latex(val) + "\n\n"

    # ── Funder-specific named sections (sections dict) ────────────────────────
    if "sections" in grant_data:
        for sec_title, sec_content in grant_data["sections"].items():
            doc += f"\\section{{{_esc(sec_title)}}}\n"
            doc += _section_body_latex(sec_content) + "\n\n"

    doc += "\\end{document}\n"
    return doc


# ══════════════════════════════════════════════════════════════════════════════
#  PDF generator (reportlab — pure Python, no LaTeX installation needed)
# ══════════════════════════════════════════════════════════════════════════════

def generate_pdf_bytes(grant_data: dict, topic: str, format_name: str = "") -> bytes:
    """Return PDF bytes with LaTeX-style academic formatting via reportlab."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import (
            BaseDocTemplate, Frame, PageTemplate,
            Paragraph, Spacer, HRFlowable, PageBreak,
        )
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
    except ImportError:
        raise RuntimeError(
            "reportlab is not installed. Run:  pip install reportlab"
        )

    buffer = io.BytesIO()

    DARK_BLUE = HexColor("#1a3a6e")
    MID_BLUE  = HexColor("#2563a8")
    RULE_CLR  = HexColor("#2563a8")
    BODY_CLR  = HexColor("#1a1a1a")

    W, H = A4
    margin_lr = 3.0 * cm
    margin_tb = 2.5 * cm
    top_margin = 3.2 * cm   # room for header line

    title_raw = grant_data.get("title", topic)
    fmt       = format_name or grant_data.get("format_used", "")
    now       = datetime.now().strftime("%B %d, %Y")

    # ── Styles ────────────────────────────────────────────────────────────────
    S = {
        "title": ParagraphStyle(
            "RL_Title",
            fontName="Times-Bold", fontSize=22, leading=28,
            textColor=DARK_BLUE, alignment=TA_CENTER, spaceAfter=10,
        ),
        "subtitle": ParagraphStyle(
            "RL_Subtitle",
            fontName="Times-Italic", fontSize=13, leading=18,
            textColor=MID_BLUE, alignment=TA_CENTER, spaceAfter=5,
        ),
        "meta": ParagraphStyle(
            "RL_Meta",
            fontName="Times-Roman", fontSize=11, leading=16,
            textColor=HexColor("#444444"), alignment=TA_CENTER, spaceAfter=4,
        ),
        "h1": ParagraphStyle(
            "RL_H1",
            fontName="Times-Bold", fontSize=13, leading=18,
            textColor=DARK_BLUE, spaceBefore=16, spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "RL_H2",
            fontName="Times-Bold", fontSize=11, leading=16,
            textColor=MID_BLUE, spaceBefore=10, spaceAfter=3,
        ),
        "body": ParagraphStyle(
            "RL_Body",
            fontName="Times-Roman", fontSize=11, leading=17,
            textColor=BODY_CLR, alignment=TA_JUSTIFY,
            spaceAfter=7, firstLineIndent=0,
        ),
        "bullet": ParagraphStyle(
            "RL_Bullet",
            fontName="Times-Roman", fontSize=11, leading=16,
            textColor=BODY_CLR, leftIndent=18, spaceAfter=3,
        ),
    }

    # ── Page callbacks (header + footer drawn on every page except title) ─────
    def _draw_header_footer(canvas, doc):
        page_num = canvas.getPageNumber()
        if page_num <= 1:
            return
        canvas.saveState()
        canvas.setFont("Times-Italic", 9)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawString(margin_lr, H - 1.8 * cm, "Grant Proposal")
        canvas.drawRightString(W - margin_lr, H - 1.8 * cm, fmt)
        canvas.setStrokeColor(HexColor("#cccccc"))
        canvas.line(margin_lr, H - 2.0 * cm, W - margin_lr, H - 2.0 * cm)
        canvas.line(margin_lr, 1.8 * cm, W - margin_lr, 1.8 * cm)
        canvas.setFont("Times-Roman", 9)
        canvas.setFillColor(HexColor("#555555"))
        canvas.drawCentredString(W / 2, 1.3 * cm, str(page_num))
        canvas.restoreState()

    frame = Frame(
        margin_lr, margin_tb,
        W - 2 * margin_lr, H - margin_tb - top_margin,
        id="main",
    )
    pt = PageTemplate(id="main", frames=[frame], onPage=_draw_header_footer)
    doc = BaseDocTemplate(
        buffer,
        pagesize=A4,
        pageTemplates=[pt],
    )

    story = []

    # ── Title page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE, spaceAfter=6))
    story.append(Paragraph(title_raw, S["title"]))
    story.append(HRFlowable(width="100%", thickness=2, color=DARK_BLUE, spaceBefore=6))
    story.append(Spacer(1, 1.2 * cm))
    story.append(Paragraph("Grant Proposal", S["subtitle"]))
    if fmt:
        story.append(Paragraph(f"Format: <b>{fmt}</b>", S["meta"]))
    story.append(Paragraph(now, S["meta"]))
    story.append(PageBreak())

    # ── Content helpers ───────────────────────────────────────────────────────
    def _xml_safe(text: str) -> str:
        return (
            str(text)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    def _add_content(content):
        if isinstance(content, list):
            for item in content:
                story.append(Paragraph(f"\u2022\u2002{_xml_safe(str(item))}", S["bullet"]))
            story.append(Spacer(1, 0.15 * cm))
        elif isinstance(content, dict):
            for k, v in content.items():
                story.append(Paragraph(_xml_safe(k), S["h2"]))
                _add_content(v)
        else:
            raw = str(content).replace("\\n", "\n")
            for para in raw.split("\n\n"):
                para = para.strip()
                if para:
                    story.append(Paragraph(_xml_safe(para), S["body"]))

    def add_section(display: str, content):
        story.append(Paragraph(display, S["h1"]))
        story.append(
            HRFlowable(
                width="100%", thickness=0.6,
                color=RULE_CLR, spaceAfter=5,
            )
        )
        _add_content(content)

    # ── Core ordered sections ─────────────────────────────────────────────────
    for key, display in _CORE_SECTIONS:
        val = grant_data.get(key)
        if not val:
            continue
        add_section(display, val)

    # ── Extra top-level keys ──────────────────────────────────────────────────
    for key, val in grant_data.items():
        if key in _SKIP_KEYS:
            continue
        add_section(key.replace("_", " ").title(), val)

    # ── Funder-specific sections ──────────────────────────────────────────────
    if "sections" in grant_data:
        for sec_title, sec_content in grant_data["sections"].items():
            add_section(sec_title, sec_content)

    doc.build(story)
    return buffer.getvalue()
