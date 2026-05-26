from dataclasses import dataclass


@dataclass
class BPMNEvidence:
    criterion_id: str
    category: str               # syntax | proposal | semantics | best_practices | readability
    status: str                 # cumprido | nao_cumprido | nao_aplicavel
    value: float                # checklist penalty score to deduct if not met
    element: str
    observation: str | None = None
    question: str | None = None


@dataclass
class BPMNAssessment:
    criterion_id: str
    category: str
    category_weight: float
    status: str
    checklist_penalty: float
    applied_penalty: float
    justification: str
    confidence: float
    flag_review: bool
    plan_log: str | None = None
    
@dataclass
class ItemGrade:
    value: float
    category: str

# TODO: Esse não é o contrato definitivo
@dataclass
class BPMNFeedback:
    grades_and_feedbacks: list[tuple[ItemGrade, str]]

