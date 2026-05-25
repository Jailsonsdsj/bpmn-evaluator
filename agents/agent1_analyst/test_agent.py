from pathlib import Path

import pytest

from agents.agent1_analyst import Agent1Analyst


def test_agent1_maps_present_absent_and_incorrect() -> None:
    diagram = {
        "id": "diagram_001",
        "elements": [
            {"id": "e1", "type": "startEvent", "name": "Start", "outgoing": ["f1"]},
            {"id": "t1", "type": "task", "name": "Task A", "incoming": ["f1"], "outgoing": []},
        ],
        "flows": [{"id": "f1", "source": "e1", "target": "t1"}],
    }
    checklist = {
        "criteria": [
            {"id": "c1", "category": "syntax", "description": "Deve existir evento de início"},
            {"id": "c2", "category": "syntax", "element_type": "endEvent"},
            {
                "id": "c3",
                "category": "syntax",
                "element_type": "task",
                "require_outgoing": True,
            },
        ]
    }

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})
    by_id = {item.criterion_id: item for item in evidences}

    assert by_id["c1"].status == "cumprido"
    assert by_id["c2"].status == "nao_cumprido"
    assert by_id["c3"].status == "nao_cumprido"
    assert by_id["c1"].question == "Deve existir evento de início"
    assert by_id["c1"].value == 1.0
    assert by_id["c2"].value == 0.0
    assert by_id["c3"].value == 0.0


def test_agent1_accepts_checklist_grouped_by_category() -> None:
    diagram = {"elements": [], "flows": []}
    checklist = {
        "syntax": [{"id": "s1", "description": "Start event obrigatório"}],
        "semantics": [{"id": "m1", "description": "Evento de fim obrigatório"}],
    }

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 2
    assert {e.category for e in evidences} == {"syntax", "semantics"}
    assert all(e.status == "nao_cumprido" for e in evidences)


def test_agent1_accepts_txt_tuple_checklist(tmp_path: Path) -> None:
    diagram_path = tmp_path / "diagram.json"
    checklist_path = tmp_path / "checklist.txt"

    diagram_path.write_text(
        """{
  "id": "diagram_001",
  "elements": [{"id":"e1","type":"startEvent","name":"Start","outgoing":["f1"]}],
  "flows": [{"id":"f1","source":"e1","target":"e1","name":"loop"}]
}""",
        encoding="utf-8",
    )
    checklist_path.write_text(
        """[
    ('sintaxe (4 pts)', 'O evento inicial foi definido?'),
    ('Semântica (1 pts)', 'Todas as tarefas possuem fluxo de saída?')
]""",
        encoding="utf-8",
    )

    evidences = Agent1Analyst().run_from_files(diagram_path, checklist_path)

    assert len(evidences) == 2
    assert evidences[0].category == "syntax"
    assert evidences[1].category == "semantics"


def test_agent1_accepts_csv_checklist(tmp_path: Path) -> None:
    diagram_path = tmp_path / "diagram.json"
    checklist_path = tmp_path / "checklist.csv"

    diagram_path.write_text(
        """{
  "id": "diagram_001",
  "elements": [],
  "flows": []
}""",
        encoding="utf-8",
    )
    checklist_path.write_text(
        """,,
Categoria,Itens avaliados,Resposta
sintaxe 30%,O evento inicial foi definido?,Sim
,Evento final foi definido?,Sim
Semântica 20%,Todas as tarefas possuem fluxo de saída?,Sim
""",
        encoding="utf-8",
    )

    evidences = Agent1Analyst().run_from_files(diagram_path, checklist_path)

    assert len(evidences) == 3
    assert evidences[0].category == "syntax"
    assert evidences[1].category == "syntax"
    assert evidences[2].category == "semantics"


def test_agent1_csv_uses_score_value(tmp_path: Path) -> None:
    diagram_path = tmp_path / "diagram.json"
    checklist_path = tmp_path / "checklist.csv"

    diagram_path.write_text(
        """{
  "id": "diagram_001",
  "elements": [{"id":"e1","type":"startEvent","name":"Start","outgoing":["f1"]}],
  "flows": [{"id":"f1","source":"e1","target":"e1","name":"loop"}]
}""",
        encoding="utf-8",
    )
    checklist_path.write_text(
        """,,
Categoria,Itens avaliados,Pontuação geral
sintaxe 30%,O evento inicial foi definido?,"0,2"
""",
        encoding="utf-8",
    )

    evidences = Agent1Analyst().run_from_files(diagram_path, checklist_path)

    assert len(evidences) == 1
    assert evidences[0].status == "cumprido"
    assert evidences[0].value == 0.2


def test_agent1_csv_fallback_criteria_column(tmp_path: Path) -> None:
    diagram_path = tmp_path / "diagram.json"
    checklist_path = tmp_path / "checklist.csv"

    diagram_path.write_text(
        """{
  "id": "diagram_001",
  "elements": [],
  "flows": []
}""",
        encoding="utf-8",
    )
    checklist_path.write_text(
        """,,
Categoria,Itens avaliados,Resposta,Feedback,Pontuação geral,Critérios avaliados
Boas práticas 20%,,Sim,,,"“São usados nomes breves e objetivos para os eventos, os gateways e as atividades?”"
""",
        encoding="utf-8",
    )

    evidences = Agent1Analyst().run_from_files(diagram_path, checklist_path)

    assert len(evidences) == 1
    assert evidences[0].category == "best_practices"


def test_agent1_accepts_alternative_diagram_keys() -> None:
    diagram = {
        "nodes": [
            {"id": "e1", "type": "startEvent", "name": "Start", "outgoing": ["f1"]},
            {"id": "t1", "type": "task", "name": "Task A", "incoming": ["f1"], "outgoing": ["f2"]},
        ],
        "connections": [
            {"id": "f1", "source": "e1", "target": "t1", "name": "to task"},
            {"id": "f2", "source": "t1", "target": "t1", "name": "loop"},
        ],
    }
    checklist = {"criteria": [{"id": "c1", "category": "syntax", "description": "O evento inicial foi definido?"}]}

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 1
    assert evidences[0].status == "cumprido"


def test_agent1_default_to_absent_when_no_match() -> None:
    diagram = {"elements": [], "flows": []}
    checklist = {"criteria": [{"id": "c1", "category": "syntax", "description": "Critério não mapeado"}]}

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 1
    assert evidences[0].status == "nao_cumprido"


def test_agent1_finds_elements_in_nested_structure() -> None:
    diagram = {
        "model": {
            "processes": [
                {
                    "shapes": [
                        {"id": "e1", "type": "startEvent", "name": "Start", "outgoing": ["f1"]},
                        {"id": "t1", "type": "task", "name": "Task A", "incoming": ["f1"], "outgoing": []},
                    ],
                    "connectors": [{"id": "f1", "sourceRef": "e1", "targetRef": "t1", "name": "go"}],
                }
            ]
        }
    }
    checklist = {"criteria": [{"id": "c1", "category": "syntax", "description": "O evento inicial foi definido?"}]}

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 1
    assert evidences[0].status == "cumprido"


def test_agent1_handles_lucidchart_shapes() -> None:
    diagram = {
        "pages": [
            {
                "items": {
                    "shapes": [
                        {"id": "s1", "class": "ProcessBlock", "textAreas": [{"label": "Text", "text": "INÍCIO"}]},
                        {
                            "id": "s2",
                            "class": "DecisionBlock",
                            "textAreas": [{"label": "Text", "text": "Decisão"}],
                        },
                    ],
                    "lines": [
                        {
                            "id": "l1",
                            "endpoint1": {"connectedTo": "s1"},
                            "endpoint2": {"connectedTo": "s2"},
                        }
                    ],
                }
            }
        ]
    }
    checklist = {
        "criteria": [
            {"id": "c1", "category": "syntax", "description": "O evento inicial foi definido?"},
            {"id": "c2", "category": "syntax", "description": "Os desvios (Gateway) possuem mais de um fluxo?"},
        ]
    }

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 2
    assert evidences[0].status == "cumprido"


def test_agent1_image_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diagram_path = tmp_path / "diagram.png"
    checklist_path = tmp_path / "checklist.txt"

    diagram_path.write_bytes(b"\x89PNG\r\n\x1a\n")
    checklist_path.write_text(
        """[
    ('sintaxe (4 pts)', 'O evento inicial foi definido?')
]""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("MODEL_NAME", "")

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY ausente"):
        Agent1Analyst().run_from_files(diagram_path, checklist_path)


def test_agent1_pdf_requires_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    try:
        import fitz  # PyMuPDF
    except Exception:
        pytest.skip("PyMuPDF não disponível.")

    diagram_path = tmp_path / "diagram.pdf"
    checklist_path = tmp_path / "checklist.txt"

    doc = fitz.open()
    doc.new_page()
    doc.save(diagram_path)
    doc.close()

    checklist_path.write_text(
        """[
    ('sintaxe (4 pts)', 'O evento inicial foi definido?')
]""",
        encoding="utf-8",
    )

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("MODEL_NAME", "")

    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY ausente"):
        Agent1Analyst().run_from_files(diagram_path, checklist_path)
def test_agent1_marks_not_applicable_for_pool_criteria_without_pools() -> None:
    diagram = {
        "elements": [{"id": "e1", "type": "startEvent", "name": "Start", "outgoing": []}],
        "flows": [],
    }
    checklist = {"criteria": [{"id": "c1", "category": "syntax", "description": "Critério de pool único"}]}

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert evidences[0].status == "nao_aplicavel"
    assert evidences[0].value == 0.0
