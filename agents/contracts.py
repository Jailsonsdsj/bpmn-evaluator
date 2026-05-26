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
    category_weight: float      # global weight of the category (e.g. 0.30 for syntax)
    status: str                 # cumprido | nao_cumprido | nao_aplicavel
    checklist_penalty: float    # penalty value COPIED from the checklist (not computed)
    applied_penalty: float      # 0.0 if cumprido/nao_aplicavel; equals checklist_penalty if nao_cumprido
    justification: str          # Agent 2's reasoning validating the finding
    confidence: float           # 0.0–1.0 (never inflate)
    flag_review: bool           # True if confidence < CONFIDENCE_THRESHOLD
    plan_log: str | None = None  # Agent 2's analysis plan (only on the first item)
