from __future__ import annotations

from pathlib import Path
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

from agents.contracts import BPMNEvidence
from agents.shared_tools.llm import get_chat_model

load_dotenv()

_CATEGORY_ORDER = ["syntax", "proposal", "semantics", "best_practices", "readability"]

_SYSTEM_PROMPT = """\
You are Agent 2, a BPMN evaluation specialist. Your role is to critically assess \
BPMN diagram evidence before applying penalties.

Before evaluating any item, you ALWAYS produce a structured analysis plan that:
1. Lists the categories present in the evidence, ordered by their pedagogical importance.
2. Highlights criteria that require closer attention (nao_cumprido elements).
3. Notes any patterns or risks across categories.

Be concise and specific. The plan guides the evaluation — it is not a final verdict.\
"""


def generate_analysis_plan(evidence_list: list[BPMNEvidence]) -> str:
    """Call the configured LLM once to produce a per-category analysis plan.

    Returns the plan as a plain string for storage in BPMNAssessment.plan_log.
    """
    client = get_chat_model()

    summary = _build_evidence_summary(evidence_list)

    response = client.with_config(max_tokens=1024).invoke(
        input=[
            {
                "role": "system",
                "content": (
                    _SYSTEM_PROMPT
                ),
            },
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
    return StrOutputParser().invoke(response)


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
        nao_cumprido = [e for e in items if e.status == "nao_cumprido"]
        nao_aplicavel = [e for e in items if e.status == "nao_aplicavel"]
        nao_avaliado = [e for e in items if e.status == "nao_avaliado"]
        cumprido = [e for e in items if e.status == "cumprido"]

        lines.append(f"\n[{category.upper()}] ({len(items)} criteria)")
        if nao_cumprido:
            lines.append(f"  NAO_CUMPRIDO ({len(nao_cumprido)}):")
            for e in nao_cumprido:
                obs = f" — {e.observation}" if e.observation else ""
                lines.append(f"    - [{e.criterion_id}] {e.question or e.element}{obs}")
        if nao_aplicavel:
            lines.append(f"  NAO_APLICAVEL ({len(nao_aplicavel)}): {', '.join(e.criterion_id for e in nao_aplicavel)}")
        if nao_avaliado:
            lines.append(f"  NAO_AVALIADO ({len(nao_avaliado)}): {', '.join(e.criterion_id for e in nao_avaliado)}")
        if cumprido:
            lines.append(f"  CUMPRIDO ({len(cumprido)}): {', '.join(e.criterion_id for e in cumprido)}")

    return "\n".join(lines)


if __name__ == "__main__":
    from agents.agent2_evaluator.loaders import load_evidence

    real_path = Path(__file__).parents[2] / "evaluation" / "results" / "BPMNEvidence.json"
    evidence = load_evidence(real_path)
    print(f"Loaded {len(evidence)} evidence items. Generating plan...\n")
    plan = generate_analysis_plan(evidence)
    print("=== ANALYSIS PLAN ===")
    print(plan)
