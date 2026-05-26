from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import anthropic
import structlog
from dotenv import load_dotenv

from agents.contracts import BPMNAssessment, BPMNEvidence

load_dotenv()

_STAGNATION_EPSILON = 0.001

_EVAL_SYSTEM_PROMPT = """\
You are Agent 2, a conservative critic-validator for BPMN diagram evaluations.

Your task is to validate findings produced by Agent 1 (the criteria mapper).
For each evidence item you will assess whether Agent 1's judgment is well-supported
by the available observation.

CRITICAL RULES:
- You NEVER decide or invent penalty values. Penalties come from the evidence contract.
- You ONLY assess criteria present in the input. Do not reference other elements.
- Be CONSERVATIVE with confidence. When in doubt, score below 0.6.
  Reserve 0.9+ for completely clear-cut cases with solid evidence.
  A genuinely uncertain judgment must score below 0.6 — do not inflate.
- You validate JUDGMENT ("is Agent 1 correct?"), not scoring.
- For status "cumprido": confirm the element was correctly identified as met.
- For status "nao_cumprido": confirm the criterion is truly unmet, not just overlooked.
- For status "nao_aplicavel": confirm the criterion is genuinely out of scope.
"""

_CRITIQUE_SYSTEM_PROMPT = """\
You are Agent 2 in self-critique mode. You are reviewing your own previous assessments.

For each item provided, ask:
  - Is the judgment (cumprido / nao_cumprido / nao_aplicavel) clearly supported?
  - Is the justification specific enough for a human reviewer to act on?
  - Is the confidence score calibrated honestly — not inflated?

CRITICAL RULES:
- Do NOT change the status. Only improve justification quality and recalibrate confidence.
- Do NOT invent penalties or change scoring. Penalties are not your concern.
- If the justification was already solid, keep confidence the same or raise it slightly.
- If there was genuine uncertainty, you may lower confidence to reflect that honestly.
- Be CONSERVATIVE: uncertain items must stay below 0.6.

Return a JSON array — one object per criterion_id — with exactly these keys:
  {"criterion_id": "...", "justification": "...", "confidence": 0.0}
Return ONLY the JSON array, no markdown fences, no extra text.
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_once(
    evidence_list: list[BPMNEvidence],
    checklist: dict[str, dict[str, Any]],
    plan: str,
) -> list[BPMNAssessment]:
    """Single-pass evaluation: validate each Agent 1 finding with one LLM call.

    checklist is used ONLY for category_weight — penalties come from evidence.value.
    Returns one BPMNAssessment per evidence item. plan_log is stored only on
    the first item. Does not loop — _reflect_loop wraps this function.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    model = os.getenv("MODEL_NAME", "claude-opus-4-7")
    threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))

    client = anthropic.Anthropic(api_key=api_key)
    logger = structlog.get_logger("evaluate_once")

    prompt = _build_evaluation_prompt(evidence_list, plan)
    logger.info("evaluate_once.llm_call", items=len(evidence_list), model=model)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_EVAL_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = next(block.text for block in response.content if block.type == "text")
    llm_results = _parse_json_response(raw_text)
    llm_by_id = {r["criterion_id"]: r for r in llm_results}

    assessments: list[BPMNAssessment] = []
    for idx, evidence in enumerate(evidence_list):
        cid = evidence.criterion_id
        # Checklist consulted only for category_weight; penalty comes from evidence.value
        checklist_entry = checklist.get(cid, {})
        llm_entry = llm_by_id.get(cid, {})

        checklist_penalty = evidence.value
        category_weight = float(checklist_entry.get("category_weight", 0.0))
        justification = llm_entry.get("justification", "No justification returned by model.")
        confidence = float(llm_entry.get("confidence", 0.0))

        applied_penalty = (
            0.0
            if evidence.status in ("cumprido", "nao_aplicavel")
            else checklist_penalty  # nao_cumprido
        )

        assessments.append(
            BPMNAssessment(
                criterion_id=cid,
                category=evidence.category,
                category_weight=category_weight,
                status=evidence.status,
                checklist_penalty=checklist_penalty,
                applied_penalty=applied_penalty,
                justification=justification,
                confidence=confidence,
                flag_review=confidence < threshold,
                plan_log=plan if idx == 0 else None,
            )
        )

    logger.info(
        "evaluate_once.done",
        total=len(assessments),
        flagged=sum(1 for a in assessments if a.flag_review),
    )
    return assessments


# ---------------------------------------------------------------------------
# Reflection loop
# ---------------------------------------------------------------------------

def _reflect_loop(
    evidence_list: list[BPMNEvidence],
    checklist: dict[str, dict[str, Any]],
    plan: str,
    client: anthropic.Anthropic,
    model: str,
    threshold: float,
    max_iterations: int,
) -> tuple[list[BPMNAssessment], list[dict[str, Any]]]:
    """Producer-Critic loop wrapping evaluate_once.

    Each iteration reviews weak items (confidence < threshold) and refines them.
    Stops when threshold is reached, max_iterations is exhausted, or confidence
    stagnates. Penalties are never touched across iterations.
    """
    logger = structlog.get_logger("reflect_loop")
    evidence_by_id = {e.criterion_id: e for e in evidence_list}
    iteration_log: list[dict[str, Any]] = []

    # --- Iteration 1: full evaluation pass ---
    assessments = evaluate_once(evidence_list, checklist, plan)
    avg_conf = _avg_confidence(assessments)
    weak = [a for a in assessments if a.confidence < threshold]

    stop_reason = _check_stop(1, avg_conf, None, max_iterations, threshold, len(weak))
    iteration_log.append({
        "iteration": 1,
        "avg_confidence": round(avg_conf, 4),
        "items_total": len(assessments),
        "items_weak": len(weak),
        "items_refined": [],
        "stop_reason": stop_reason,
    })
    logger.info(
        "reflect_loop.iteration",
        iteration=1,
        avg_confidence=round(avg_conf, 4),
        weak=len(weak),
        stop=stop_reason,
    )

    if stop_reason:
        return assessments, iteration_log

    # --- Iterations 2..N: critique weak items only ---
    prev_avg = avg_conf
    for iteration in range(2, max_iterations + 1):
        refined_ids = _critique_and_merge(
            assessments, weak, evidence_by_id, client, model, threshold
        )

        avg_conf = _avg_confidence(assessments)
        weak = [a for a in assessments if a.confidence < threshold]

        stop_reason = _check_stop(iteration, avg_conf, prev_avg, max_iterations, threshold, len(weak))
        iteration_log.append({
            "iteration": iteration,
            "avg_confidence": round(avg_conf, 4),
            "items_total": len(assessments),
            "items_weak": len(weak),
            "items_refined": refined_ids,
            "stop_reason": stop_reason,
        })
        logger.info(
            "reflect_loop.iteration",
            iteration=iteration,
            avg_confidence=round(avg_conf, 4),
            weak=len(weak),
            refined=len(refined_ids),
            stop=stop_reason,
        )

        if stop_reason:
            break
        prev_avg = avg_conf

    # Recompute flag_review on final assessments with final confidence values
    for a in assessments:
        object.__setattr__(a, "flag_review", a.confidence < threshold) if hasattr(a, "__dataclass_fields__") else None

    # Dataclass is not frozen so direct assignment works
    for a in assessments:
        a.flag_review = a.confidence < threshold

    return assessments, iteration_log


def _critique_and_merge(
    assessments: list[BPMNAssessment],
    weak: list[BPMNAssessment],
    evidence_by_id: dict[str, BPMNEvidence],
    client: anthropic.Anthropic,
    model: str,
    threshold: float,
) -> list[str]:
    """Run one critique pass on weak items; mutate assessments in-place.

    Returns list of criterion_ids that were refined.
    """
    if not weak:
        return []

    prompt = _build_critique_prompt(weak, evidence_by_id)
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=_CRITIQUE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = next(block.text for block in response.content if block.type == "text")
    refined_results = _parse_json_response(raw_text)
    refined_by_id = {r["criterion_id"]: r for r in refined_results}

    # Index assessments for fast lookup
    assess_by_id = {a.criterion_id: a for a in assessments}
    refined_ids: list[str] = []

    for cid, refined in refined_by_id.items():
        if cid not in assess_by_id:
            continue
        a = assess_by_id[cid]
        new_justification = refined.get("justification", a.justification)
        new_confidence = float(refined.get("confidence", a.confidence))

        # Mutate in-place — penalties and status are never touched
        a.justification = new_justification
        a.confidence = new_confidence
        a.flag_review = new_confidence < threshold
        refined_ids.append(cid)

    return refined_ids


def _check_stop(
    iteration: int,
    avg_conf: float,
    prev_avg: float | None,
    max_iterations: int,
    threshold: float,
    n_weak: int,
) -> str | None:
    """Return stop reason string if any criterion is met, else None."""
    if avg_conf >= threshold:
        return "threshold_reached"
    if n_weak == 0:
        return "no_weak_items"
    if iteration >= max_iterations:
        return "max_iterations"
    if prev_avg is not None and abs(avg_conf - prev_avg) < _STAGNATION_EPSILON:
        return "stagnant"
    return None


def _avg_confidence(assessments: list[BPMNAssessment]) -> float:
    if not assessments:
        return 0.0
    return sum(a.confidence for a in assessments) / len(assessments)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def _build_evaluation_prompt(evidence_list: list[BPMNEvidence], plan: str) -> str:
    lines = [
        "ANALYSIS PLAN (produced in the planning step):",
        plan,
        "",
        "EVIDENCE FROM AGENT 1:",
        "For each item below, validate whether Agent 1's status is well-supported.",
        "Return a JSON array — one object per criterion_id — with exactly these keys:",
        '  {"criterion_id": "...", "justification": "...", "confidence": 0.0}',
        "Return ONLY the JSON array, no markdown fences, no extra text.",
        "",
    ]
    for e in evidence_list:
        obs = e.observation or "(none)"
        lines += [
            f"[{e.criterion_id}] status={e.status.upper()}",
            f"  Question   : {e.question or '(not provided)'}",
            f"  Element    : {e.element or '(not provided)'}",
            f"  Observation: {obs}",
            "",
        ]
    return "\n".join(lines)


def _build_critique_prompt(
    weak: list[BPMNAssessment],
    evidence_by_id: dict[str, BPMNEvidence],
) -> str:
    lines = [
        "Review the following low-confidence assessments.",
        "For each item: improve the justification if possible and recalibrate confidence.",
        "Do NOT change the status. Do NOT touch penalties.",
        "",
        "ITEMS TO REVIEW:",
        "",
    ]
    for a in weak:
        evidence = evidence_by_id.get(a.criterion_id)
        obs = (evidence.observation if evidence else None) or "(none)"
        question = (evidence.question if evidence else None) or "(not provided)"
        element = (evidence.element if evidence else None) or "(not provided)"
        lines += [
            f"[{a.criterion_id}] status={a.status.upper()}  current_confidence={a.confidence:.2f}",
            f"  Question        : {question}",
            f"  Element         : {element}",
            f"  Observation     : {obs}",
            f"  Current justif. : {a.justification}",
            "",
        ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_response(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


# ---------------------------------------------------------------------------
# Agent class
# ---------------------------------------------------------------------------

class Agent2Evaluator:
    """Agent 2: validates BPMNEvidence and produces BPMNAssessment.

    Full pipeline: load checklist → generate plan → reflection loop → flag → serialize.
    After run(), iteration_log contains the per-iteration convergence record.
    """

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.iteration_log: list[dict[str, Any]] = []

    def run(
        self,
        evidence_list: list[BPMNEvidence],
        checklist_path: str | Path,
        output_path: str | Path | None = None,
    ) -> list[BPMNAssessment]:
        """Execute the full Agent 2 pipeline and return final assessments.

        Steps: load checklist → generate plan → reflection loop → flag → serialize.
        Writes JSON output to output_path when provided.
        """
        from agents.agent2_evaluator.loaders import load_checklist
        from agents.agent2_evaluator.planning import generate_analysis_plan

        api_key = os.getenv("ANTHROPIC_API_KEY")
        model = os.getenv("MODEL_NAME", "claude-opus-4-7")
        threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
        max_iterations = int(os.getenv("MAX_ITERATIONS", "3"))

        client = anthropic.Anthropic(api_key=api_key)

        self.logger.info(
            "agent2.start",
            total_evidence=len(evidence_list),
            threshold=threshold,
            max_iterations=max_iterations,
        )

        # Load → Plan
        checklist = load_checklist(checklist_path)
        self.logger.info("agent2.checklist_loaded", keys=len(checklist))

        plan = generate_analysis_plan(evidence_list)
        self.logger.info("agent2.plan_generated", plan_length=len(plan))

        # Reflection loop
        assessments, self.iteration_log = _reflect_loop(
            evidence_list, checklist, plan, client, model, threshold, max_iterations
        )

        # Flag — recompute flag_review from final confidence values
        for a in assessments:
            a.flag_review = a.confidence < threshold

        # Plan log on first item
        if assessments:
            assessments[0].plan_log = plan

        final_avg = _avg_confidence(assessments)
        self.logger.info(
            "agent2.finished",
            total_assessments=len(assessments),
            final_avg_confidence=round(final_avg, 4),
            iterations=len(self.iteration_log),
            flagged=sum(1 for a in assessments if a.flag_review),
        )

        # Serialize
        if output_path is not None:
            output = build_output(assessments, self.iteration_log)
            Path(output_path).write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.logger.info("agent2.output_written", path=str(output_path))

        return assessments


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------

def build_output(
    assessments: list[BPMNAssessment],
    iteration_log: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the JSON-serializable output dict matching the mock structure."""
    from collections import Counter

    status_counts = Counter(a.status for a in assessments)
    items_for_review = [a.criterion_id for a in assessments if a.flag_review]
    total_applied = round(sum(a.applied_penalty for a in assessments), 4)
    final_avg = round(_avg_confidence(assessments), 4)
    stop_reason = iteration_log[-1]["stop_reason"] if iteration_log else None

    summary: dict[str, Any] = {
        "total_criteria": len(assessments),
        "status_counts": {
            "cumprido": status_counts.get("cumprido", 0),
            "nao_cumprido": status_counts.get("nao_cumprido", 0),
            "nao_aplicavel": status_counts.get("nao_aplicavel", 0),
        },
        "items_for_review": items_for_review,
        "total_applied_penalty": total_applied,
        "iterations_ran": len(iteration_log),
        "final_avg_confidence": final_avg,
        "stop_reason": stop_reason,
    }

    return {
        "summary": summary,
        "assessments": [asdict(a) for a in assessments],
    }
