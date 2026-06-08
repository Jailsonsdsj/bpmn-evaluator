from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any

import structlog

from agents.contracts import BPMNEvidence
from agents.agent1_analyst.checklist.parser import read_checklist_file
from agents.agent1_analyst.diagram.normalize import normalize_diagram
from agents.agent1_analyst.diagram.reader import read_diagram_file


@dataclass(frozen=True)
class Criterion:
    criterion_id: str
    category: str
    description: str
    raw: dict[str, Any]


class Agent1Analyst:
    """Agent 1: maps checklist criteria to BPMN evidence."""

    def __init__(self) -> None:
        self.logger = structlog.get_logger(self.__class__.__name__)

    def run(self, payload: dict[str, Any]) -> list[BPMNEvidence]:
        """Runs the mapper from in-memory payload."""
        diagram = normalize_diagram(payload.get("diagram", {}))
        checklist = payload.get("checklist", {})

        self.logger.info("agent1.start")
        self._validate_diagram(diagram)
        self.logger.info(
            "agent1.diagram_loaded",
            elements=len(diagram.get("elements", [])),
            flows=len(diagram.get("flows", [])),
        )

        criteria = self._extract_criteria(checklist)
        self.logger.info("agent1.criteria_loaded", total=len(criteria))

        evidences = [self._map_criterion(diagram=diagram, criterion=criterion) for criterion in criteria]
        self.logger.info("agent1.finished", total_evidences=len(evidences))
        return evidences

    def run_from_files(self, diagram_path: str | Path, checklist_path: str | Path) -> list[BPMNEvidence]:
        """Runs the mapper by loading diagram/checklist files from disk."""
        diagram = read_diagram_file(diagram_path)
        checklist = read_checklist_file(checklist_path)
        return self.run({"diagram": diagram, "checklist": checklist})

    @staticmethod
    def serialize(evidences: list[BPMNEvidence]) -> str:
        return json.dumps([asdict(item) for item in evidences], ensure_ascii=False, indent=2)

    @staticmethod
    def _validate_diagram(diagram: dict[str, Any]) -> None:
        if "elements" not in diagram or not isinstance(diagram.get("elements"), list):
            raise ValueError("Diagrama inválido: não foi possível identificar a lista de elementos.")
        if "flows" in diagram and not isinstance(diagram.get("flows"), list):
            raise ValueError("Diagrama inválido: campo 'flows' deve ser uma lista.")

    @staticmethod
    def _build_evidence(
        criterion: Criterion,
        status: str,
        element: str,
        observation: str | None = None,
    ) -> BPMNEvidence:
        value = Agent1Analyst._value_for_status(status, criterion.raw)
        observation_text = Agent1Analyst._format_observation(status, value, observation)
        return BPMNEvidence(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            status=status,
            value=value,
            element=element,
            observation=observation_text,
            question=criterion.description,
        )

    @staticmethod
    def _value_for_status(status: str, raw: dict[str, Any]) -> float:
        score = Agent1Analyst._criterion_score(raw)
        if score is None:
            return Agent1Analyst._status_value(status)

        normalized = status.lower()
        if normalized == "cumprido":
            return score
        return 0.0

    @staticmethod
    def _format_observation(status: str, value: float | None, reason: str | None) -> str:
        normalized = status.lower()
        if normalized == "cumprido":
            base = "Critério atendido"
        elif normalized == "nao_cumprido":
            base = "Critério não atendido"
        else:
            base = "Critério não aplicável"

        parts = [base]
        if reason:
            clean_reason = reason.strip().rstrip(".")
            parts.append(f"Motivo: {clean_reason}")
        if value is not None:
            parts.append(f"Pontuação: {value}")
        return ". ".join(parts) + "."

    @staticmethod
    def _status_value(status: str) -> float:
        normalized = status.lower()
        if normalized == "cumprido":
            return 1.0
        return 0.0

    @staticmethod
    def _criterion_score(raw: dict[str, Any]) -> float | None:
        for key in (
            "score",
            "pontuacao",
            "pontuação",
            "pontuacao_geral",
            "pontuação geral",
            "penalty",
            "value",
        ):
            if key in raw:
                return Agent1Analyst._parse_score(raw.get(key))
        return None

    @staticmethod
    def _parse_score(value: Any) -> float | None:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)

        cleaned = str(value).strip()
        if not cleaned:
            return None

        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", ".")

        try:
            return float(cleaned)
        except ValueError:
            return None

    def _extract_criteria(self, checklist: dict[str, Any]) -> list[Criterion]:
        normalized: list[Criterion] = []

        if "criteria" in checklist and isinstance(checklist["criteria"], list):
            normalized.extend(self._normalize_criteria_list(checklist["criteria"], default_category=None))
            return normalized

        if "checklist" in checklist and isinstance(checklist["checklist"], list):
            normalized.extend(self._normalize_criteria_list(checklist["checklist"], default_category=None))
            return normalized

        for key, value in checklist.items():
            if isinstance(value, list):
                normalized.extend(self._normalize_criteria_list(value, default_category=key))
            elif isinstance(value, dict) and isinstance(value.get("criteria"), list):
                normalized.extend(self._normalize_criteria_list(value["criteria"], default_category=key))

        return normalized

    @staticmethod
    def _normalize_criteria_list(items: list[Any], default_category: str | None) -> list[Criterion]:
        criteria: list[Criterion] = []
        for index, item in enumerate(items, start=1):
            if not isinstance(item, dict):
                continue

            criterion_id = str(
                item.get("criterion_id")
                or item.get("criterio_id")
                or item.get("id")
                or f"{default_category or 'criterion'}_{index}"
            )
            category = str(item.get("category") or item.get("categoria") or default_category or "syntax")
            description = str(
                item.get("description")
                or item.get("descricao")
                or item.get("criterion")
                or item.get("criterio")
                or item.get("name")
                or item.get("nome")
                or criterion_id
            )

            criteria.append(
                Criterion(
                    criterion_id=criterion_id,
                    category=category,
                    description=description,
                    raw=item,
                )
            )

        return criteria

    def _map_criterion(self, diagram: dict[str, Any], criterion: Criterion) -> BPMNEvidence:
        elements = diagram.get("elements", [])
        flows = diagram.get("flows", [])

        not_applicable_reason = self._not_applicable_reason(elements, flows, criterion)
        if not_applicable_reason:
            return self._build_evidence(
                criterion,
                status="nao_aplicavel",
                element=criterion.description,
                observation=not_applicable_reason,
            )

        explicit_mapping = self._map_with_explicit_fields(
            elements=elements,
            flows=flows,
            criterion=criterion,
        )
        if explicit_mapping is not None:
            return explicit_mapping

        return self._map_with_textual_heuristics(
            elements=elements,
            flows=flows,
            criterion=criterion,
        )

    def _map_with_explicit_fields(
        self,
        elements: list[dict[str, Any]],
        flows: list[dict[str, Any]],
        criterion: Criterion,
    ) -> BPMNEvidence | None:
        raw = criterion.raw
        expected_type = raw.get("element_type") or raw.get("tipo_elemento") or raw.get("expected_type")
        expected_name = raw.get("element_name") or raw.get("nome_elemento") or raw.get("expected_name")
        min_occ = raw.get("min_occurrences")
        exact_occ = raw.get("exact_occurrences")
        max_occ = raw.get("max_occurrences")

        if not any(v is not None for v in (expected_type, expected_name, min_occ, exact_occ, max_occ)):
            return None

        candidates = []
        for element in elements:
            if expected_type and str(element.get("type")) != str(expected_type):
                continue
            if expected_name and str(element.get("name", "")).strip() != str(expected_name).strip():
                continue
            candidates.append(element)

        if not candidates:
            target = str(expected_name or expected_type or criterion.description)
            expectation = self._describe_expectation(expected_type=expected_type, expected_name=expected_name)
            inspected = self._summarize_elements(elements)
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=target,
                observation=f"{expectation} não foi encontrado no diagrama. Elementos analisados: {inspected}.",
            )

        if exact_occ is not None and len(candidates) != int(exact_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=(
                    f"{self._describe_expectation(expected_type=expected_type, expected_name=expected_name)} "
                    f"exigia exatamente {int(exact_occ)} ocorrência(s), mas foram encontradas {len(candidates)}. "
                    f"Primeira ocorrência: {self._element_ref(candidates[0])}."
                ),
            )

        if min_occ is not None and len(candidates) < int(min_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=(
                    f"{self._describe_expectation(expected_type=expected_type, expected_name=expected_name)} "
                    f"exigia no mínimo {int(min_occ)} ocorrência(s), mas foram encontradas {len(candidates)}. "
                    f"Primeira ocorrência: {self._element_ref(candidates[0])}."
                ),
            )

        if max_occ is not None and len(candidates) > int(max_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=(
                    f"{self._describe_expectation(expected_type=expected_type, expected_name=expected_name)} "
                    f"permitia no máximo {int(max_occ)} ocorrência(s), mas foram encontradas {len(candidates)}. "
                    f"Primeira ocorrência: {self._element_ref(candidates[0])}."
                ),
            )

        connection_error = self._validate_connection_rules(candidates[0], raw)
        if connection_error:
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=(
                    f"{self._describe_expectation(expected_type=expected_type, expected_name=expected_name)} "
                    f"foi encontrado em {self._element_ref(candidates[0])}, mas a validação de conexões falhou: "
                    f"{connection_error}"
                ),
            )

        if raw.get("require_named_flows") is True:
            unnamed_flow = next((flow for flow in flows if not str(flow.get("name", "")).strip()), None)
            if unnamed_flow:
                return self._build_evidence(
                    criterion,
                    status="nao_cumprido",
                    element=str(unnamed_flow.get("id", "sequenceFlow")),
                    observation="Fluxo de sequência sem nome.",
                )

        return self._build_evidence(
            criterion,
            status="cumprido",
            element=self._element_ref(candidates[0]),
        )

    def _map_with_textual_heuristics(
        self,
        elements: list[dict[str, Any]],
        flows: list[dict[str, Any]],
        criterion: Criterion,
    ) -> BPMNEvidence:
        description = criterion.description.lower()

        start_events = [e for e in elements if e.get("type") == "startEvent"]
        end_events = [e for e in elements if e.get("type") == "endEvent"]
        tasks = [e for e in elements if str(e.get("type")) in {"task", "userTask", "serviceTask"}]
        gateways = [e for e in elements if str(e.get("type", "")).endswith("Gateway")]

        if (
            "início" in description
            or "inicio" in description
            or "start event" in description
            or "evento inicial" in description
            or "evento de inicio" in description
            or "evento de início" in description
        ):
            return self._exists_result(criterion, start_events, "startEvent")

        if (
            "fim" in description
            or "end event" in description
            or "evento final" in description
            or "evento de fim" in description
            or "evento de término" in description
            or "evento de termino" in description
        ):
            return self._exists_result(criterion, end_events, "endEvent")

        if "gateway" in description:
            return self._exists_result(criterion, gateways, "gateway")

        if "atividade" in description or "task" in description or "tarefa" in description:
            return self._exists_result(criterion, tasks, "task")

        if ("fluxo" in description or "sequence flow" in description) and (
            "nome" in description or "label" in description or "rótulo" in description or "rotulo" in description
        ):
            unnamed_flow = next((flow for flow in flows if not str(flow.get("name", "")).strip()), None)
            if unnamed_flow:
                return self._build_evidence(
                    criterion,
                    status="nao_cumprido",
                    element=str(unnamed_flow.get("id", "sequenceFlow")),
                    observation=(
                        f"Foi encontrado um fluxo sem nome ({unnamed_flow.get('id', 'sequenceFlow')}) "
                        f"para o critério '{criterion.description}'."
                    ),
                )
            first = flows[0] if flows else None
            return self._build_evidence(
                criterion,
                status="cumprido" if first else "nao_cumprido",
                element=str(first.get("id")) if first else "sequenceFlow",
                observation=None
                if first
                else f"Nenhum fluxo de sequência foi encontrado para o critério '{criterion.description}'.",
            )

        return self._build_evidence(
            criterion,
            status="nao_cumprido",
            element=criterion.description,
            observation=(
                f"Não foi possível relacionar o critério '{criterion.description}' a padrões conhecidos "
                f"do diagrama. Elementos analisados: {self._summarize_elements(elements)}."
            ),
        )

    @staticmethod
    def _validate_connection_rules(element: dict[str, Any], criterion: dict[str, Any]) -> str | None:
        incoming = element.get("incoming", []) or []
        outgoing = element.get("outgoing", []) or []

        if criterion.get("require_incoming") is True and len(incoming) == 0:
            return "Elemento sem fluxo de entrada, mas o critério exige entrada."
        if criterion.get("require_outgoing") is True and len(outgoing) == 0:
            return "Elemento sem fluxo de saída, mas o critério exige saída."

        min_incoming = criterion.get("min_incoming")
        min_outgoing = criterion.get("min_outgoing")
        exact_incoming = criterion.get("exact_incoming")
        exact_outgoing = criterion.get("exact_outgoing")

        if min_incoming is not None and len(incoming) < int(min_incoming):
            return f"Esperado no mínimo {int(min_incoming)} fluxo(s) de entrada, encontrado {len(incoming)}."
        if min_outgoing is not None and len(outgoing) < int(min_outgoing):
            return f"Esperado no mínimo {int(min_outgoing)} fluxo(s) de saída, encontrado {len(outgoing)}."
        if exact_incoming is not None and len(incoming) != int(exact_incoming):
            return f"Esperado exatamente {int(exact_incoming)} fluxo(s) de entrada, encontrado {len(incoming)}."
        if exact_outgoing is not None and len(outgoing) != int(exact_outgoing):
            return f"Esperado exatamente {int(exact_outgoing)} fluxo(s) de saída, encontrado {len(outgoing)}."

        return None

    @staticmethod
    def _exists_result(
        criterion: Criterion,
        candidates: list[dict[str, Any]],
        expected_label: str,
    ) -> BPMNEvidence:
        if candidates:
            return Agent1Analyst._build_evidence(
                criterion,
                status="cumprido",
                element=Agent1Analyst._element_ref(candidates[0]),
                observation=(
                    f"Foi encontrado {len(candidates)} elemento(s) compatível(is) com "
                    f"'{criterion.description}'. Principal ocorrência: {Agent1Analyst._element_ref(candidates[0])}."
                ),
            )
        return Agent1Analyst._build_evidence(
            criterion,
            status="nao_cumprido",
            element=expected_label,
            observation=(
                f"Não foi encontrado nenhum elemento compatível com '{criterion.description}'. "
                f"Esperado algo como {expected_label}."
            ),
        )

    @staticmethod
    def _element_ref(element: dict[str, Any]) -> str:
        element_id = str(element.get("id", "unknown"))
        name = str(element.get("name", "")).strip()
        if name:
            return f"{name} ({element_id})"
        return element_id

    @staticmethod
    def _not_applicable_reason(
        elements: list[dict[str, Any]],
        flows: list[dict[str, Any]],
        criterion: Criterion,
    ) -> str | None:
        raw = criterion.raw
        if raw.get("nao_aplicavel") is True or raw.get("not_applicable") is True:
            return f"O checklist marcou o critério '{criterion.description}' como não aplicável."
        if raw.get("aplicavel") is False or raw.get("applicable") is False:
            return f"O checklist marcou o critério '{criterion.description}' como não aplicável."

        description = criterion.description.lower()
        has_pool = any(str(element.get("type")) == "pool" for element in elements)
        has_lane = any(str(element.get("type")) == "lane" for element in elements)
        has_subprocess = any(str(element.get("type")) == "subProcess" for element in elements)
        has_message_flow = any(
            str(flow.get("type", "")).lower() in {"messageflow", "message_flow"} for flow in flows
        )

        if (
            "message flow" in description
            or "messageflow" in description
            or "mensagem" in description
        ) and not (has_message_flow or has_pool or has_lane):
            return (
                f"O critério '{criterion.description}' não se aplica porque o diagrama não possui "
                f"pools, raias ou fluxos de mensagem."
            )
        if "pool" in description and not has_pool:
            return f"O critério '{criterion.description}' não se aplica porque o diagrama não possui pool."
        if ("lane" in description or "raia" in description) and not has_lane:
            return f"O critério '{criterion.description}' não se aplica porque o diagrama não possui raia."
        if (
            "subprocess" in description
            or "sub-processo" in description
            or "subprocesso" in description
        ) and not has_subprocess:
            return (
                f"O critério '{criterion.description}' não se aplica porque o diagrama não possui subprocesso."
            )

        return None

    @staticmethod
    def _describe_expectation(expected_type: str | None, expected_name: str | None) -> str:
        parts: list[str] = []
        if expected_type:
            parts.append(f"tipo '{expected_type}'")
        if expected_name:
            parts.append(f'nome "{expected_name}"')
        if not parts:
            return "O critério"
        return "O critério que espera " + " e ".join(parts)

    @staticmethod
    def _summarize_elements(elements: list[dict[str, Any]], limit: int = 4) -> str:
        if not elements:
            return "nenhum elemento"

        summary = [Agent1Analyst._element_ref(element) for element in elements[:limit]]
        if len(elements) > limit:
            summary.append(f"... (+{len(elements) - limit} outros)")
        return ", ".join(summary)
