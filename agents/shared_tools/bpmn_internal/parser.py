from __future__ import annotations

import ast
import csv
import io
import json
import re
from pathlib import Path
from typing import Any
from agents.contracts import *

def read_bpmnassessment_file(file_path: str | Path) -> list[BPMNAssessment]:
    path = Path(file_path)
    json_raw = _read_json_file(path)
    to_return = json_raw["assessments"]
    return [BPMNAssessment(**val) for val in to_return]

def read_bpmnevidence_file(file_path: str | Path) -> list[BPMNEvidence]:
    path = Path(file_path)
    to_return = _read_json_file(path)
    return [BPMNEvidence(**val) for val in to_return]

def _read_json_file(path: Path) -> dict[Any]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ValueError(f"JSON inválido em {path}: esperado objeto no topo.")
    return data