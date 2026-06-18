"""Tests for Agent 3 — deterministic grading, feedback coverage, student report.

All LLM calls are mocked; no network access required.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from agents.contracts import BPMNAssessment, BPMNFeedback, CategoryGrade, FeedbackItem
from agents.agent3_feedback.agent import Agent3Feedback
from agents.agent3_feedback.chains import COVERAGE_MARKER, render_grade_table
from agents.agent3_feedback.grading import compute_grades


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

DIAGRAM = {
    "id": "d1",
    "name": "Processo de teste",
    "elements": [
        {"id": "e1", "type": "startEvent", "name": "Início", "outgoing": ["f1"]},
        {"id": "t1", "type": "task", "name": "Tarefa", "incoming": ["f1"], "outgoing": ["f2"]},
        {"id": "e2", "type": "endEvent", "name": "Fim", "incoming": ["f2"]},
    ],
    "flows": [
        {"id": "f1", "source": "e1", "target": "t1"},
        {"id": "f2", "source": "t1", "target": "e2"},
    ],
}

ENUNCIADO = "Modele o processo de compra de materiais."


def make_assessment(
    criterion_id: str = "syntax_1",
    status: str = "nao_cumprido",
    applied_penalty: float = 0.20,
    category: str = "syntax",
    category_weight: float = 0.30,
    question: str = "O critério foi atendido?",
) -> BPMNAssessment:
    return BPMNAssessment(
        criterion_id=criterion_id,
        category=category,
        category_weight=category_weight,
        status=status,
        checklist_penalty=applied_penalty,
        applied_penalty=applied_penalty,
        justification="justificativa de teste",
        confidence=0.8,
        flag_review=False,
        element="elem",
        plan_log=None,
        question=question,
    )


def make_payload(assessments: list[BPMNAssessment]) -> dict:
    return {"diagram": DIAGRAM, "assessment": assessments, "enunciado": ENUNCIADO}


def report_with_markers(items_ids: list[str], final_grade: float, grades: list[CategoryGrade]) -> str:
    """A well-formed report: grade table verbatim + one marked section per error."""
    sections = "\n\n".join(
        f"{COVERAGE_MARKER.format(criterion_id=cid)}\n### Erro {cid}\nTexto." for cid in items_ids
    )
    return f"# Avaliação\n\n## Resultado\n\n{render_grade_table(final_grade, grades)}\n\n## Pontos a melhorar\n\n{sections}"


# ---------------------------------------------------------------------------
# Job 1 — deterministic grading (pure Python, no mocks)
# ---------------------------------------------------------------------------

class TestComputeGrades:
    def test_cumprido_does_not_subtract(self):
        final, grades = compute_grades([make_assessment(status="cumprido", applied_penalty=0.0)])
        assert final == pytest.approx(3.0)  # syntax max = 0.30 * 10
        assert grades[0].penalty == 0.0

    def test_nao_aplicavel_never_subtracts_even_with_penalty(self):
        # Real-world case: a bad upstream edit leaves applied_penalty > 0 on nao_aplicavel
        final, grades = compute_grades([make_assessment(status="nao_aplicavel", applied_penalty=0.4)])
        assert final == pytest.approx(3.0)
        assert grades[0].penalty == 0.0

    def test_nao_cumprido_subtracts_applied_penalty(self):
        final, grades = compute_grades([make_assessment(status="nao_cumprido", applied_penalty=0.8)])
        assert final == pytest.approx(2.2)
        assert grades[0].penalty == pytest.approx(0.8)
        assert grades[0].max_score == pytest.approx(3.0)

    def test_category_breakdown_and_final_grade(self):
        assessments = [
            make_assessment("syntax_1", "nao_cumprido", 0.5, "syntax", 0.30),
            make_assessment("syntax_2", "cumprido", 0.0, "syntax", 0.30),
            make_assessment("proposal_1", "nao_cumprido", 0.3, "proposal", 0.20),
            make_assessment("readability_1", "nao_aplicavel", 0.0, "readability", 0.10),
        ]
        final, grades = compute_grades(assessments)
        by_cat = {g.category: g for g in grades}
        assert by_cat["syntax"].score == pytest.approx(2.5)       # 3.0 - 0.5
        assert by_cat["proposal"].score == pytest.approx(1.7)     # 2.0 - 0.3
        assert by_cat["readability"].score == pytest.approx(1.0)  # 1.0 - 0
        assert final == pytest.approx(5.2)

    def test_category_score_floors_at_zero(self):
        assessments = [
            make_assessment(f"readability_{i}", "nao_cumprido", 0.8, "readability", 0.10)
            for i in range(3)  # 2.4 penalty > 1.0 max
        ]
        final, grades = compute_grades(assessments)
        assert grades[0].score == 0.0
        assert final == 0.0

    def test_categories_follow_checklist_order(self):
        assessments = [
            make_assessment("readability_1", category="readability", category_weight=0.10),
            make_assessment("syntax_1", category="syntax", category_weight=0.30),
        ]
        _, grades = compute_grades(assessments)
        assert [g.category for g in grades] == ["syntax", "readability"]


# ---------------------------------------------------------------------------
# Job 2 + Goal Monitoring + student report (LLM mocked)
# ---------------------------------------------------------------------------

@patch("agents.agent3_feedback.agent.get_chat_model")
@patch("agents.agent3_feedback.agent.student_report_chain")
@patch("agents.agent3_feedback.agent.map_assessment_chain")
class TestAgentRun:
    def test_one_feedback_item_per_error_even_with_zero_penalty(
        self, mock_chain, mock_report, mock_llm
    ):
        # nao_cumprido with applied_penalty=0 (human zeroed it) still gets feedback
        assessments = [
            make_assessment("syntax_1", "nao_cumprido", 0.5),
            make_assessment("syntax_2", "nao_cumprido", 0.0),
            make_assessment("syntax_3", "cumprido", 0.0),
            make_assessment("syntax_4", "nao_aplicavel", 0.0),
        ]
        mock_chain.return_value = "feedback gerado"
        mock_report.side_effect = lambda llm, e, t, items, s: report_with_markers(
            [it.criterion_id for it in items], *compute_grades(assessments)
        )
        feedback = Agent3Feedback().run(make_payload(assessments))

        assert [it.criterion_id for it in feedback.feedback_items] == ["syntax_1", "syntax_2"]
        assert mock_chain.call_count == 2
        assert all(it.feedback == "feedback gerado" for it in feedback.feedback_items)

    def test_coverage_retry_then_fallback(self, mock_chain, mock_report, mock_llm):
        # First call empty -> one retry; retry also empty -> deterministic fallback
        mock_chain.side_effect = ["", ""]
        mock_report.return_value = ""
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))

        assert mock_chain.call_count == 2
        item = feedback.feedback_items[0]
        assert item.feedback.strip()
        assert "justificativa de teste" in item.feedback

    def test_feedback_llm_exception_degrades_gracefully(self, mock_chain, mock_report, mock_llm):
        # An LLM exception on every feedback call must NOT crash the run: the
        # item falls back to the Agent 2 justification (retry also raises).
        mock_chain.side_effect = RuntimeError("rate limit")
        mock_report.return_value = ""
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))

        item = feedback.feedback_items[0]
        assert item.feedback.strip()
        assert "justificativa de teste" in item.feedback

    def test_report_llm_exception_degrades_to_deterministic(self, mock_chain, mock_report, mock_llm):
        # An exception from the student-report LLM must not crash the run; the
        # report is rebuilt deterministically (error section + official table).
        mock_chain.return_value = "feedback do erro"
        mock_report.side_effect = RuntimeError("network down")
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))

        assert COVERAGE_MARKER.format(criterion_id="syntax_1") in feedback.student_report
        assert "feedback do erro" in feedback.student_report
        assert f"**Nota final: {feedback.final_grade:.2f} / 10**" in feedback.student_report

    def test_strengths_collect_cumprido_questions(self, mock_chain, mock_report, mock_llm):
        mock_report.return_value = ""
        assessments = [
            make_assessment("syntax_1", "cumprido", 0.0, question="Eventos nomeados?"),
            make_assessment("syntax_2", "nao_aplicavel", 0.0, question="Mensagens entre pools?"),
        ]
        feedback = Agent3Feedback().run(make_payload(assessments))
        assert feedback.strengths == ["Eventos nomeados?"]

    def test_report_appends_missing_error_sections(self, mock_chain, mock_report, mock_llm):
        # LLM report omits the error section -> Python appends it from FeedbackItem
        mock_chain.return_value = "feedback do erro"
        mock_report.return_value = "# Avaliação\n\nRelatório sem a seção do erro."
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))

        marker = COVERAGE_MARKER.format(criterion_id="syntax_1")
        assert marker in feedback.student_report
        assert "feedback do erro" in feedback.student_report

    def test_report_restores_official_grade_table(self, mock_chain, mock_report, mock_llm):
        # LLM report mangles/omits the grade line -> authoritative table appended
        mock_report.return_value = "# Avaliação\n\nNota final: 9.99 / 10 (inventada)"
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))

        assert f"**Nota final: {feedback.final_grade:.2f} / 10**" in feedback.student_report

    def test_report_kept_verbatim_when_complete(self, mock_chain, mock_report, mock_llm):
        mock_chain.return_value = "feedback"
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        good = report_with_markers(["syntax_1"], *compute_grades(assessments))
        mock_report.return_value = good
        feedback = Agent3Feedback().run(make_payload(assessments))
        assert feedback.student_report == good

    def test_serialize_roundtrip_has_contract_fields(self, mock_chain, mock_report, mock_llm):
        mock_chain.return_value = "feedback"
        mock_report.return_value = ""
        assessments = [make_assessment("syntax_1", "nao_cumprido", 0.5)]
        feedback = Agent3Feedback().run(make_payload(assessments))
        data = json.loads(Agent3Feedback.serialize(feedback))
        for key in ("final_grade", "category_grades", "feedback_items", "strengths", "student_report"):
            assert key in data, f"missing field: {key}"


# ---------------------------------------------------------------------------
# run_from_files — file loading path
# ---------------------------------------------------------------------------

@patch("agents.agent3_feedback.agent.get_chat_model")
@patch("agents.agent3_feedback.agent.student_report_chain")
@patch("agents.agent3_feedback.agent.map_assessment_chain")
def test_run_from_files(mock_chain, mock_report, mock_llm, tmp_path):
    mock_chain.return_value = "feedback"
    mock_report.return_value = ""

    diagram_path = tmp_path / "diagram.json"
    diagram_path.write_text(json.dumps(DIAGRAM), encoding="utf-8")
    enunciado_path = tmp_path / "enunciado.txt"
    enunciado_path.write_text(ENUNCIADO, encoding="utf-8")
    assessment_path = tmp_path / "assessment.json"
    assessment_path.write_text(
        json.dumps({"assessments": [asdict(make_assessment("syntax_1", "nao_cumprido", 0.5))]}),
        encoding="utf-8",
    )

    feedback = Agent3Feedback().run_from_files(enunciado_path, diagram_path, assessment_path)
    assert isinstance(feedback, BPMNFeedback)
    assert feedback.final_grade == pytest.approx(2.5)
    assert feedback.feedback_items[0].criterion_id == "syntax_1"
