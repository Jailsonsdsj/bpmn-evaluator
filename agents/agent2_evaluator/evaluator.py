from __future__ import annotations

import json
import os
import re
from typing import Any

import anthropic
import structlog
from dotenv import load_dotenv

from agents.contracts import BPMNAssessment, BPMNEvidence

load_dotenv()

_SYSTEM_PROMPT = """\
You are Agent 2, a conservative critic-validator for BPMN diagram evaluations.

Your task is to validate findings produced by Agent 1 (the criteria mapper).
For each evidence item you will assess whether Agent 1's judgment is well-supported
by the available observation.

CRITICAL RULES:
- You NEVER decide or invent penalty values. Penalties come from the checklist.
- You ONLY assess criteria present in the input. Do not reference other elements.
- Be CONSERVATIVE with confidence. When in doubt, score below 0.6.
  Reserve 0.9+ for completely clear-cut cases with solid evidence.
  A genuinely uncertain judgment must score below 0.6 — do not inflate.
- You validate JUDGMENT ("is Agent 1 correct?"), not scoring.
- For status "present": confirm the element was correctly identified as present.
- For status "absent": confirm the element is truly missing, not just overlooked.
- For status "incorrect": confirm the incorrectness is well-documented.
- For status "not_applicable": confirm the criterion is genuinely out of scope.
"""


def evaluate_once(
    evidence_list: list[BPMNEvidence],
    checklist: dict[str, dict[str, Any]],
    plan: str,
) -> list[BPMNAssessment]:
    """Single-pass evaluation: validate each Agent 1 finding with one LLM call.

    Returns one BPMNAssessment per evidence item. plan_log is stored only on
    the first item. Does not loop — the Reflection loop wraps this function.
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
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = next(block.text for block in response.content if block.type == "text")
    llm_results = _parse_json_response(raw_text)
    llm_by_id = {r["criterion_id"]: r for r in llm_results}

    assessments: list[BPMNAssessment] = []
    for idx, evidence in enumerate(evidence_list):
        cid = evidence.criterion_id
        checklist_entry = checklist.get(cid, {})
        llm_entry = llm_by_id.get(cid, {})

        checklist_penalty = float(checklist_entry.get("checklist_penalty", 0.0))
        category_weight = float(checklist_entry.get("category_weight", 0.0))
        justification = llm_entry.get("justification", "No justification returned by model.")
        confidence = float(llm_entry.get("confidence", 0.0))

        applied_penalty = (
            0.0
            if evidence.status in ("present", "not_applicable")
            else checklist_penalty
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
            f"  Question : {e.question or '(not provided)'}",
            f"  Element  : {e.element or '(not provided)'}",
            f"  Observation: {obs}",
            "",
        ]
    return "\n".join(lines)


def _parse_json_response(text: str) -> list[dict[str, Any]]:
    # Strip markdown code fences if the model wrapped the output
    cleaned = re.sub(r"```(?:json)?\s*|\s*```", "", text).strip()
    try:
        result = json.loads(cleaned)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass
    # Fallback: extract the first [...] block
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return []


class Agent2Evaluator:
    """Agent 2: validates BPMNEvidence and produces BPMNAssessment.

    Uses a Planning + Reflection (Producer-Critic) loop to refine its output.
    The loop is not yet implemented — evaluate_once is called directly.
    # Note: real Agent 1 output contains only 'present' and 'absent'; 'incorrect'
    # and 'not_applicable' are handled by the contract but absent in current data.
    """

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)

    def run(self, evidence_list: list[BPMNEvidence]) -> list[BPMNAssessment]:
        """Evaluate evidence and return a list of BPMNAssessment instances.

        Stub — wiring to evaluate_once and the Reflection loop is a future task.
        """
        self.logger.info("agent2.start", total_evidence=len(evidence_list))
        assessments: list[BPMNAssessment] = []
        self.logger.info("agent2.finished", total_assessments=len(assessments))
        return assessments
