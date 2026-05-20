from __future__ import annotations

from typing import Any


def normalize_diagram(diagram: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(diagram, dict):
        raise ValueError("Diagrama inválido: esperado objeto JSON.")

    elements = _pick_first_list(
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
    flows = _pick_first_list(
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
        return normalize_diagram(diagram["diagram"])

    if elements is None:
        elements = _find_elements_recursively(diagram)
    if not flows:
        flows = _find_flows_recursively(diagram)

    normalized = dict(diagram)
    if elements is not None:
        normalized["elements"] = elements
    if flows is not None:
        normalized["flows"] = flows
    return normalized


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


def _find_elements_recursively(data: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if _looks_like_bpmn_element(node):
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


def _find_flows_recursively(data: Any) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if _looks_like_flow(node):
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


def _looks_like_bpmn_element(node: dict[str, Any]) -> bool:
    node_type = node.get("type")
    if not isinstance(node_type, str):
        return False

    normalized_type = node_type.strip()
    if not normalized_type:
        return False

    return any(key in node for key in ("id", "name", "incoming", "outgoing"))


def _looks_like_flow(node: dict[str, Any]) -> bool:
    return ("source" in node and "target" in node) or ("sourceRef" in node and "targetRef" in node)
