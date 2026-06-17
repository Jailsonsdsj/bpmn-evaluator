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
class CategoryGrade:
    category: str
    weight: float       # global checklist weight (e.g. 0.30 for syntax)
    max_score: float    # weight * 10
    penalty: float      # sum of applied_penalty of nao_cumprido items in the category
    score: float        # max(0, max_score - penalty)


@dataclass
class FeedbackItem:
    criterion_id: str
    category: str
    question: str
    element: str | None
    applied_penalty: float
    feedback: str       # personalized formative feedback (where, why it matters, how to fix)


# Agent 3 final report — espelho da saída exigida na especificação:
# (1) nota final por categoria e total, (2) feedback por erro com sugestão
# de correção, (3) resumo dos acertos, + texto legível ao estudante.
@dataclass
class BPMNFeedback:
    final_grade: float                      # 0..10, computed deterministically in Python
    category_grades: list[CategoryGrade]
    feedback_items: list[FeedbackItem]      # one per nao_cumprido item
    strengths: list[str]                    # criteria the student got right (resumo dos acertos)
    student_report: str                     # Markdown report written for the student

