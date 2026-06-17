"""Deterministic grade calculation for Agent 3 (Job 1 — no LLM).

The final grade and per-category breakdown come exclusively from the validated
``BPMNAssessment`` list: each category starts from its weighted share of the full
grade (weight × 10) and loses the ``applied_penalty`` of its ``nao_cumprido`` items.
``cumprido`` and ``nao_aplicavel`` items NEVER subtract points, even if a non-zero
``applied_penalty`` slipped through upstream — the status is authoritative.
"""
from __future__ import annotations

from agents.contracts import BPMNAssessment, CategoryGrade

FULL_GRADE = 10.0

# Canonical display order (checklist categories); unknown categories go last.
_CATEGORY_ORDER = ["syntax", "proposal", "semantics", "best_practices", "readability"]


def compute_grades(assessments: list[BPMNAssessment]) -> tuple[float, list[CategoryGrade]]:
    """Return ``(final_grade, per-category breakdown)`` for the assessments.

    The category weight is taken from the items themselves (``category_weight``).
    Scores are floored at 0 per category; the final grade is the sum of category
    scores (≤ 10 when the weights sum to 1).
    """
    by_category: dict[str, list[BPMNAssessment]] = {}
    for a in assessments:
        by_category.setdefault(a.category, []).append(a)

    ordered = [c for c in _CATEGORY_ORDER if c in by_category]
    ordered += [c for c in by_category if c not in _CATEGORY_ORDER]

    grades: list[CategoryGrade] = []
    for category in ordered:
        items = by_category[category]
        weight = items[0].category_weight
        max_score = round(weight * FULL_GRADE, 4)
        penalty = round(
            sum(a.applied_penalty for a in items if a.status == "nao_cumprido"), 4
        )
        score = round(max(0.0, max_score - penalty), 4)
        grades.append(
            CategoryGrade(
                category=category,
                weight=weight,
                max_score=max_score,
                penalty=penalty,
                score=score,
            )
        )

    final_grade = round(sum(g.score for g in grades), 4)
    return final_grade, grades
