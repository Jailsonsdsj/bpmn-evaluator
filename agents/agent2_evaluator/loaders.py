from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any

from agents.contracts import BPMNEvidence

# Fallback weights used only when the "%" suffix is absent from the Categoria cell.
# Primary source: the percentage embedded in the CSV category text (e.g. "sintaxe 30%").
CATEGORY_WEIGHTS: dict[str, float] = {
    "syntax": 0.30,
    "proposal": 0.20,
    "semantics": 0.20,
    "best_practices": 0.20,
    "readability": 0.10,
}


def load_evidence(path: str | Path) -> list[BPMNEvidence]:
    """Read a BPMNEvidence JSON file and return a list of BPMNEvidence instances."""
    raw = Path(path).read_text(encoding="utf-8")
    items: list[dict[str, Any]] = json.loads(raw)
    return [
        BPMNEvidence(
            criterion_id=item["criterion_id"],
            category=item["category"],
            status=item["status"],
            value=item["value"],
            element=item["element"],
            observation=item.get("observation"),
            question=item.get("question"),
        )
        for item in items
    ]


def load_checklist(path: str | Path) -> dict[str, dict[str, Any]]:
    """Read a checklist CSV and return a dict keyed by criterion_id.

    Each value contains:
      - category: normalized category name
      - category_weight: percentage weight of the category (0.0–1.0)
      - checklist_penalty: point deduction for this criterion
      - description: the criterion question text
    """
    raw = Path(path).read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(raw[:4096])
    except csv.Error:
        dialect = csv.excel

    rows = list(csv.reader(io.StringIO(raw), dialect))

    header_idx = _find_header_row(rows)
    if header_idx is None:
        raise ValueError("Checklist CSV inválido: cabeçalho não encontrado.")

    col = _detect_columns(rows[header_idx])

    result: dict[str, dict[str, Any]] = {}
    counters: dict[str, int] = {}
    last_raw_category: str | None = None

    for row in rows[header_idx + 1 :]:
        if len(row) <= col["item"]:
            continue

        category_cell = row[col["category"]].strip() if len(row) > col["category"] else ""
        item_cell = row[col["item"]].strip() if len(row) > col["item"] else ""
        penalty_cell = row[col["penalty"]].strip() if col["penalty"] is not None and len(row) > col["penalty"] else ""

        if category_cell:
            last_raw_category = category_cell
        if not item_cell or not last_raw_category:
            continue

        normalized = _normalize_category(last_raw_category)
        weight = _extract_weight(last_raw_category, normalized)
        counters[normalized] = counters.get(normalized, 0) + 1
        criterion_id = f"{normalized}_{counters[normalized]}"
        penalty = _parse_penalty(penalty_cell)

        result[criterion_id] = {
            "category": normalized,
            "category_weight": weight,
            "checklist_penalty": penalty,
            "description": item_cell,
        }

    return result


def _find_header_row(rows: list[list[str]]) -> int | None:
    for idx, row in enumerate(rows):
        normalized = [c.replace("﻿", "").strip().lower() for c in row]
        if "categoria" in normalized and "itens avaliados" in normalized:
            return idx
    return None


def _detect_columns(header_row: list[str]) -> dict[str, Any]:
    normalized = [c.replace("﻿", "").strip().lower() for c in header_row]

    def find(candidates: list[str]) -> int | None:
        for cand in candidates:
            if cand in normalized:
                return normalized.index(cand)
        return None

    return {
        "category": find(["categoria"]) or 0,
        "item": find(["itens avaliados"]) or 1,
        "penalty": find(["pontuação geral", "pontuacao geral", "pontuação", "score"]),
    }


def _normalize_category(raw: str) -> str:
    lower = re.sub(r"\(.*?\)", "", raw).strip().lower()
    if "sintaxe" in lower:
        return "syntax"
    if "semântica" in lower or "semantica" in lower:
        return "semantics"
    if "boas pr" in lower:
        return "best_practices"
    if "modelagem alinhada" in lower or "proposta" in lower:
        return "proposal"
    if "legibilidade" in lower:
        return "readability"
    return re.sub(r"[^a-z0-9]+", "_", lower).strip("_") or "criteria"


def _extract_weight(raw_category: str, normalized: str) -> float:
    # Primary: parse "30%" from the Categoria cell text (e.g. "sintaxe 30%").
    # Fallback: CATEGORY_WEIGHTS constant when the suffix is absent.
    match = re.search(r"(\d+)\s*%", raw_category)
    if match:
        return int(match.group(1)) / 100.0
    return CATEGORY_WEIGHTS.get(normalized, 0.0)


def _parse_penalty(cell: str) -> float:
    cleaned = cell.replace(",", ".").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
