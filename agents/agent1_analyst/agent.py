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
from agents.agent1_analyst.preprocessing import (
    build_connectivity_map,
    build_lane_map,
    classify_events,
    resolve_structural_criteria,
)


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

    def run(self, payload: dict[str, Any], enunciado: str | None = None) -> list[BPMNEvidence]:
        """Runs the mapper from in-memory payload."""
        raw_diagram = payload.get("diagram", {})
        diagram = normalize_diagram(raw_diagram)
        checklist = payload.get("checklist", {})

        self.logger.info("agent1.start")
        self._validate_diagram(diagram)
        self.logger.info(
            "agent1.diagram_loaded",
            elements=len(diagram.get("elements", [])),
            flows=len(diagram.get("flows", [])),
        )

        # Build structural pre-processing structures from the raw LucidChart JSON.
        # These work on all shape classes (BPMNGateway, BPMNEvent, …) before
        # normalization strips them, so structural criteria can be resolved
        # deterministically without any LLM call.
        shapes, lines = self._extract_lucidchart_data(raw_diagram)
        connectivity = build_connectivity_map(shapes, lines)
        lane_map = build_lane_map(shapes)
        event_map = classify_events(shapes, connectivity)
        self.logger.info(
            "agent1.preprocessing_done",
            shapes=len(shapes),
            lines=len(lines),
            pools=len(lane_map.get("pools", [])),
            has_lanes=lane_map.get("has_lanes", False),
            events=len(event_map),
        )

        criteria = self._extract_criteria(checklist)
        self.logger.info("agent1.criteria_loaded", total=len(criteria))

        evidences = [
            self._map_criterion(
                diagram=diagram,
                criterion=criterion,
                shapes=shapes,
                connectivity=connectivity,
                lane_map=lane_map,
                event_map=event_map,
                enunciado=enunciado,
            )
            for criterion in criteria
        ]
        self.logger.info("agent1.finished", total_evidences=len(evidences))
        return evidences

    def run_from_files(
        self,
        diagram_path: str | Path,
        checklist_path: str | Path,
        enunciado_path: str | Path | None = None,
    ) -> list[BPMNEvidence]:
        """Runs the mapper by loading diagram/checklist files from disk."""
        diagram = read_diagram_file(diagram_path)
        checklist = read_checklist_file(checklist_path)
        enunciado: str | None = None
        if enunciado_path is not None:
            enunciado = Path(enunciado_path).read_text(encoding="utf-8")
        return self.run({"diagram": diagram, "checklist": checklist}, enunciado=enunciado)

    @staticmethod
    def serialize(evidences: list[BPMNEvidence]) -> str:
        return json.dumps([asdict(item) for item in evidences], ensure_ascii=False, indent=2)

    @staticmethod
    def _extract_lucidchart_data(raw_diagram: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return (shapes, lines) from a LucidChart JSON, or ([], []) for other formats."""
        shapes: list[dict[str, Any]] = []
        lines: list[dict[str, Any]] = []
        pages = raw_diagram.get("pages", [])
        for page in pages:
            items = page.get("items", {}) if isinstance(page, dict) else {}
            if isinstance(items, dict):
                shapes.extend(items.get("shapes", []))
                lines.extend(items.get("lines", []))
        return shapes, lines

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
        element: str | None,
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
        """Get the penalty value from checklist for the criterion.
        
        Value is ALWAYS the checklist penalty, regardless of status:
        - cumprido: use checklist penalty value
        - nao_cumprido: use checklist penalty value (will be applied as penalty)
        - nao_aplicavel: use checklist penalty value (won't be applied)
        - nao_avaliado: use checklist penalty value (won't be applied)
        """
        score = Agent1Analyst._criterion_score(raw)
        if score is not None:
            return score
        
        return Agent1Analyst._status_value(status)

    @staticmethod
    def _format_observation(status: str, value: float | None, reason: str | None) -> str:
        normalized = status.lower()
        if normalized == "cumprido":
            base = "Critério atendido"
        elif normalized == "nao_cumprido":
            base = "Critério não atendido"
        elif normalized == "nao_avaliado":
            base = "Critério não avaliado"
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

    def _map_criterion(
        self,
        diagram: dict[str, Any],
        criterion: Criterion,
        shapes: list[dict[str, Any]] | None = None,
        connectivity: dict[str, Any] | None = None,
        lane_map: dict[str, Any] | None = None,
        event_map: dict[str, str] | None = None,
        enunciado: str | None = None,
    ) -> BPMNEvidence:
        tipo = criterion.raw.get("tipo_avaliacao", "interpretativo")
        code = criterion.raw.get("code", "")

        # Structural criteria: resolved deterministically — no heuristics, no LLM.
        if tipo == "estrutural" and code and shapes is not None:
            status, obs = resolve_structural_criteria(
                code,
                connectivity or {},
                lane_map or {},
                event_map or {},
                shapes,
            )
            return self._build_evidence(
                criterion,
                status=status,
                element="diagrama",
                observation=obs,
            )

        elements = diagram.get("elements", [])
        flows = diagram.get("flows", [])

        not_applicable_reason = self._not_applicable_reason(
            elements, flows, criterion, shapes=shapes, lane_map=lane_map
        )
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

        # Task-statement-aware evaluation for proposal criteria and pool-name check.
        if enunciado is not None and shapes is not None:
            enunciado_result = self._map_with_enunciado(
                criterion=criterion,
                shapes=shapes,
                lane_map=lane_map or {},
                event_map=event_map or {},
                enunciado=enunciado,
            )
            if enunciado_result is not None:
                return enunciado_result

        return self._map_with_textual_heuristics(
            elements=elements,
            flows=flows,
            criterion=criterion,
            shapes=shapes,
            connectivity=connectivity,
            lane_map=lane_map,
            event_map=event_map,
        )

    def _map_with_enunciado(
        self,
        criterion: Criterion,
        shapes: list[dict[str, Any]],
        lane_map: dict[str, Any],
        event_map: dict[str, str],
        enunciado: str,
    ) -> BPMNEvidence | None:
        """Evaluate criteria that need the task statement.

        Returns a BPMNEvidence when the criterion is handled, None to fall through
        to textual heuristics.  Handles: BP6 (pool name vs process name) and
        P1-P5 (expected elements modeled).
        If the task statement is insufficient to answer, returns nao_avaliado
        with an observation that cites both pool name and task context.
        """
        code = criterion.raw.get("code", "")

        gateways = [s for s in shapes if "Gateway" in s.get("class", "")]
        events   = [s for s in shapes if "Event"   in s.get("class", "")]
        tasks    = [s for s in shapes if s.get("class") == "ProcessBlock"]
        pools    = lane_map.get("pools", [])

        # ----------------------------------------------------------------
        # BP6 — pool name matches the process described in the task statement
        # ----------------------------------------------------------------
        if code == "BP6":
            pool_name = next((p.get("pool_name", "") for p in pools if p.get("pool_name")), "")
            if not pool_name:
                return self._build_evidence(
                    criterion, status="nao_avaliado", element="pool",
                    observation="Piscina sem nome — não foi possível comparar com o enunciado.",
                )

            title_line = next((l.strip() for l in enunciado.splitlines() if l.strip()), "")
            stop_words = {"de", "da", "do", "dos", "das", "e", "o", "a", "os", "as", "em", "para", "com"}
            pool_keywords = {w.lower() for w in pool_name.split() if w.lower() not in stop_words}
            enunciado_lower = enunciado.lower()
            matches = [w for w in pool_keywords if w in enunciado_lower]

            if len(matches) >= max(1, len(pool_keywords) // 2):
                return self._build_evidence(
                    criterion, status="cumprido", element=pool_name,
                    observation=(
                        f"Nome da piscina '{pool_name}' corresponde ao processo descrito no enunciado "
                        f"(palavras-chave encontradas: {', '.join(sorted(matches))})."
                    ),
                )
            return self._build_evidence(
                criterion, status="nao_cumprido", element=pool_name,
                observation=(
                    f"Nome da piscina '{pool_name}' não corresponde ao processo '{title_line}'. "
                    f"Palavras-chave do nome da piscina não encontradas no enunciado: "
                    f"{', '.join(sorted(pool_keywords - set(matches)))}."
                ),
            )

        # ----------------------------------------------------------------
        # P1 — expected tasks modeled
        # ----------------------------------------------------------------
        if code == "P1":
            if tasks:
                sample = [self._get_shape_name(t) for t in tasks[:3]]
                return self._build_evidence(
                    criterion, status="cumprido", element="tarefas",
                    observation=(
                        f"{len(tasks)} tarefa(s) modeladas "
                        f"(ex: {', '.join(filter(None, sample))})."
                    ),
                )
            return self._build_evidence(
                criterion, status="nao_cumprido", element="tarefas",
                observation="Nenhuma tarefa (ProcessBlock) encontrada no diagrama.",
            )

        # ----------------------------------------------------------------
        # P2 — expected actors modeled (pools / lanes)
        # ----------------------------------------------------------------
        if code == "P2":
            if pools and any(p.get("lanes") for p in pools):
                lane_names = [l for p in pools for l in p.get("lanes", [])]
                return self._build_evidence(
                    criterion, status="cumprido", element="atores",
                    observation=f"Atores modelados nas raias: {', '.join(lane_names)}.",
                )
            if pools:
                names = [p.get("pool_name", "") for p in pools]
                return self._build_evidence(
                    criterion, status="cumprido", element="atores",
                    observation=f"Piscina presente: {', '.join(filter(None, names))}.",
                )
            return self._build_evidence(
                criterion, status="nao_cumprido", element="atores",
                observation="Nenhuma piscina ou raia encontrada para representar atores.",
            )

        # ----------------------------------------------------------------
        # P3 — expected events modeled
        # ----------------------------------------------------------------
        if code == "P3":
            if events:
                return self._build_evidence(
                    criterion, status="cumprido", element="eventos",
                    observation=f"{len(events)} evento(s) modelado(s) no diagrama.",
                )
            return self._build_evidence(
                criterion, status="nao_cumprido", element="eventos",
                observation="Nenhum evento (BPMNEvent) encontrado no diagrama.",
            )

        # ----------------------------------------------------------------
        # P4 — expected flow objects / artifacts modeled
        # Data objects / artifacts are not encoded in LucidChart JSON shapes.
        # ----------------------------------------------------------------
        # P4 returns None → falls through to nao_avaliado in textual heuristics.

        # ----------------------------------------------------------------
        # P5 — expected gateways modeled
        # ----------------------------------------------------------------
        if code == "P5":
            if gateways:
                gw_names = [self._get_shape_name(g) for g in gateways]
                return self._build_evidence(
                    criterion, status="cumprido", element="gateways",
                    observation=(
                        f"{len(gateways)} gateway(s) modelado(s): "
                        f"{', '.join(filter(None, gw_names))}."
                    ),
                )
            return self._build_evidence(
                criterion, status="nao_cumprido", element="gateways",
                observation="Nenhum gateway (BPMNGateway) encontrado no diagrama.",
            )

        return None

    def _map_with_explicit_fields(
        self,
        elements: list[dict[str, Any]],
        flows: list[dict[str, Any]],
        criterion: Criterion,
    ) -> BPMNEvidence | None:
        """Map criterion using explicit field definitions from checklist.
        
        Explicit fields allow precise matching:
        - element_type: Expected BPMN element type (e.g., "startEvent", "exclusiveGateway")
        - element_name: Expected element name/label
        - occurrences: Exact, min, max count constraints
        
        Decision logic:
        - No explicit fields defined → return None (use textual heuristics)
        - Explicit fields defined but NO matching candidates:
          → nao_cumprido (reference element doesn't exist in diagram)
        - Candidates exist but violate constraints:
          → nao_cumprido (element exists but criteria not met)
        - Candidates exist and all constraints satisfied:
          → cumprido
        
        Example:
        - Criterion: element_type="startEvent" → find all startEvents
        - No startEvents found → nao_cumprido ("Start event not found")
        - StartEvent found but has no outgoing flow → nao_cumprido ("Start event has no output flow")
        - StartEvent exists and has outgoing flow → cumprido
        """
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
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=target,
                observation=f"Elemento esperado não encontrado: {target}.",
            )

        if exact_occ is not None and len(candidates) != int(exact_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado exatamente {int(exact_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        if min_occ is not None and len(candidates) < int(min_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado no mínimo {int(min_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        if max_occ is not None and len(candidates) > int(max_occ):
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado no máximo {int(max_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        connection_error = self._validate_connection_rules(candidates[0], raw)
        if connection_error:
            return self._build_evidence(
                criterion,
                status="nao_cumprido",
                element=self._element_ref(candidates[0]),
                observation=connection_error,
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

    @staticmethod
    def _get_shape_name(shape: dict[str, Any]) -> str:
        for area in shape.get("textAreas") or []:
            txt = str(area.get("text", "")).strip()
            if txt:
                return txt
        return ""

    def _map_with_textual_heuristics(
        self,
        elements: list[dict[str, Any]],
        flows: list[dict[str, Any]],
        criterion: Criterion,
        shapes: list[dict[str, Any]] | None = None,
        connectivity: dict[str, Any] | None = None,
        lane_map: dict[str, Any] | None = None,
        event_map: dict[str, str] | None = None,
    ) -> BPMNEvidence:
        description = criterion.description.lower()

        start_events = [e for e in elements if e.get("type") == "startEvent"]
        end_events   = [e for e in elements if e.get("type") == "endEvent"]
        tasks        = [e for e in elements if str(e.get("type")) in {"task", "userTask", "serviceTask"}]
        # gateways from normalized elements are always empty for LucidChart BPMNGateway shapes;
        # use raw shapes when available.
        raw_gateways = [s for s in (shapes or []) if "Gateway" in s.get("class", "")]

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
            # Use raw shapes — normalized elements miss BPMNGateway class.
            if raw_gateways:
                gw_names = [self._get_shape_name(g) for g in raw_gateways]
                return self._build_evidence(
                    criterion,
                    status="nao_avaliado",
                    element="gateway",
                    observation=(
                        f"Gateway(s) presentes: {', '.join(filter(None, gw_names))} — "
                        "corretude do tipo ou comportamento requer julgamento."
                    ),
                )
            return self._build_evidence(
                criterion,
                status="nao_aplicavel",
                element="gateway",
                observation="Diagrama não possui gateways.",
            )

        if "atividade" in description or "task" in description or "tarefa" in description:
            # Lane-assignment criteria need spatial data — avoid a false cumprido.
            if "raia" in description or "lane" in description:
                lane_context = ""
                if lane_map and lane_map.get("has_lanes"):
                    all_lanes = [l for p in lane_map.get("pools", []) for l in p.get("lanes", [])]
                    pool_name = (lane_map["pools"][0].get("pool_name", "") if lane_map.get("pools") else "")
                    lane_context = (
                        f" Piscina '{pool_name}' com raias: {', '.join(all_lanes)}."
                        if all_lanes else ""
                    )
                return self._build_evidence(
                    criterion,
                    status="nao_avaliado",
                    element=criterion.description,
                    observation=(
                        f"Raias detectadas no diagrama.{lane_context} "
                        "Atribuição correta de tarefas requer dados espaciais e enunciado do processo."
                    ),
                )
            return self._exists_result(criterion, tasks, "task")

        if ("fluxo" in description or "sequence flow" in description) and (
            "nome" in description or "label" in description or "rótulo" in description or "rotulo" in description
        ):
            unnamed_flow = next((f for f in flows if not str(f.get("name", "")).strip()), None)
            if unnamed_flow:
                return self._build_evidence(
                    criterion,
                    status="nao_cumprido",
                    element=str(unnamed_flow.get("id", "sequenceFlow")),
                    observation="Fluxo de sequência sem nome.",
                )
            first = flows[0] if flows else None
            return self._build_evidence(
                criterion,
                status="cumprido" if first else "nao_cumprido",
                element=str(first.get("id")) if first else "sequenceFlow",
                observation=None if first else "Nenhum fluxo de sequência encontrado.",
            )

        return self._build_evidence(
            criterion,
            status="nao_avaliado",
            element=criterion.description,
            observation="Não foi possível coletar evidências suficientes para avaliar este critério.",
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
            )
        return Agent1Analyst._build_evidence(
            criterion,
            status="nao_cumprido",
            element=expected_label,
            observation=f"Elemento esperado não encontrado: {expected_label}.",
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
        shapes: list[dict[str, Any]] | None = None,
        lane_map: dict[str, Any] | None = None,
    ) -> str | None:
        """Determine if a criterion is not applicable to this diagram.

        Uses preprocessing data (shapes, lane_map) when available so that
        element types stripped by normalization (gateways, events, pools) are
        still visible to the applicability check.
        """
        raw = criterion.raw

        if raw.get("nao_aplicavel") is True or raw.get("not_applicable") is True:
            return "Marcado como não aplicável no checklist."
        if raw.get("aplicavel") is False or raw.get("applicable") is False:
            return "Marcado como não aplicável no checklist."

        description = criterion.description.lower()

        # Use preprocessing lane_map when available — normalized elements miss pools/lanes.
        if lane_map is not None:
            has_pool = bool(lane_map.get("pools"))
            has_lane = lane_map.get("has_lanes", False)
        else:
            has_pool = any(str(e.get("type")) == "pool" for e in elements)
            has_lane = any(str(e.get("type")) == "lane" for e in elements)

        has_subprocess = any(str(e.get("type")) == "subProcess" for e in elements)
        has_message_flow = any(
            str(f.get("type", "")).lower() in {"messageflow", "message_flow"} for f in flows
        )
        has_link_event = any(
            str(e.get("type", "")).lower() in {"linkcatchevent", "linkthrowevent"}
            for e in elements
        )
        # SI7 is now estrutural — its "interrompido" check never reaches here.
        # Keep the condition only for any future semi/interpretativo criterion with that text.
        has_interrupting_flow = any(
            f.get("is_interrupting") is True
            or str(f.get("type", "")).lower() == "interruptingflow"
            for f in flows
        )

        if (
            "message flow" in description
            or "messageflow" in description
            or "mensagem" in description
        ) and not (has_message_flow or has_pool or has_lane):
            return "Diagrama não possui pools/raias ou fluxos de mensagem."

        if "pool" in description and not has_pool:
            return "Diagrama não possui pool."

        if ("lane" in description or "raia" in description) and not has_lane:
            return "Diagrama não possui raia."

        if (
            "subprocess" in description
            or "sub-processo" in description
            or "subprocesso" in description
        ) and not has_subprocess:
            return "Diagrama não possui subprocesso."

        if (
            "link event" in description
            or "evento de link" in description
            or "eventos de link" in description
        ) and not has_link_event:
            return "Diagrama não possui eventos de link."

        if (
            "flow is interrupted" in description
            or "fluxo é interrompido" in description
            or "fluxo interrompido" in description
            or "interrompido" in description
        ) and not has_interrupting_flow:
            return "Diagrama não possui fluxos interrompidos."

        return None
