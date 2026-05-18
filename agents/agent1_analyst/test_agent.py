from pathlib import Path

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

    assert by_id["c1"].status == "present"
    assert by_id["c2"].status == "absent"
    assert by_id["c3"].status == "incorrect"


def test_agent1_accepts_checklist_grouped_by_category() -> None:
    diagram = {"elements": [], "flows": []}
    checklist = {
        "syntax": [{"id": "s1", "description": "Start event obrigatório"}],
        "semantics": [{"id": "m1", "description": "Evento de fim obrigatório"}],
    }

    evidences = Agent1Analyst().run({"diagram": diagram, "checklist": checklist})

    assert len(evidences) == 2
    assert {e.category for e in evidences} == {"syntax", "semantics"}
    assert all(e.status == "absent" for e in evidences)


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
    assert evidences[0].status == "present"


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
    assert evidences[0].status == "present"
