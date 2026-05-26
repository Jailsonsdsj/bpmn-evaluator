from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import langchain_google_genai
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import RunnableConfig
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
    client: ChatAnthropic | ChatGoogleGenerativeAI | None = None,
    model: str | None = None,
) -> list[BPMNAssessment]:
    """Single-pass evaluation: validate each Agent 1 finding with one LLM call.

    checklist is used ONLY for category_weight — penalties come from evidence.value.
    client and model may be injected (used by _reflect_loop and tests); when None
    they are loaded from env. Returns empty list immediately for empty input.
    """
    if not evidence_list:
        return []

    if model is None:
        model = os.getenv("MODEL_NAME", "claude-opus-4-7")
    if client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key:
            client = ChatAnthropic(model_name=model, timeout=None, stop=[])
        else:
            client = ChatGoogleGenerativeAI(model=os.getenv("MODEL_NAME", "").strip(), temperature=0.7)
    threshold = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    logger = structlog.get_logger("evaluate_once")

    logger.info("evaluate_once.llm_call", items=len(evidence_list), model=model)

    prompt = _build_evaluation_prompt(evidence_list, plan)
    llm_results = _call_llm_json(
        client, model, _EVAL_SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        logger, context="evaluate_once",
    )
    llm_by_id = {r["criterion_id"]: r for r in llm_results}

    assessments: list[BPMNAssessment] = []
    for idx, evidence in enumerate(evidence_list):
        cid = evidence.criterion_id
        checklist_entry = checklist.get(cid)
        if checklist_entry is None:
            logger.warning("evaluate_once.missing_checklist_entry", criterion_id=cid)
        checklist_entry = checklist_entry or {}

        llm_entry = llm_by_id.get(cid, {})
        checklist_penalty = 1.0 - evidence.value # Aplica penalidade
        category_weight = float(checklist_entry.get("category_weight", 0.0))
        checklist_penalty = evidence.value
        category_weight = float(checklist_entry.get("category_weight", 0.001))
        justification = llm_entry.get("justification", "No justification returned by model.")
        confidence = float(llm_entry.get("confidence", 0.001))

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
                element=evidence_list[idx].element,
                question=evidence_list[idx].question
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
    client: ChatAnthropic | ChatGoogleGenerativeAI,
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

    # Iteration 1: full evaluation pass; inject client so tests can mock both calls
    assessments = evaluate_once(evidence_list, checklist, plan, client=client, model=model)
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

    # Iterations 2..N: critique weak items only
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

    return assessments, iteration_log


def _critique_and_merge(
    assessments: list[BPMNAssessment],
    weak: list[BPMNAssessment],
    evidence_by_id: dict[str, BPMNEvidence],
    client: ChatAnthropic | ChatGoogleGenerativeAI,
    model: str,
    threshold: float,
) -> list[str]:
    """Run one critique pass on weak items; mutate assessments in-place.

    Returns list of criterion_ids that were refined.
    """
    if not weak:
        return []

    logger = structlog.get_logger("critique_and_merge")
    logger.info("critique.llm_call", weak_items=len(weak))

    prompt = _build_critique_prompt(weak, evidence_by_id)
    refined_results = _call_llm_json(
        client, model, _CRITIQUE_SYSTEM_PROMPT,
        [{"role": "user", "content": prompt}],
        logger, context="critique",
    )
    refined_by_id = {r["criterion_id"]: r for r in refined_results}

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
# LLM helper — retry once on JSON parse failure
# ---------------------------------------------------------------------------

def _call_llm_json(
    client: ChatAnthropic | ChatGoogleGenerativeAI,
    model: str,
    system: str,
    messages: list[dict[str, Any]],
    logger: Any,
    context: str = "",
) -> list[dict[str, Any]]:
    """Call the LLM and parse the JSON response. Retries once on parse failure."""
    for attempt in range(2):
        response = client.with_config(max_tokens=4096).invoke(
            input=[{"role": "system", "content": system}]+messages,
        )
        results = JsonOutputParser().invoke(response)
        if results:
            if attempt > 0:
                logger.info("llm.json_retry_success", context=context)
            return results
        logger.warning(
            "llm.invalid_json",
            attempt=attempt + 1,
            context=context,
            preview=str(results)[:200],
        )

    logger.error("llm.json_parse_failed_after_retry", context=context)
    return []


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
# Serialization
# ---------------------------------------------------------------------------

def build_output(
    assessments: list[BPMNAssessment],
    iteration_log: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the JSON-serializable output dict matching the mock structure."""
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
        if api_key:
            client = ChatAnthropic(model_name=model, timeout=None, stop=[])
        else:
            client = ChatGoogleGenerativeAI(model=os.getenv("MODEL_NAME", "").strip(), temperature=0.7)

        self.logger.info(
            "agent2.start",
            total_evidence=len(evidence_list),
            threshold=threshold,
            max_iterations=max_iterations,
        )

        checklist = load_checklist(checklist_path)
        self.logger.info("agent2.checklist_loaded", keys=len(checklist))

        plan = generate_analysis_plan(evidence_list)
        self.logger.info("agent2.plan_generated", plan_length=len(plan))

        assessments, self.iteration_log = _reflect_loop(
            evidence_list, checklist, plan, client, model, threshold, max_iterations
        )

        # Final flag_review pass after loop completes
        for a in assessments:
            a.flag_review = a.confidence < threshold

        # plan_log on first item only
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

        if output_path is not None:
            output = build_output(assessments, self.iteration_log)
            Path(output_path).write_text(
                json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            self.logger.info("agent2.output_written", path=str(output_path))

        return assessments
