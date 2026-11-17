"""
agents/format_matcher.py
LLM-native grant format selection agent.
Sits between Agent 4 (Methodology) and Agent 5 (Grant Writing).
Takes topic + methodology summary + format summaries → selects best format_id.
"""

import os
import json
from utils.schema import safe_parse, call_gemini_with_retry
from utils.format_loader import format_summary_list


def run(
    topic: str,
    methodology: dict,
    formats: dict,
    user_override: str = None
) -> dict:
    """
    Select the most appropriate grant format for this topic and methodology.

    Args:
        topic:          The research topic string.
        methodology:    Agent 4 output dict (Schema 4).
        formats:        All loaded formats dict from format_loader.load_all_formats().
        user_override:  format_id string if the user picked manually in the UI.
                        If provided, skips LLM matching and returns directly.

    Returns:
        {
          "selected_format_id": "nsf_cise",
          "selected_format": { ...full format record... },
          "reasoning": "explanation of why this format was chosen",
          "llm_selected": true | false   (false if user override)
        }
    """
    print("[FormatMatcher] Selecting grant format")

    fallback_id = list(formats.keys())[0] if formats else None
    fallback = {
        "selected_format_id": fallback_id,
        "selected_format": formats.get(fallback_id, {}),
        "reasoning": "Fallback — format matching failed, used first available format.",
        "llm_selected": False,
    }

    # ── MOCK_MODE path ───────────────────────────────────────────────────────
    if os.getenv("MOCK_MODE", "").lower() == "true":
        mock_id = "nsf_cise" if "nsf_cise" in formats else fallback_id
        return {
            "selected_format_id": mock_id,
            "selected_format": formats.get(mock_id, {}),
            "reasoning": "Mock mode format selection.",
            "llm_selected": False,
        }

    # ── User override path ───────────────────────────────────────────────────
    if user_override:
        if user_override not in formats:
            print(
                f"[FormatMatcher] Warning: user override '{user_override}' not found in loaded "
                f"formats. Falling back to LLM selection."
            )
        else:
            chosen = formats[user_override]
            print(f"[FormatMatcher] User override accepted: {user_override}")
            return {
                "selected_format_id": user_override,
                "selected_format": chosen,
                "reasoning": "User selected this format manually.",
                "llm_selected": False,
            }

    # ── LLM matching path ────────────────────────────────────────────────────
    if not formats:
        print("[FormatMatcher] No formats loaded — cannot match.")
        return fallback

    summaries = format_summary_list(formats)

    # Extract a concise methodology summary to keep the prompt compact
    methodology_summary = {
        "experimental_design": methodology.get("experimental_design", ""),
        "evaluation_metrics": methodology.get("evaluation_metrics", []),
        "tools_and_frameworks": methodology.get("tools_and_frameworks", []),
    }

    sys_inst = """You are an expert research funding advisor.
Return ONLY valid JSON matching this schema:
{
  "selected_format_id": "the format_id string of the best matching format",
  "reasoning": "2-3 sentence explanation of why this format fits the topic, domain, and methodology"
}"""

    prompt = f"""Given a research topic, methodology summary, and a list of available grant formats,
select the single best-fitting grant format.

Consider:
- Domain alignment (domain_keywords vs topic words)
- Career stage appropriateness
- Rhetorical fit (exploratory vs established vs applied)
- Scale of the proposed research vs typical award size

Research Topic: {topic}

Methodology Summary: {json.dumps(methodology_summary, indent=2)}

Available Grant Formats:
{json.dumps(summaries, indent=2)}

Select the format_id that best fits. Return your selection and reasoning."""

    try:
        for attempt in range(2):
            try:
                response = call_gemini_with_retry(prompt, system_instruction=sys_inst)
                result = safe_parse(
                    response.text,
                    required_keys=["selected_format_id", "reasoning"]
                )

                selected_id = result.get("selected_format_id", "")
                if selected_id not in formats:
                    print(
                        f"[FormatMatcher] LLM returned unknown format_id '{selected_id}' "
                        f"— retrying or falling back."
                    )
                    if attempt == 1:
                        return fallback
                    continue

                chosen = formats[selected_id]
                print(f"[FormatMatcher] LLM selected: {selected_id} — {result.get('reasoning', '')}")
                return {
                    "selected_format_id": selected_id,
                    "selected_format": chosen,
                    "reasoning": result.get("reasoning", ""),
                    "llm_selected": True,
                }

            except Exception as e:
                if attempt == 1:
                    print(f"[FormatMatcher] Failed after retries: {e}")
                    return fallback

    except Exception as e:
        print(f"[FormatMatcher] Unexpected error: {e}")
        return fallback

    return fallback
