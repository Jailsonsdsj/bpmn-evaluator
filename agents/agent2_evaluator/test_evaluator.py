"""Tests for Agent 2 — evaluator, reflection loop, and error handling.

All LLM calls are mocked; no network access required.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.contracts import BPMNAssessment, BPMNEvidence
from agents.agent2_evaluator.evaluator import (
    _avg_confidence,
    _check_stop,
    _parse_json_response,
    _reflect_loop,
    build_output,
    evaluate_once,
)


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
        category_weight=0.30,
        status=status,
        checklist_penalty=checklist_penalty,
        applied_penalty=applied_penalty,
        justification="test justification",
        confidence=confidence,
        flag_review=confidence < 0.6,
        plan_log=None,
        element="elem",
        question="?"
    )


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


CHECKLIST: dict = {
    "syntax_1":   {"category_weight": 0.30, "checklist_penalty": 0.20, "category": "syntax"},
    "syntax_2":   {"category_weight": 0.30, "checklist_penalty": 0.20, "category": "syntax"},
    "proposal_1": {"category_weight": 0.20, "checklist_penalty": 0.30, "category": "proposal"},
}


# ---------------------------------------------------------------------------
# Pure Python — no mocking required
# ---------------------------------------------------------------------------

class TestAvgConfidence:
    def test_empty_returns_zero(self):
        assert _avg_confidence([]) == 0.0

    def test_single_item(self):
        assert _avg_confidence([make_assessment(confidence=0.75)]) == pytest.approx(0.75)

    def test_multiple_items(self):
        items = [make_assessment(confidence=c) for c in [0.4, 0.6, 0.8]]
        assert _avg_confidence(items) == pytest.approx(0.6)


class TestCheckStop:
    def test_threshold_reached(self):
        assert _check_stop(1, 0.7, None, 3, 0.6, 5) == "threshold_reached"

    def test_no_weak_items(self):
        assert _check_stop(1, 0.5, None, 3, 0.6, 0) == "no_weak_items"

    def test_max_iterations(self):
        assert _check_stop(3, 0.4, 0.39, 3, 0.6, 5) == "max_iterations"

    def test_stagnant(self):
        # difference smaller than _STAGNATION_EPSILON (0.001)
        assert _check_stop(2, 0.4000, 0.4001, 3, 0.6, 5) == "stagnant"

    def test_no_stop_on_first_iteration(self):
        assert _check_stop(1, 0.4, None, 3, 0.6, 5) is None

    def test_no_stop_when_still_improving(self):
        assert _check_stop(2, 0.45, 0.35, 3, 0.6, 5) is None


class TestParseJsonResponse:
    def test_clean_json_array(self):
        text = '[{"criterion_id": "a", "confidence": 0.7, "justification": "ok"}]'
        result = _parse_json_response(text)
        assert len(result) == 1
        assert result[0]["criterion_id"] == "a"

    def test_strips_markdown_fences(self):
        text = '```json\n[{"criterion_id":"a","confidence":0.5,"justification":"x"}]\n```'
        assert len(_parse_json_response(text)) == 1

    def test_extracts_array_from_surrounding_prose(self):
        text = 'Here is the result:\n[{"criterion_id":"b","confidence":0.3,"justification":"y"}]'
        assert len(_parse_json_response(text)) == 1

    def test_returns_empty_on_invalid(self):
        assert _parse_json_response("not json at all {{") == []

    def test_returns_empty_on_empty_string(self):
        assert _parse_json_response("") == []


class TestBuildOutput:
    def test_has_required_top_level_keys(self):
        output = build_output([make_assessment()], [])
        assert "summary" in output
        assert "assessments" in output

    def test_summary_has_all_contract_fields(self):
        output = build_output([make_assessment()], [])
        s = output["summary"]
        for key in ("total_criteria", "status_counts", "items_for_review",
                    "total_applied_penalty", "iterations_ran", "final_avg_confidence",
                    "stop_reason"):
            assert key in s, f"missing summary key: {key}"

    def test_assessments_have_all_contract_fields(self):
        output = build_output([make_assessment()], [])
        item = output["assessments"][0]
        for field in ("criterion_id", "category", "category_weight", "status",
                      "checklist_penalty", "applied_penalty", "justification",
                      "confidence", "flag_review", "plan_log"):
            assert field in item, f"missing assessment field: {field}"

    def test_total_applied_penalty_matches_sum(self):
        items = [
            make_assessment("s1", "nao_cumprido", 0.20, 0.20, 0.3),
            make_assessment("s2", "cumprido",     0.20, 0.00, 0.8),
            make_assessment("s3", "nao_cumprido", 0.30, 0.30, 0.4),
        ]
        output = build_output(items, [])
        assert output["summary"]["total_applied_penalty"] == pytest.approx(0.50)

    def test_items_for_review_matches_flag_review(self):
        items = [
            make_assessment("s1", confidence=0.3),   # flagged
            make_assessment("s2", confidence=0.8),   # not flagged
            make_assessment("s3", confidence=0.59),  # flagged
        ]
        for a in items:
            a.flag_review = a.confidence < 0.6
        output = build_output(items, [])
        assert output["summary"]["items_for_review"] == ["s1", "s3"]

    def test_stop_reason_from_last_iteration_entry(self):
        log = [{"stop_reason": None}, {"stop_reason": "max_iterations"}]
        output = build_output([make_assessment()], log)
        assert output["summary"]["stop_reason"] == "max_iterations"


# ---------------------------------------------------------------------------
# Tests with LLM mocking — applied_penalty rules
# ---------------------------------------------------------------------------

class TestAppliedPenalty:
    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_cumprido_applied_penalty_is_zero(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "cumprido", value=0.20)], CHECKLIST, "plan"
        )
        assert assessments[0].applied_penalty == 0.0

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_nao_aplicavel_applied_penalty_is_zero(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.9}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.9}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "nao_aplicavel", value=0.20)], CHECKLIST, "plan"
        )
        assert assessments[0].applied_penalty == 0.0

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_nao_cumprido_applied_penalty_equals_value(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "missing", "confidence": 0.7}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "missing", "confidence": 0.7}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "nao_cumprido", value=0.20)], CHECKLIST, "plan"
        )
        assert assessments[0].applied_penalty == pytest.approx(0.20)

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_checklist_penalty_comes_from_evidence_value_not_checklist_dict(self, mock_cls: MagicMock, mock_json: MagicMock):
        """evidence.value=0.35 wins over CHECKLIST dict's 0.20."""
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.5}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.5}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "nao_cumprido", value=0.35)], CHECKLIST, "plan"
        )
        assert assessments[0].checklist_penalty == pytest.approx(0.35)
        assert assessments[0].applied_penalty == pytest.approx(0.35)

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_mixed_statuses_in_one_call(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response([
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8},
            {"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.7},
            {"criterion_id": "proposal_1", "justification": "ok", "confidence": 0.9},
        ])
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8},
            {"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.7},
            {"criterion_id": "proposal_1", "justification": "ok", "confidence": 0.9},
        ]
        evidence = [
            make_evidence("syntax_1",   "cumprido",     value=0.20),
            make_evidence("syntax_2",   "nao_cumprido", value=0.20),
            make_evidence("proposal_1", "nao_aplicavel", value=0.30),
        ]
        assessments = evaluate_once(evidence, CHECKLIST, "plan")
        by_id = {a.criterion_id: a for a in assessments}
        assert by_id["syntax_1"].applied_penalty == 0.0
        assert by_id["syntax_2"].applied_penalty == pytest.approx(0.20)
        assert by_id["proposal_1"].applied_penalty == 0.0


# ---------------------------------------------------------------------------
# Tests with LLM mocking — flag_review rules
# ---------------------------------------------------------------------------

class TestFlagReview:
    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_flag_true_below_threshold(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.59}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.59}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "nao_cumprido")], CHECKLIST, "plan"
        )
        assert assessments[0].confidence == 0.59
        assert assessments[0].flag_review is True

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_flag_false_at_threshold(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.6}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.6}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "cumprido")], CHECKLIST, "plan"
        )
        assert assessments[0].flag_review is False


    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_flag_false_above_threshold(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.95}]
        )
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.95}
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "cumprido")], CHECKLIST, "plan"
        )
        assert assessments[0].flag_review is False

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_flag_review_consistent_with_confidence_for_all_items(self, mock_cls: MagicMock, mock_json: MagicMock):
        mock_cls.return_value.invoke.return_value = llm_response([
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.3},
            {"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.8},
        ])
        
        mock_json.return_value = [
            {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.3},
            {"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.8},
        ]
        evidence = [
            make_evidence("syntax_1", "nao_cumprido"),
            make_evidence("syntax_2", "cumprido"),
        ]
        assessments = evaluate_once(evidence, CHECKLIST, "plan")
        by_id = {a.criterion_id: a for a in assessments}
        assert by_id["syntax_1"].flag_review is True
        assert by_id["syntax_2"].flag_review is False


# ---------------------------------------------------------------------------
# Tests for the reflection loop
# ---------------------------------------------------------------------------

class TestReflectLoop:
    def _mock_client(self, results: list[dict]) -> MagicMock:
        client = MagicMock()
        client.invoke.return_value = llm_response(results)
        return client

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_loop_stops_at_max_iterations(self, mock_json: MagicMock):
        client = self._mock_client(
            [{"criterion_id": "syntax_1", "justification": "uncertain", "confidence": 0.2}]
        )
        mock_json.return_value = [{"criterion_id": "syntax_1", "justification": "uncertain", "confidence": 0.2}]
        evidence = [make_evidence("syntax_1", "nao_cumprido")]
        _, log = _reflect_loop(evidence, CHECKLIST, "plan", client, "model", 0.6, 2)

        assert len(log) <= 2
        assert log[-1]["stop_reason"] == "max_iterations"

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_loop_never_exceeds_max_iterations(self, mock_json: MagicMock):
        for max_iter in (1, 2, 3):
            client = self._mock_client(
                [{"criterion_id": "syntax_1", "justification": "low", "confidence": 0.1}]
            )
            mock_json.return_value = [{"criterion_id": "syntax_1", "justification": "low", "confidence": 0.1}]
            evidence = [make_evidence("syntax_1", "nao_cumprido")]
            _, log = _reflect_loop(evidence, CHECKLIST, "plan", client, "model", 0.6, max_iter)
            assert len(log) <= max_iter, f"exceeded max_iterations={max_iter}"

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_loop_stops_when_threshold_reached(self, mock_json: MagicMock):
        client = self._mock_client(
            [{"criterion_id": "syntax_1", "justification": "solid", "confidence": 0.9}]
        )
        mock_json.return_value = [{"criterion_id": "syntax_1", "justification": "solid", "confidence": 0.9}]
        evidence = [make_evidence("syntax_1", "cumprido")]
        _, log = _reflect_loop(evidence, CHECKLIST, "plan", client, "model", 0.6, 5)

        assert log[-1]["stop_reason"] == "threshold_reached"
        assert len(log) == 1  # stops immediately on iteration 1

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_loop_stops_on_stagnation(self, mock_json: MagicMock):
        # Same confidence on every call — stagnation fires on iteration 2
        client = self._mock_client(
            [{"criterion_id": "syntax_1", "justification": "same", "confidence": 0.3}]
        )
        mock_json.return_value = [{"criterion_id": "syntax_1", "justification": "same", "confidence": 0.3}]
        evidence = [make_evidence("syntax_1", "nao_cumprido")]
        _, log = _reflect_loop(evidence, CHECKLIST, "plan", client, "model", 0.6, 10)

        stop_reasons = {e["stop_reason"] for e in log if e["stop_reason"]}
        assert stop_reasons <= {"stagnant", "max_iterations", "no_weak_items"}
        # Should not run all 10 iterations
        assert len(log) < 10

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_penalties_never_mutated_across_iterations(self, mock_json: MagicMock):
        client = self._mock_client(
            [{"criterion_id": "syntax_1", "justification": "refined", "confidence": 0.4}]
        )
        mock_json.return_value = [{"criterion_id": "syntax_1", "justification": "refined", "confidence": 0.4}]
        evidence = [make_evidence("syntax_1", "nao_cumprido", value=0.20)]
        assessments, _ = _reflect_loop(evidence, CHECKLIST, "plan", client, "model", 0.6, 3)

        assert assessments[0].checklist_penalty == pytest.approx(0.20)
        assert assessments[0].applied_penalty == pytest.approx(0.20)

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    def test_plan_log_only_on_first_item(self, mock_json: MagicMock):
        client = MagicMock()
        client.invoke.side_effect = [
            llm_response([
                {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8},
                {"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.8},
            ]),
        ]
        mock_json.side_effect = [
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.8}],
            [{"criterion_id": "syntax_2", "justification": "ok", "confidence": 0.8}],
        ]
        evidence = [
            make_evidence("syntax_1", "cumprido"),
            make_evidence("syntax_2", "cumprido"),
        ]
        assessments, _ = _reflect_loop(evidence, CHECKLIST, "MY_PLAN", client, "model", 0.6, 3)

        assert assessments[0].plan_log == "MY_PLAN"
        assert all(a.plan_log is None for a in assessments[1:])


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_empty_evidence_returns_empty_no_api_call(self, mock_cls: MagicMock):
        assessments = evaluate_once([], {}, "plan")
        assert assessments == []
        mock_cls.assert_not_called()  # no model built when there is no evidence

    # TODO: retry not working
    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_invalid_json_retries_once_then_succeeds(self, mock_cls: MagicMock, mock_json: MagicMock):
        """First response is invalid JSON; second is valid — exactly 2 API calls made."""
        mock_cls.return_value.invoke.side_effect = [
            bad_response("not json {{"),
            llm_response([
                {"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.7}
            ]),
        ]
        mock_json.side_effect = [
            None,
            [{"criterion_id": "syntax_1", "justification": "ok", "confidence": 0.7}]
        ]
        assessments = evaluate_once(
            [make_evidence("syntax_1", "cumprido")], CHECKLIST, "plan"
        )
        assert mock_json.call_count == 2
        assert len(assessments) == 1
        assert assessments[0].confidence == pytest.approx(0.7)

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_persistent_invalid_json_returns_graceful_defaults(self, mock_cls: MagicMock, mock_json: MagicMock):
        """Both attempts return invalid JSON — no crash, assessment uses defaults."""
        mock_cls.return_value.invoke.return_value = bad_response()
        mock_json.return_value = bad_response()
        assessments = evaluate_once(
            [make_evidence("syntax_1", "nao_cumprido", value=0.20)], CHECKLIST, "plan"
        )
        assert len(assessments) == 1
        a = assessments[0]
        assert a.justification == "No justification returned by model."
        assert a.confidence == 0.001
        assert a.flag_review is True
        # Penalty still applied correctly — status-based, not LLM-based
        assert a.applied_penalty == pytest.approx(0.20)

    @patch("agents.agent2_evaluator.evaluator.JsonOutputParser.invoke")
    @patch("agents.agent2_evaluator.evaluator.get_chat_model")
    def test_missing_checklist_entry_uses_zero_weight_no_crash(self, mock_cls: MagicMock, mock_json: MagicMock):
        """Criterion absent from checklist dict gets category_weight=0.0, no crash."""
        mock_cls.return_value.invoke.return_value = llm_response(
            [{"criterion_id": "unknown_99", "justification": "ok", "confidence": 0.7}]
        )
        mock_json.return_value = [
            {"criterion_id": "unknown_99", "justification": "ok", "confidence": 0.7}
        ]
        evidence = [make_evidence("unknown_99", "nao_cumprido", value=0.25)]
        assessments = evaluate_once(evidence, {}, "plan")  # empty checklist

        assert len(assessments) == 1
        a = assessments[0]
        assert a.category_weight == 0.001
        assert a.checklist_penalty == pytest.approx(0.25)
        assert a.applied_penalty == pytest.approx(0.25)
