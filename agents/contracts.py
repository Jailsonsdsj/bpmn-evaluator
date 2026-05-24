from dataclasses import dataclass


@dataclass
class BPMNEvidence:
    criterion_id: str
    category: str
    status: str
    value: float
    element: str
    observation: str | None = None
    question: str | None = None


@dataclass
class BPMNAssessment:
    criterion_id: str
    category: str
    penalty: float
    justification: str
    confidence: float
    flag_review: bool
    plan_log: str | None = None
