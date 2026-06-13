from dataclasses import dataclass


@dataclass
class BPMNEvidence:
    criterion_id: str
    category: str# syntax | proposal | semantics | best_practices | readability 
    status: str # cumprido | nao_cumprido | nao_aplicavel | nao_avaliado
    value: float # checklist penalty score to deduct if not met
    element: str | None = None
    observation: str | None = None
    question: str | None = None


@dataclass
class BPMNAssessment:
    criterion_id: str
    category: str
    category_weight: float
    status: str # cumprido | nao_cumprido | nao_aplicavel | nao_avaliado
    checklist_penalty: float
    applied_penalty: float # 0.0 for cumprido/nao_aplicavel/nao_avaliado; equals checklist_penalty for nao_cumprido
    justification: str
    confidence: float
    flag_review: bool
    element: str | None = None
    plan_log: str | None = None
    question: str | None = None
    
@dataclass
class ItemGrade:
    value: float
    category: str

# TODO: Esse não é o contrato definitivo
@dataclass
class BPMNFeedback:
    grades_and_feedbacks: list[tuple[ItemGrade, str]]

