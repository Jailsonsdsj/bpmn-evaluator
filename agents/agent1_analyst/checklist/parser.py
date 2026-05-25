from __future__ import annotations

import ast
import csv
import io
import json
import re
from pathlib import Path
from typing import Any


def read_checklist_file(file_path: str | Path) -> dict[str, Any]:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".json":
        return _read_json_file(path)
    if suffix == ".csv":
        return {"criteria": parse_csv_checklist(path)}

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError(f"Checklist vazio em {path}.")

    parsed = parse_tuple_list_checklist(raw_text)
    return {"criteria": parsed}


def parse_csv_checklist(path: Path) -> list[dict[str, Any]]:
    raw_text = path.read_text(encoding="utf-8-sig")
    if not raw_text.strip():
        raise ValueError(f"Checklist CSV vazio em {path}.")

    dialect = csv.excel
    try:
        dialect = csv.Sniffer().sniff(raw_text[:4096])
    except csv.Error:
        pass

    rows = list(csv.reader(io.StringIO(raw_text), dialect))

    if not rows:
        raise ValueError(f"Checklist CSV vazio em {path}.")

    header_idx = None
    category_idx = None
    item_idx = None
    criteria_idx = None
    score_general_idx = None
    score_equiv_idx = None
    for idx, row in enumerate(rows):
        normalized = [_normalize_header_cell(cell) for cell in row]
        category_idx = _find_header_index(normalized, ["categoria"])
        item_idx = _find_header_index(normalized, ["itens avaliados"])
        criteria_idx = _find_header_index(normalized, ["criterios avaliados", "critérios avaliados"])
        score_general_idx = _find_header_index(normalized, ["pontuação geral", "pontuacao geral"])
        score_equiv_idx = _find_header_index(
            normalized,
            [
                "pontuação equivalente - utilizar esta coluna para descontar a nota",
                "pontuacao equivalente - utilizar esta coluna para descontar a nota",
                "pontuação equivalente",
                "pontuacao equivalente",
            ],
        )
        if category_idx is not None and item_idx is not None:
            header_idx = idx
            break

    if header_idx is None or category_idx is None or item_idx is None:
        raise ValueError(
            "Checklist CSV inválido: cabeçalho não encontrado (esperado 'Categoria' e 'Itens avaliados')."
        )

    counters: dict[str, int] = {}
    criteria: list[dict[str, Any]] = []
    last_category: str | None = None

    for row_idx, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
        category_cell = row[category_idx].strip() if len(row) > category_idx else ""
        item_cell = row[item_idx].strip() if len(row) > item_idx else ""

        if category_cell:
            last_category = category_cell

        if not item_cell:
            item_cell = _fallback_item_cell(row, criteria_idx)
        if not item_cell:
            continue

        if not last_category:
            raise ValueError(f"Checklist CSV inválido: categoria ausente na linha {row_idx}.")

        normalized_category = normalize_category_label(last_category)
        counters[normalized_category] = counters.get(normalized_category, 0) + 1
        criterion_id = f"{normalized_category}_{counters[normalized_category]}"

        score_equiv = _parse_score(_get_cell(row, score_equiv_idx))
        score_general = _parse_score(_get_cell(row, score_general_idx))
        score = _select_score(score_equiv, score_general)

        criteria.append(
            {
                "criterion_id": criterion_id,
                "category": normalized_category,
                "description": item_cell,
                "source_category": last_category,
                "source_row": row_idx,
                "score": score,
            }
        )

    if not criteria:
        raise ValueError(
            "Checklist CSV inválido: nenhum item encontrado na coluna 'Itens avaliados'."
        )

    return criteria


def parse_tuple_list_checklist(raw_text: str) -> list[dict[str, Any]]:
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

        normalized_category = normalize_category_label(category)
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


def normalize_category_label(raw_category: str) -> str:
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


def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido em {path}: esperado objeto no topo.")
    return data


def _normalize_header_cell(cell: str) -> str:
    return cell.replace("\ufeff", "").replace("\u200b", "").strip().lower()


def _find_header_index(normalized: list[str], candidates: list[str]) -> int | None:
    for candidate in candidates:
        if candidate in normalized:
            return normalized.index(candidate)
    for idx, cell in enumerate(normalized):
        for candidate in candidates:
            if candidate in cell:
                return idx
    return None


def _get_cell(row: list[str], index: int | None) -> str:
    if index is None or len(row) <= index:
        return ""
    return row[index].strip()


def _fallback_item_cell(row: list[str], criteria_idx: int | None) -> str:
    if criteria_idx is not None and len(row) > criteria_idx:
        candidate = row[criteria_idx].strip()
        if candidate:
            return candidate

    for cell in row:
        candidate = cell.strip()
        if not candidate:
            continue
        lowered = candidate.lower()
        if lowered in {"sim", "não", "nao"}:
            continue
        if re.fullmatch(r"[\d.,%]+", candidate):
            continue
        if "?" in candidate or len(candidate) > 3:
            return candidate

    return ""


def _parse_score(value: str) -> float | None:
    if not value:
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


def _select_score(score_equiv: float | None, score_general: float | None) -> float | None:
    if score_equiv is not None and score_equiv != 0:
        return score_equiv
    if score_general is not None:
        return score_general
    return score_equiv
