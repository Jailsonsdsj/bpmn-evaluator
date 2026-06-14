"""Tests for Agent 3 — feedback.

All LLM calls are mocked; no network access required.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from ..contracts import ItemGrade
from agents.contracts import BPMNAssessment, BPMNEvidence
from agents.agent3_feedback.agent import (
    Agent3Feedback
)
from agents.agent3_feedback.chains import *
from agents.agent3_feedback.cli import *


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def make_evidence(
    criterion_id: str = "syntax_1",
    status: str = "nao_cumprido",
    value: float = 0.20,
    category: str = "syntax",
) -> BPMNEvidence:
    return BPMNEvidence(
        criterion_id=criterion_id,
        category=category,
        status=status,
        value=value,
        element="elem",
        observation=None,
        question="Is this criterion met?",
    )


def make_assessment(
    criterion_id: str = "syntax_1",
    status: str = "nao_cumprido",
    checklist_penalty: float = 0.20,
    applied_penalty: float = 0.20,
    confidence: float = 0.50,
    category: str = "syntax",
) -> BPMNAssessment:
    return BPMNAssessment(
        criterion_id=criterion_id,
        category=category,
        category_weight=1.0,
        status=status,
        checklist_penalty=checklist_penalty,
        applied_penalty=applied_penalty,
        justification="test justification",
        confidence=confidence,
        flag_review=confidence < 0.6,
        plan_log=None,
        element="elem",
        question="Is this criterion met?",
    )
def make_assessments(assessment_args: list[BPMNAssessment]):
    assessments = [asdict(asseessment) for asseessment in assessment_args]
    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join("evaluation", "results", f"assessment_{ts}.json")
    with open(path, "w") as f:
        json.dump({"assessments": assessments}, f, indent=2)
    return path


def llm_response(results: list[dict]) -> MagicMock:
    """Return a mock anthropic API response whose content block holds the JSON list."""
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(results)
    response = MagicMock()
    response.content = [block]
    return response


def bad_response(text: str = "not valid json {{{") -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.content = [block]
    return response


DIAGRAM_PATH = "evaluation/dataset/diagram_001.json"
ENUNCIADO_PATH = "evaluation/dataset/Instruções.txt"

# ---------------------------------------------------------------------------
# Pure Python — no mocking required
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Tests with LLM mocking — applied_penalty rules
# ---------------------------------------------------------------------------

class TestAppliedPenalty:
    @patch("agents.agent3_feedback.agent.read_diagram_file")
    @patch("agents.agent3_feedback.agent.read_bpmnassessment_file")
    @patch("agents.agent3_feedback.agent.map_assessment_chain")
    @patch("agents.agent3_feedback.agent.get_chat_model")
    def test_cumprido_applied_grade_is_correct(self, mock_get_llm, mock_chain, mock_read_assessment, mock_read_diagram):
        mock_read_diagram.return_value = {"elements": [], "flows": []}
        mock_read_assessment.return_value = [make_assessment("syntax_1", "cumprido", checklist_penalty=0.20)]
        mock_chain.return_value = "Correto"
        
        agent = Agent3Feedback()
        feedbacks = agent.run_from_files(
            diagram_path=DIAGRAM_PATH, enunciado_path=ENUNCIADO_PATH, assessment_path="dummy"
        )
        assert feedbacks.grades_and_feedbacks[0][0].value == 1.0
        # cumprido items should have positive feedback, not "Sem problemas"
        assert "✓" in feedbacks.grades_and_feedbacks[0][1] or "Critério atendido" in feedbacks.grades_and_feedbacks[0][1]

    @patch("agents.agent3_feedback.agent.read_diagram_file")
    @patch("agents.agent3_feedback.agent.read_bpmnassessment_file")
    @patch("agents.agent3_feedback.agent.map_assessment_chain")
    @patch("agents.agent3_feedback.agent.get_chat_model")
    def test_mixed_statuses_in_one_call(self, mock_get_llm, mock_chain, mock_read_assessment, mock_read_diagram):
        mock_read_diagram.return_value = {"elements": [], "flows": []}
        
        assessments = [
            make_assessment("syntax_1",   "cumprido",     applied_penalty = 0.0),
            make_assessment("syntax_2",   "nao_cumprido", applied_penalty = 0.30),
            make_assessment("proposal_1", "nao_aplicavel", applied_penalty = 0.40),
        ]
        mock_read_assessment.return_value = assessments
        mock_chain.side_effect = [
            "não ok",  # For nao_cumprido item
        ]
        
        agent = Agent3Feedback()
        feedbacks = agent.run_from_files(
            diagram_path=DIAGRAM_PATH, enunciado_path=ENUNCIADO_PATH, assessment_path="dummy"
        )
        by_idx: list[ItemGrade] = [a[0] for a in feedbacks.grades_and_feedbacks]
        
        # cumprido: full score, positive message
        assert by_idx[0].value == pytest.approx(1.0)
        assert "✓" in feedbacks.grades_and_feedbacks[0][1] or "Critério atendido" in feedbacks.grades_and_feedbacks[0][1]
        
        # nao_cumprido: penalty applied, LLM feedback
        assert by_idx[1].value == pytest.approx(0.7)
        assert feedbacks.grades_and_feedbacks[1][1] == "não ok"
        
        # nao_aplicavel: no penalty, contextual message
        assert by_idx[2].value == pytest.approx(0.6)
        assert "não aplicável" in feedbacks.grades_and_feedbacks[2][1]
