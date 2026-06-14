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
from .chains import map_assessment_system_message, map_assessment_chain
from dotenv import load_dotenv
from langchain_core.messages import SystemMessage


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    category: str
    description: str
    raw: dict[str, Any]


class Agent3Feedback:
    """Agent 3: BPMN Assessment to personalized feedback."""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)

    def run(self, payload: dict[str, Any]) -> BPMNFeedback:
        """Runs the mapper from in-memory payload."""
        load_dotenv()
        llm = get_chat_model(temperature=0.3)

        diagram = normalize_diagram(payload.get("diagram", {}))
        assessment: list[BPMNAssessment] = payload.get("assessment", {})
        enunciado: str = payload.get("enunciado", {})

        self.logger.info("agent3.start")
        self._validate_diagram(diagram)
        self.logger.info(
            "agent3.diagram_loaded",
            elements=len(diagram.get("elements", [])),
            flows=len(diagram.get("flows", [])),
        )
        
        self.logger.info("agent3.bpmnasessment_loaded", total=len(assessment))
        system_message = map_assessment_system_message(enunciado, diagram)
        feedbacks = [self._map_assessment(system_message=system_message, assessment=assessment, llm=llm) for assessment in assessment]
        
        return BPMNFeedback([(ItemGrade(feed[1], feed[2]), feed[0]) for feed in feedbacks])

    def run_from_files(self, enunciado_path: str | Path, diagram_path: str | Path, assessment_path: str | Path) -> BPMNFeedback:
        """Runs the mapper by loading diagram/checklist files from disk."""
        diagram = read_diagram_file(diagram_path)
        assessment = read_bpmnassessment_file(assessment_path)
        enunciado: str = Path(enunciado_path).read_text(encoding="utf-8")
        return self.run({"diagram": diagram, "assessment": assessment, "enunciado": enunciado})

    @staticmethod
    def serialize(feedback: BPMNFeedback) -> str:
        return json.dumps(asdict(feedback), ensure_ascii=False, indent=2)

    @staticmethod
    def _validate_diagram(diagram: dict[str, Any]) -> None:
        if "elements" not in diagram or not isinstance(diagram.get("elements"), list):
            raise ValueError("Diagrama inválido: não foi possível identificar a lista de elementos.")
        if "flows" in diagram and not isinstance(diagram.get("flows"), list):
            raise ValueError("Diagrama inválido: campo 'flows' deve ser uma lista.")

    def _map_assessment(self, assessment: BPMNAssessment, system_message: SystemMessage, llm) -> tuple[str, float, str]:
        """Mapeia um assessment, juntamente como um enunciado e diagrama, a um feedback personalizado

        Args:
            enunciado (str): Enunciado original descrevendo o processo
            diagram (dict[str, Any]): Diagrama BPMN
            assessment (BPMNAssessment): Avaliação de um critério do checklist

        Returns:
            tuple[str, float, str]: Feedback personalizado, nota, questão
        """
        # Calcula a nota com base em applied_penalty e category_weight
        grade = (1.0 - assessment.applied_penalty) * assessment.category_weight
        
        # nao_avaliado: excluído da avaliação (nota 0.0, sem feedback)
        if assessment.status == "nao_avaliado":
            return ("Não avaliado", 0.0, assessment.question or "")
        
        # nao_aplicavel: contextual, sem penalidade aplicada
        if assessment.status == "nao_aplicavel":
            return (f"Critério não aplicável a este diagrama ({assessment.justification})", 
                    grade, assessment.question or "")
        
        # cumprido: positivo, sem penalidade
        if assessment.status == "cumprido":
            return ("✓ Critério atendido com sucesso.", grade, assessment.question or "")
        
        # nao_cumprido: ÚNICO status que chama LLM para feedback personalizado
        if assessment.status == "nao_cumprido":
            try:
                feedback = map_assessment_chain(system_message, llm, assessment)
                # Valida feedback não vazio
                if not feedback or feedback.strip() == "":
                    feedback = f"Critério não atendido. {assessment.justification or 'Verifique o diagrama.'}"
                return (feedback, grade, assessment.question or "")
            except Exception as exc:
                self.logger.error("agent3.llm_call_failed", criterion_id=assessment.criterion_id, error=str(exc))
                return (f"Critério não atendido. {assessment.justification or 'Erro ao gerar feedback.'}", 
                        grade, assessment.question or "")
        
        # Fallback para status desconhecido
        return ("Status desconhecido", 0.0, assessment.question or "")


