from __future__ import annotations

import os
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from agents.contracts import BPMNEvidence

load_dotenv()

_CATEGORY_ORDER = ["syntax", "proposal", "semantics", "best_practices", "readability"]

_SYSTEM_PROMPT = """\
You are Agent 2, a BPMN evaluation specialist. Your role is to critically assess \
BPMN diagram evidence before applying penalties.

Before evaluating any item, you ALWAYS produce a structured analysis plan that:
1. Lists the categories present in the evidence, ordered by their pedagogical importance.
2. Highlights criteria that require closer attention (absent or incorrect elements).
3. Notes any patterns or risks across categories.

Be concise and specific. The plan guides the evaluation — it is not a final verdict.\
"""


def generate_analysis_plan(evidence_list: list[BPMNEvidence]) -> str:
    """Call the Anthropic API once to produce a per-category analysis plan.

    Returns the plan as a plain string for storage in BPMNAssessment.plan_log.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("MODEL_NAME", "claude-opus-4-7")

    client = anthropic.Anthropic(api_key=api_key)

    summary = _build_evidence_summary(evidence_list)

    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    "Below is the evidence collected by Agent 1 for a BPMN diagram.\n"
                    "Produce a concise analysis plan: which categories to review, in what order, "
                    "and which criteria deserve priority attention.\n\n"
                    f"{summary}"
                ),
            }
        ],
    )

    return next(block.text for block in response.content if block.type == "text")


def _build_evidence_summary(evidence_list: list[BPMNEvidence]) -> str:
    """Summarise evidence grouped by category for the planning prompt."""
    from collections import defaultdict

    by_category: dict[str, list[BPMNEvidence]] = defaultdict(list)
    for item in evidence_list:
        by_category[item.category].append(item)

    lines: list[str] = ["EVIDENCE SUMMARY"]
    ordered_categories = [c for c in _CATEGORY_ORDER if c in by_category]
    ordered_categories += [c for c in by_category if c not in _CATEGORY_ORDER]

    for category in ordered_categories:
        items = by_category[category]
        absent = [e for e in items if e.status == "absent"]
        incorrect = [e for e in items if e.status == "incorrect"]
        present = [e for e in items if e.status == "present"]

        lines.append(f"\n[{category.upper()}] ({len(items)} criteria)")
        if absent:
            lines.append(f"  ABSENT ({len(absent)}):")
            for e in absent:
                lines.append(f"    - [{e.criterion_id}] {e.question or e.element}")
        if incorrect:
            lines.append(f"  INCORRECT ({len(incorrect)}):")
            for e in incorrect:
                obs = f" — {e.observation}" if e.observation else ""
                lines.append(f"    - [{e.criterion_id}] {e.question or e.element}{obs}")
        if present:
            lines.append(f"  PRESENT ({len(present)}): {', '.join(e.criterion_id for e in present)}")

    return "\n".join(lines)


if __name__ == "__main__":
    from agents.agent2_evaluator.loaders import load_evidence

    real_path = Path(__file__).parents[2] / "evaluation" / "results" / "BPMNEvidence.json"
    evidence = load_evidence(real_path)
    print(f"Loaded {len(evidence)} evidence items. Generating plan...\n")
    plan = generate_analysis_plan(evidence)
    print("=== ANALYSIS PLAN ===")
    print(plan)
