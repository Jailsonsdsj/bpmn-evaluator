from __future__ import annotations

from typing import Any


def normalize_diagram(diagram: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(diagram, dict):
        raise ValueError("Diagrama inválido: esperado objeto JSON.")

    lucid = _normalize_lucidchart(diagram)
    if lucid is not None:
        normalized = dict(diagram)
        normalized["elements"] = lucid["elements"]
        normalized["flows"] = lucid["flows"]
        return normalized

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


def _normalize_lucidchart(diagram: dict[str, Any]) -> dict[str, Any] | None:
    pages = diagram.get("pages")
    if not isinstance(pages, list):
        return None

    elements: list[dict[str, Any]] = []
    flows: list[dict[str, Any]] = []

    for page in pages:
        items = page.get("items", {}) if isinstance(page, dict) else {}
        shapes = items.get("shapes", []) if isinstance(items, dict) else []
        lines = items.get("lines", []) if isinstance(items, dict) else []

        if isinstance(shapes, list):
            for shape in shapes:
                if not isinstance(shape, dict):
                    continue
                element = _lucidchart_shape_to_element(shape)
                if element:
                    elements.append(element)

        if isinstance(lines, list):
            for line in lines:
                if not isinstance(line, dict):
                    continue
                flow = _lucidchart_line_to_flow(line)
                if flow:
                    flows.append(flow)

    if not elements and not flows:
        return None

    _attach_lucidchart_flow_refs(elements, flows)
    return {"elements": elements, "flows": flows}


def _lucidchart_shape_to_element(shape: dict[str, Any]) -> dict[str, Any] | None:
    shape_id = shape.get("id")
    if not shape_id:
        return None

    class_name = str(shape.get("class", "")).strip()
    name = _lucidchart_shape_text(shape)
    element_type = _lucidchart_class_to_type(class_name, name)
    if not element_type:
        return None

    return {"id": shape_id, "type": element_type, "name": name, "incoming": [], "outgoing": []}


def _lucidchart_shape_text(shape: dict[str, Any]) -> str:
    text_areas = shape.get("textAreas")
    if isinstance(text_areas, list):
        for area in text_areas:
            if isinstance(area, dict) and area.get("text"):
                return str(area.get("text")).strip()
    return ""


def _lucidchart_class_to_type(class_name: str, name: str) -> str | None:
    if class_name == "DecisionBlock":
        return "exclusiveGateway"
    if class_name == "ProcessBlock":
        lowered = name.strip().lower()
        if lowered in {"início", "inicio", "start"}:
            return "startEvent"
        if lowered in {"fim", "end"}:
            return "endEvent"
        return "task"
    if class_name == "AdvancedSwimLaneBlock":
        return "pool"
    return None


def _lucidchart_line_to_flow(line: dict[str, Any]) -> dict[str, Any] | None:
    line_id = line.get("id")
    endpoint1 = line.get("endpoint1") if isinstance(line.get("endpoint1"), dict) else {}
    endpoint2 = line.get("endpoint2") if isinstance(line.get("endpoint2"), dict) else {}
    source = endpoint1.get("connectedTo")
    target = endpoint2.get("connectedTo")
    if not line_id or not source or not target:
        return None

    name = ""
    text_areas = line.get("textAreas")
    if isinstance(text_areas, list):
        for area in text_areas:
            if isinstance(area, dict) and area.get("text"):
                name = str(area.get("text")).strip()
                break

    flow: dict[str, Any] = {"id": line_id, "source": source, "target": target}
    if name:
        flow["name"] = name
    return flow


def _attach_lucidchart_flow_refs(elements: list[dict[str, Any]], flows: list[dict[str, Any]]) -> None:
    incoming_map: dict[str, list[str]] = {}
    outgoing_map: dict[str, list[str]] = {}

    for flow in flows:
        source = flow.get("source")
        target = flow.get("target")
        flow_id = flow.get("id")
        if not flow_id:
            continue
        if source:
            outgoing_map.setdefault(str(source), []).append(flow_id)
        if target:
            incoming_map.setdefault(str(target), []).append(flow_id)

    for element in elements:
        element_id = element.get("id")
        if not element_id:
            continue
        element["incoming"] = incoming_map.get(str(element_id), [])
        element["outgoing"] = outgoing_map.get(str(element_id), [])


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
