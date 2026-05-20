from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from anthropic import Anthropic
from dotenv import load_dotenv

from .normalize import normalize_diagram


def read_diagram_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        return _read_json_file(path)
    if suffix in {".png", ".jpg", ".jpeg"}:
        return _image_to_diagram_json(path)
    if suffix == ".pdf":
        return _pdf_to_diagram_json(path)

    raise ValueError("Formato de diagrama inválido: use .json, .pdf ou imagem (.png/.jpg/.jpeg).")


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido em {path}: esperado objeto no topo.")
    return data


def _image_to_diagram_json(path: Path) -> dict[str, Any]:
    media_type = _image_media_type(path)
    return _diagram_from_image_bytes(
        image_bytes=path.read_bytes(),
        media_type=media_type,
        source_label=path.name,
    )


def _pdf_to_diagram_json(path: Path) -> dict[str, Any]:
    try:
        import fitz  # PyMuPDF
    except Exception as exc:  # pragma: no cover - dependency missing
        raise ValueError("Para usar PDF, instale a dependência pymupdf.") from exc

    doc = fitz.open(path)
    try:
        if doc.page_count == 0:
            raise ValueError("PDF inválido: nenhuma página encontrada.")

        diagrams: list[dict[str, Any]] = []
        for page_index in range(doc.page_count):
            page = doc.load_page(page_index)
            pix = page.get_pixmap(dpi=200)
            image_bytes = pix.tobytes("png")
            diagram = _diagram_from_image_bytes(
                image_bytes=image_bytes,
                media_type="image/png",
                source_label=f"{path.name}#p{page_index + 1}",
            )
            diagrams.append(diagram)
    finally:
        doc.close()

    if len(diagrams) == 1:
        return diagrams[0]
    return _merge_diagrams(diagrams)


def _diagram_from_image_bytes(image_bytes: bytes, media_type: str, source_label: str) -> dict[str, Any]:
    load_dotenv()
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    model = os.getenv("MODEL_NAME", "").strip()

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY ausente. Configure no arquivo .env.")
    if not model:
        raise ValueError("MODEL_NAME ausente. Configure no arquivo .env.")

    image_data = base64.b64encode(image_bytes).decode("ascii")

    prompt = (
        "Converta o diagrama BPMN da imagem para JSON. "
        "Retorne SOMENTE um objeto JSON válido (sem markdown). "
        "Schema esperado:\n"
        "{\n"
        '  "id": "diagram_001",\n'
        '  "name": "Nome do processo",\n'
        '  "elements": [\n'
        '    {"id": "e1", "type": "startEvent", "name": "Start", "incoming": [], "outgoing": ["f1"]}\n'
        "  ],\n"
        '  "flows": [\n'
        '    {"id": "f1", "source": "e1", "target": "t1", "name": "label opcional"}\n'
        "  ]\n"
        "}\n"
        "Regras:\n"
        "- Use SOMENTE tipos válidos: startEvent, endEvent, task, userTask, serviceTask, "
        "exclusiveGateway, parallelGateway, inclusiveGateway, pool, lane, subProcess.\n"
        "- Use IDs simples e consistentes (e1, t1, g1, f1...).\n"
        "- Use nome vazio ('') quando não houver rótulo visível.\n"
        "- Preencha incoming/outgoing com IDs de fluxos quando possível; caso contrário, use [].\n"
        "- Não invente elementos que não estejam visíveis na imagem.\n"
        f"- Fonte: {source_label}\n"
    )

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=2000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {"type": "base64", "media_type": media_type, "data": image_data},
                    },
                    {"type": "text", "text": prompt},
                ],
            }
        ],
    )

    text = "".join(block.text for block in response.content if getattr(block, "type", "") == "text")
    return _parse_json_output(text)


def _image_media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".png":
        return "image/png"
    return "image/jpeg"


def _parse_json_output(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise ValueError("Resposta da LLM não contém JSON válido.")
        data = json.loads(cleaned[start : end + 1])

    if not isinstance(data, dict):
        raise ValueError("Resposta da LLM inválida: esperado objeto JSON.")
    return data


def _merge_diagrams(diagrams: list[dict[str, Any]]) -> dict[str, Any]:
    if not diagrams:
        return {"elements": [], "flows": []}

    merged: dict[str, Any] = {}
    merged["id"] = diagrams[0].get("id", "diagram_pdf")
    if diagrams[0].get("name"):
        merged["name"] = diagrams[0].get("name")
    merged["elements"] = []
    merged["flows"] = []

    for idx, diagram in enumerate(diagrams, start=1):
        normalized = normalize_diagram(diagram)
        prefixed = _prefix_diagram_ids(normalized, f"p{idx}_")
        merged["elements"].extend(prefixed.get("elements", []))
        merged["flows"].extend(prefixed.get("flows", []))

    return merged


def _prefix_diagram_ids(diagram: dict[str, Any], prefix: str) -> dict[str, Any]:
    elements = diagram.get("elements", [])
    flows = diagram.get("flows", [])
    element_id_map: dict[str, str] = {}
    flow_id_map: dict[str, str] = {}

    for element in elements:
        element_id = element.get("id")
        if element_id:
            new_id = f"{prefix}{element_id}"
            element_id_map[str(element_id)] = new_id
            element["id"] = new_id

    for flow in flows:
        flow_id = flow.get("id")
        if flow_id:
            new_id = f"{prefix}{flow_id}"
            flow_id_map[str(flow_id)] = new_id
            flow["id"] = new_id

    for element in elements:
        incoming = element.get("incoming")
        if isinstance(incoming, list):
            element["incoming"] = [flow_id_map.get(str(fid), f"{prefix}{fid}") for fid in incoming]

        outgoing = element.get("outgoing")
        if isinstance(outgoing, list):
            element["outgoing"] = [flow_id_map.get(str(fid), f"{prefix}{fid}") for fid in outgoing]

    for flow in flows:
        source = flow.get("source")
        if source:
            flow["source"] = element_id_map.get(str(source), f"{prefix}{source}")
        target = flow.get("target")
        if target:
            flow["target"] = element_id_map.get(str(target), f"{prefix}{target}")

    return diagram
