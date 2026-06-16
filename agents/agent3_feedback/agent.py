from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import structlog

from agents.contracts import *
# TODO: mover ferramentas usadas em múltiplos agentes para shared tools
from agents.shared_tools.bpmn_internal.parser import *
from agents.shared_tools.diagram.normalize import normalize_diagram
from agents.shared_tools.diagram.reader import read_diagram_file

from agents.shared_tools.llm import get_chat_model
from agents.agent3_feedback.grading import compute_grades
from .chains import (
    COVERAGE_MARKER,
    map_assessment_system_message,
    map_assessment_chain,
    render_grade_table,
    student_report_chain,
)
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    category: str
    description: str
    raw: dict[str, Any]


class Agent3Feedback:
    """Agent 3: validated BPMNAssessment -> grades + formative feedback report.

    Per the project spec ("Definição e escopo do projeto.md"):
    - Input: validated BPMNAssessment + task statement (enunciado) + diagram.
    - Job 1: final grade per category and total — deterministic Python, no LLM.
    - Job 2: formative feedback per error — where it is, why it matters, how to fix.
    - Goal Setting & Monitoring: verifies every error is covered before emitting.
    - Final step: rewrites the results as a readable Markdown report for the student.
    """

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)

    def run(self, payload: dict[str, Any]) -> BPMNFeedback:
        """Runs the full Agent 3 pipeline from an in-memory payload."""
        load_dotenv()
        llm = get_chat_model(temperature=0.3)

        diagram = normalize_diagram(payload.get("diagram", {}))
        assessments: list[BPMNAssessment] = payload.get("assessment", [])
        enunciado: str = payload.get("enunciado", "")

        self.logger.info("agent3.start")
        self._validate_diagram(diagram)
        self.logger.info(
            "agent3.diagram_loaded",
            elements=len(diagram.get("elements", [])),
            flows=len(diagram.get("flows", [])),
        )
        self.logger.info("agent3.bpmnassessment_loaded", total=len(assessments))

        # Job 1 — final grade per category and total (deterministic, no LLM)
        final_grade, category_grades = compute_grades(assessments)
        self.logger.info(
            "agent3.grades_computed",
            final_grade=final_grade,
            categories={g.category: g.score for g in category_grades},
        )

        # Job 2 — formative feedback for every error (nao_cumprido)
        errors = [a for a in assessments if a.status == "nao_cumprido"]
        self.logger.info(
            "agent3.feedback_generation.start",
            errors=len(errors),
            criteria=[a.criterion_id for a in errors],
        )
        system_message = map_assessment_system_message(enunciado, diagram)
        feedback_items = [
            self._build_feedback_item(a, system_message, llm, index=i, total=len(errors))
            for i, a in enumerate(errors, start=1)
        ]
        self.logger.info("agent3.feedback_generation.done", items=len(feedback_items))

        # Goal Monitoring (coverage): every error must have non-empty feedback;
        # empty ones get one targeted retry, then a deterministic fallback.
        feedback_items = self._ensure_feedback_coverage(
            feedback_items, errors, system_message, llm
        )

        # Resumo dos acertos — criteria the student got right
        strengths = [
            (a.question or a.criterion_id)
            for a in assessments
            if a.status == "cumprido"
        ]

        # Final step — rewrite the results as readable text for the student
        student_report = self._write_student_report(
            llm, enunciado, final_grade, category_grades, feedback_items, strengths
        )

        self.logger.info(
            "agent3.finished",
            errors=len(feedback_items),
            strengths=len(strengths),
            report_chars=len(student_report),
        )
        return BPMNFeedback(
            final_grade=final_grade,
            category_grades=category_grades,
            feedback_items=feedback_items,
            strengths=strengths,
            student_report=student_report,
        )

    def run_from_files(
        self,
        enunciado_path: str | Path,
        diagram_path: str | Path,
        assessment_path: str | Path,
    ) -> BPMNFeedback:
        """Runs the pipeline loading enunciado/diagram/assessment from disk."""
        diagram = read_diagram_file(diagram_path)
        assessment = read_bpmnassessment_file(assessment_path)
        enunciado: str = Path(enunciado_path).read_text(encoding="utf-8")
        return self.run({"diagram": diagram, "assessment": assessment, "enunciado": enunciado})

    @staticmethod
    def serialize(feedback: BPMNFeedback) -> str:
        return json.dumps(asdict(feedback), ensure_ascii=False, indent=2)

    @staticmethod
    def serialize_markdown(feedback: BPMNFeedback) -> str:
        return feedback.student_report

    @staticmethod
    def _validate_diagram(diagram: dict[str, Any]) -> None:
        if "elements" not in diagram or not isinstance(diagram.get("elements"), list):
            raise ValueError("Diagrama inválido: não foi possível identificar a lista de elementos.")
        if "flows" in diagram and not isinstance(diagram.get("flows"), list):
            raise ValueError("Diagrama inválido: campo 'flows' deve ser uma lista.")

    def _build_feedback_item(
        self,
        assessment: BPMNAssessment,
        system_message: SystemMessage,
        llm,
        index: int = 0,
        total: int = 0,
    ) -> FeedbackItem:
        self.logger.info(
            "agent3.feedback_item.llm_call",
            criterion_id=assessment.criterion_id,
            category=assessment.category,
            index=index,
            total=total,
        )
        try:
            feedback = map_assessment_chain(system_message, llm, assessment)
        except Exception as exc:
            # Graceful degradation: an LLM failure must not crash the run.
            # Empty feedback is handled downstream by _ensure_feedback_coverage
            # (retry, then deterministic fallback to the Agent 2 justification).
            self.logger.error(
                "agent3.feedback_item.llm_failed",
                criterion_id=assessment.criterion_id,
                error=str(exc),
            )
            feedback = ""
        self.logger.info(
            "agent3.feedback_item.generated",
            criterion_id=assessment.criterion_id,
            chars=len(feedback),
        )
        return FeedbackItem(
            criterion_id=assessment.criterion_id,
            category=assessment.category,
            question=assessment.question or "",
            element=assessment.element,
            applied_penalty=assessment.applied_penalty,
            feedback=feedback,
        )

    def _ensure_feedback_coverage(
        self,
        items: list[FeedbackItem],
        errors: list[BPMNAssessment],
        system_message: SystemMessage,
        llm,
    ) -> list[FeedbackItem]:
        """Goal Monitoring: retry empty feedbacks once, then fall back to the
        Agent 2 justification so no error is ever emitted without feedback."""
        errors_by_id = {a.criterion_id: a for a in errors}
        covered: list[FeedbackItem] = []
        retried: list[str] = []
        for item in items:
            if not item.feedback.strip():
                self.logger.warning("agent3.coverage_retry", criterion_id=item.criterion_id)
                retried.append(item.criterion_id)
                try:
                    retry = map_assessment_chain(system_message, llm, errors_by_id[item.criterion_id])
                except Exception as exc:
                    self.logger.error(
                        "agent3.coverage_retry_failed",
                        criterion_id=item.criterion_id,
                        error=str(exc),
                    )
                    retry = ""
                if not retry.strip():
                    self.logger.error("agent3.coverage_fallback", criterion_id=item.criterion_id)
                    retry = (
                        "Não foi possível gerar o feedback detalhado deste item. "
                        f"Avaliação registrada: {errors_by_id[item.criterion_id].justification}"
                    )
                item = FeedbackItem(**{**asdict(item), "feedback": retry})
            covered.append(item)
        self.logger.info(
            "agent3.coverage_check.done",
            total=len(covered),
            retried=retried,
            all_covered=all(it.feedback.strip() for it in covered),
        )
        return covered

    def _write_student_report(
        self,
        llm,
        enunciado: str,
        final_grade: float,
        category_grades: list[CategoryGrade],
        feedback_items: list[FeedbackItem],
        strengths: list[str],
    ) -> str:
        """Final step: LLM rewrites the results as student-readable Markdown.

        Coverage is verified via per-error markers; any error section the LLM
        dropped is appended deterministically from its FeedbackItem. The grade
        table is rendered in Python and re-appended if the LLM altered it."""
        grade_table = render_grade_table(final_grade, category_grades)
        try:
            report = student_report_chain(
                llm, enunciado, grade_table, feedback_items, strengths
            )
        except Exception as exc:
            # Graceful degradation: on LLM failure, fall back to an empty report;
            # the coverage-gap and grade-table restoration below rebuild a
            # deterministic report from the FeedbackItems and the grade table.
            self.logger.error("agent3.student_report.llm_failed", error=str(exc))
            report = ""

        missing = [
            it for it in feedback_items
            if COVERAGE_MARKER.format(criterion_id=it.criterion_id) not in report
        ]
        if missing:
            self.logger.warning(
                "agent3.report_coverage_gap",
                missing=[it.criterion_id for it in missing],
            )
            sections = [
                f"{COVERAGE_MARKER.format(criterion_id=it.criterion_id)}\n"
                f"### {it.question or it.criterion_id}\n\n{it.feedback}"
                for it in missing
            ]
            report += "\n\n## Pontos a melhorar (complemento)\n\n" + "\n\n".join(sections)

        # The official numbers are deterministic — if the LLM did not reproduce
        # the final grade line verbatim, append the authoritative table.
        if f"**Nota final: {final_grade:.2f} / 10**" not in report:
            self.logger.warning("agent3.report_grade_table_restored")
            report += "\n\n## Resultado (oficial)\n\n" + grade_table

        return report
