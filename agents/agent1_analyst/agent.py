from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
from typing import Any

import structlog

from agents.contracts import BPMNEvidence


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
        diagram = self._normalize_diagram(payload.get("diagram", {}))
        checklist = payload.get("checklist", {})

        self.logger.info("agent1.start")
        self._validate_diagram(diagram)
        self.logger.info("agent1.diagram_loaded", elements=len(diagram.get("elements", [])), flows=len(diagram.get("flows", [])))

        criteria = self._extract_criteria(checklist)
        self.logger.info("agent1.criteria_loaded", total=len(criteria))

        evidences = [self._map_criterion(diagram=diagram, criterion=criterion) for criterion in criteria]
        self.logger.info("agent1.finished", total_evidences=len(evidences))
        return evidences

    def run_from_files(self, diagram_path: str | Path, checklist_path: str | Path) -> list[BPMNEvidence]:
        """Runs the mapper by loading diagram/checklist files from disk."""
        diagram = self._read_json_file(diagram_path)
        checklist = self._read_checklist_file(checklist_path)
        return self.run({"diagram": diagram, "checklist": checklist})

    @staticmethod
    def serialize(evidences: list[BPMNEvidence]) -> str:
        return json.dumps([asdict(item) for item in evidences], ensure_ascii=False, indent=2)

    @staticmethod
    def _read_json_file(file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            raise ValueError(f"JSON inválido em {path}: esperado objeto no topo.")
        return data

    @staticmethod
    def _read_checklist_file(file_path: str | Path) -> dict[str, Any]:
        path = Path(file_path)

        if path.suffix.lower() == ".json":
            return Agent1Analyst._read_json_file(path)

        raw_text = path.read_text(encoding="utf-8").strip()
        if not raw_text:
            raise ValueError(f"Checklist vazio em {path}.")

        parsed = Agent1Analyst._parse_tuple_list_checklist(raw_text)
        return {"criteria": parsed}

    @staticmethod
    def _parse_tuple_list_checklist(raw_text: str) -> list[dict[str, Any]]:
        try:
            data = ast.literal_eval(raw_text)
        except (ValueError, SyntaxError) as exc:
            raise ValueError(
                "Checklist TXT inválido: esperado formato de lista de tuplas "
                "[(categoria, descricao), ...]."
            ) from exc

        if not isinstance(data, list):
            raise ValueError("Checklist TXT inválido: esperado uma lista.")

        counters: dict[str, int] = {}
        criteria: list[dict[str, Any]] = []

        for item in data:
            if not isinstance(item, tuple) or len(item) != 2:
                raise ValueError(
                    "Checklist TXT inválido: cada item deve ser uma tupla (categoria, descricao)."
                )

            category_raw, description = item
            category = str(category_raw).strip()
            desc = str(description).strip()
            if not category or not desc:
                raise ValueError("Checklist TXT inválido: categoria e descrição não podem ser vazias.")

            normalized_category = Agent1Analyst._normalize_category_label(category)
            counters[normalized_category] = counters.get(normalized_category, 0) + 1
            criterion_id = f"{normalized_category}_{counters[normalized_category]}"

            criteria.append(
                {
                    "criterion_id": criterion_id,
                    "category": normalized_category,
                    "description": desc,
                    "source_category": category,
                }
            )

        return criteria

    @staticmethod
    def _normalize_category_label(raw_category: str) -> str:
        category = raw_category.strip().lower()
        category = re.sub(r"\(.*?\)", "", category).strip()

        if "sintaxe" in category:
            return "syntax"
        if "semântica" in category or "semantica" in category:
            return "semantics"
        if "boas pr" in category:
            return "best_practices"
        if "modelagem alinhada" in category or "proposta" in category:
            return "proposal"
        if "legibilidade" in category:
            return "readability"

        sanitized = re.sub(r"[^a-z0-9]+", "_", category).strip("_")
        return sanitized or "criteria"

    @staticmethod
    def _validate_diagram(diagram: dict[str, Any]) -> None:
        if "elements" not in diagram or not isinstance(diagram.get("elements"), list):
            raise ValueError("Diagrama inválido: não foi possível identificar a lista de elementos.")
        if "flows" in diagram and not isinstance(diagram.get("flows"), list):
            raise ValueError("Diagrama inválido: campo 'flows' deve ser uma lista.")

    @staticmethod
    def _normalize_diagram(diagram: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(diagram, dict):
            raise ValueError("Diagrama inválido: esperado objeto JSON.")

        elements = Agent1Analyst._pick_first_list(
            diagram,
            keys=[
                "elements",
                "elemnts",
                "elementos",
                "nodes",
                "activities",
                "objects",
                "bpmn_elements",
                "items",
            ],
        )
        flows = Agent1Analyst._pick_first_list(
            diagram,
            keys=[
                "flows",
                "sequenceFlows",
                "sequence_flows",
                "connections",
                "edges",
                "fluxos",
                "links",
            ],
            default=[],
        )

        if elements is None and "diagram" in diagram and isinstance(diagram["diagram"], dict):
            return Agent1Analyst._normalize_diagram(diagram["diagram"])

        if elements is None:
            elements = Agent1Analyst._find_elements_recursively(diagram)
        if not flows:
            flows = Agent1Analyst._find_flows_recursively(diagram)

        normalized = dict(diagram)
        if elements is not None:
            normalized["elements"] = elements
        if flows is not None:
            normalized["flows"] = flows
        return normalized

    @staticmethod
    def _pick_first_list(
        data: dict[str, Any],
        keys: list[str],
        default: list[Any] | None = None,
    ) -> list[dict[str, Any]] | list[Any] | None:
        for key in keys:
            value = data.get(key)
            if isinstance(value, list):
                return value
        return default

    @staticmethod
    def _find_elements_recursively(data: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                if Agent1Analyst._looks_like_bpmn_element(node):
                    candidates.append(node)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(data)

        unique: list[dict[str, Any]] = []
        seen: set[str] = set()
        for item in candidates:
            key = str(item.get("id") or id(item))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    @staticmethod
    def _find_flows_recursively(data: Any) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []

        def visit(node: Any) -> None:
            if isinstance(node, dict):
                if Agent1Analyst._looks_like_flow(node):
                    normalized = dict(node)
                    if "source" not in normalized and "sourceRef" in normalized:
                        normalized["source"] = normalized.get("sourceRef")
                    if "target" not in normalized and "targetRef" in normalized:
                        normalized["target"] = normalized.get("targetRef")
                    candidates.append(normalized)
                for value in node.values():
                    visit(value)
            elif isinstance(node, list):
                for item in node:
                    visit(item)

        visit(data)
        return candidates

    @staticmethod
    def _looks_like_bpmn_element(node: dict[str, Any]) -> bool:
        node_type = node.get("type")
        if not isinstance(node_type, str):
            return False

        normalized_type = node_type.strip()
        if not normalized_type:
            return False

        return any(key in node for key in ("id", "name", "incoming", "outgoing"))

    @staticmethod
    def _looks_like_flow(node: dict[str, Any]) -> bool:
        return ("source" in node and "target" in node) or ("sourceRef" in node and "targetRef" in node)

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
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="absent",
                element=target,
                observation=None,
            )

        if exact_occ is not None and len(candidates) != int(exact_occ):
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="incorrect",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado exatamente {int(exact_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        if min_occ is not None and len(candidates) < int(min_occ):
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="incorrect",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado no mínimo {int(min_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        if max_occ is not None and len(candidates) > int(max_occ):
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="incorrect",
                element=self._element_ref(candidates[0]),
                observation=f"Esperado no máximo {int(max_occ)} ocorrência(s), encontrado {len(candidates)}.",
            )

        connection_error = self._validate_connection_rules(candidates[0], raw)
        if connection_error:
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="incorrect",
                element=self._element_ref(candidates[0]),
                observation=connection_error,
            )

        if raw.get("require_named_flows") is True:
            unnamed_flow = next((flow for flow in flows if not str(flow.get("name", "")).strip()), None)
            if unnamed_flow:
                return BPMNEvidence(
                    criterion_id=criterion.criterion_id,
                    category=criterion.category,
                    status="incorrect",
                    element=str(unnamed_flow.get("id", "sequenceFlow")),
                    observation="Fluxo de sequência sem nome.",
                )

        return BPMNEvidence(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            status="present",
            element=self._element_ref(candidates[0]),
            observation=None,
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

        if "início" in description or "inicio" in description or "start event" in description:
            return self._exists_result(criterion, start_events, "startEvent")

        if "fim" in description or "end event" in description:
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
                return BPMNEvidence(
                    criterion_id=criterion.criterion_id,
                    category=criterion.category,
                    status="incorrect",
                    element=str(unnamed_flow.get("id", "sequenceFlow")),
                    observation="Fluxo de sequência sem nome.",
                )
            first = flows[0] if flows else None
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="present" if first else "absent",
                element=str(first.get("id")) if first else "sequenceFlow",
                observation=None,
            )

        return BPMNEvidence(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            status="present",
            element=criterion.description,
            observation=None,
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
            return BPMNEvidence(
                criterion_id=criterion.criterion_id,
                category=criterion.category,
                status="present",
                element=Agent1Analyst._element_ref(candidates[0]),
                observation=None,
            )
        return BPMNEvidence(
            criterion_id=criterion.criterion_id,
            category=criterion.category,
            status="absent",
            element=expected_label,
            observation=None,
        )

    @staticmethod
    def _element_ref(element: dict[str, Any]) -> str:
        element_id = str(element.get("id", "unknown"))
        name = str(element.get("name", "")).strip()
        if name:
            return f"{name} ({element_id})"
        return element_id
