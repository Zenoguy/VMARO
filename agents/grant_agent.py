"""
agents/grant_agent.py  (updated — Agent 5)
Now receives a selected_format dict from FormatMatcher and adapts
its system prompt and section structure accordingly.
"""

import os
import json
from utils.schema import safe_parse, call_gemini_with_retry


def _build_section_instructions(sections: list) -> str:
    """Render section specs into a compact instruction block for the system prompt."""
    lines = []
    for s in sections:
        limit_str = ""
        if s.get("max_words"):
            limit_str = f"max {s['max_words']} words"
        elif s.get("max_pages"):
            limit_str = f"max {s['max_pages']} pages"
        req_str = "REQUIRED" if s.get("required") else "optional"
        notes_str = f" — {s['notes']}" if s.get("notes") else ""
        lines.append(f"  • {s['name']} [{req_str}]{', ' + limit_str if limit_str else ''}{notes_str}")
    return "\n".join(lines)


def run(topic: str, gap_description: str, methodology: dict, format_selection: dict = None) -> dict:
    """
    Generate a grant proposal shaped by the selected grant format.

    Args:
        topic:            Research topic string.
        gap_description:  The selected gap from Agent 3.
        methodology:      Agent 4 output (Schema 4).
        format_selection: FormatMatcher output containing 'selected_format' dict.

    Returns:
        Schema 5 — grant proposal JSON, structured per the selected format.
    """
    print("[Agent5]       Grant Writing")

    if os.getenv("MOCK_MODE", "").lower() == "true":
        with open("mock_data/mock_grant.json") as f:
            return json.load(f)

    if not format_selection:
        format_selection = {}

    fallback = {
        "title": f"Research Proposal: {topic}",
        "problem_statement": gap_description,
        "proposed_solution": "",
        "methodology_summary": "",
        "expected_outcomes": [],
        "broader_impacts": "",
        "budget_justification": "",
        "format_used": "unknown",
        "sections": {}
    }

    try:
        selected_format = format_selection.get("selected_format", {})
        format_id = format_selection.get("selected_format_id", "unknown")
        format_name = selected_format.get("name", "Generic Grant Format")
        sections = selected_format.get("sections", [])
        emphasis = selected_format.get("emphasis", "")
        avoid = selected_format.get("avoid", "")
        tone = selected_format.get("rhetorical_tone", "Academic")

        section_instructions = _build_section_instructions(sections)

        # Build the section output schema dynamically from the format
        section_schema = {
            s["name"]: "string — content for this section"
            for s in sections
        }

        sys_inst = f"""You are an expert grant writer producing a proposal for the {format_name}.

RHETORICAL TONE: {tone}

WHAT REVIEWERS CARE ABOUT:
{emphasis}

WHAT TO AVOID:
{avoid if avoid else 'N/A'}

REQUIRED SECTIONS (write all required sections, include optional ones where appropriate):
{section_instructions}

Return ONLY valid JSON matching this schema:
{{
  "title": "Proposal title string",
  "problem_statement": "Clear statement of the research problem",
  "proposed_solution": "Summary of the proposed approach",
  "methodology_summary": "Brief methodology overview",
  "expected_outcomes": ["outcome 1", "outcome 2"],
  "broader_impacts": "Societal and scientific impact",
  "budget_justification": "High-level budget rationale",
  "format_used": "{format_id}",
  "sections": {json.dumps(section_schema, indent=2)}
}}

Write each section in the sections dict with full prose content appropriate for the {format_name}.
Respect word and page limits in the instructions above."""

        prompt = f"""Write a complete grant proposal for the following:

Research Topic: {topic}
Research Gap Being Addressed: {gap_description}
Proposed Methodology: {json.dumps(methodology, indent=2)}

Shape the proposal for the {format_name}. Follow all section requirements in your instructions."""

        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                result = safe_parse(
                    response.text,
                    required_keys=["title", "problem_statement", "sections"]
                )
                result["format_used"] = format_id
                print(f"[Agent5] Grant proposal generated using format: {format_id}")
                return result
            except Exception as e:
                if attempt == 1:
                    print(f"[Agent5] Grant generation failed: {e}")
                    raise

    except Exception as e:
        print(f"[Agent5] Unexpected error: {e}")
        fallback["format_used"] = format_selection.get("selected_format_id", "unknown")
        return fallback
