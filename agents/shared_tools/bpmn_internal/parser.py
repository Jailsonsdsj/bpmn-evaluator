from __future__ import annotations

import ast
import csv
import io
import json
import re
from pathlib import Path
from typing import Any
from agents.contracts import *

def read_bpmnassessment_file(file_path: str | Path) -> dict[str, list[BPMNAssessment]]:
    path = Path(file_path)
    return _read_json_file(path)

def write_bpmnassessment_file(file_path: str | Path, value: list[BPMNAssessment]):
    to_json = value
    path = Path(file_path)
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_json, file, ensure_ascii=True, indent=2)

def _read_json_file(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido em {path}: esperado objeto no topo.")
    return data