# Agent 2 — Critic Validator

Agent 2 receives the evidence list produced by Agent 1 and validates each finding before scoring. It does **not** decide penalties — those are copied directly from `BPMNEvidence.value`. Its job is to assess whether Agent 1's judgment is well-supported and to assign a calibrated confidence score per criterion.

---

## Responsibility

1. **Validate judgment** — for each `BPMNEvidence` item, assess whether the status (`cumprido` / `nao_cumprido` / `nao_aplicavel`) is supported by the available observation.
2. **Resolve `nao_aplicavel` cases** — confirm that out-of-scope criteria genuinely do not apply to the diagram.
3. **Assign confidence** — conservative 0.0–1.0 score; items below `CONFIDENCE_THRESHOLD` are flagged for human review.
4. **Copy penalties** — `checklist_penalty` is copied from `evidence.value`; `applied_penalty` is set deterministically from status (never by the LLM).

---

## Agentic patterns

| Pattern | Where |
|---|---|
| Planning | `planning.py` — one LLM call generates a per-category analysis plan before any evaluation |
| Reflection (Producer-Critic) | `evaluator.py` — up to `MAX_ITERATIONS` critique passes refine weak-confidence items |

---

## Input

A list of `BPMNEvidence` objects (JSON file), one per checklist criterion:

```json
[
  {
    "criterion_id": "syntax_1",
    "category": "syntax",
    "status": "nao_cumprido",
    "value": 0.20,
    "element": "sequenceFlow",
    "observation": null,
    "question": "O conector \"fluxo de sequência\" está sendo utilizado apenas entre raias?"
  }
]
```

| Field | Description |
|---|---|
| `criterion_id` | Matches the checklist CSV row (e.g. `syntax_1`) |
| `status` | `cumprido` \| `nao_cumprido` \| `nao_aplicavel` |
| `value` | Checklist penalty to deduct if the criterion fails |
| `element` | Diagram element involved |
| `observation` | Agent 1's description of the problem (may be `null`) |
| `question` | The criterion text from the checklist |

The checklist CSV is also required — used **only** to look up `category_weight` per criterion.

---

## Output

A JSON file with two top-level keys:

```json
{
  "summary": {
    "total_criteria": 10,
    "status_counts": { "cumprido": 4, "nao_cumprido": 6, "nao_aplicavel": 0 },
    "items_for_review": ["syntax_1", "syntax_4"],
    "total_applied_penalty": 1.20,
    "iterations_ran": 3,
    "final_avg_confidence": 0.37,
    "stop_reason": "max_iterations"
  },
  "assessments": [
    {
      "criterion_id": "syntax_1",
      "category": "syntax",
      "category_weight": 0.30,
      "status": "nao_cumprido",
      "checklist_penalty": 0.20,
      "applied_penalty": 0.20,
      "justification": "Agent 1 flagged NAO_CUMPRIDO without observation data...",
      "confidence": 0.20,
      "flag_review": true,
      "plan_log": "..."
    }
  ]
}
```

**`applied_penalty` rules (deterministic — never set by LLM):**

| Status | `applied_penalty` |
|---|---|
| `cumprido` | `0.0` |
| `nao_aplicavel` | `0.0` |
| `nao_cumprido` | `= checklist_penalty` |

Items with `confidence < CONFIDENCE_THRESHOLD` get `flag_review=True` and appear in `items_for_review`. `plan_log` is set only on the first item.

---

## Reflection loop — stopping criteria

The loop stops on the **first** condition that fires:

| Condition | `stop_reason` |
|---|---|
| `avg_confidence >= CONFIDENCE_THRESHOLD` | `threshold_reached` |
| No weak items remain | `no_weak_items` |
| `iteration >= MAX_ITERATIONS` | `max_iterations` |
| Confidence unchanged vs previous iteration | `stagnant` |

---

## Environment variables

Loaded from `.env` via `python-dotenv`:

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `MODEL_NAME` | `claude-opus-4-7` | Model used for all LLM calls |
| `CONFIDENCE_THRESHOLD` | `0.6` | Below this → `flag_review=True` |
| `MAX_ITERATIONS` | `3` | Hard cap on reflection loop |

---

## How to run

**Full pipeline (load → plan → loop → serialize):**

```python
from agents.agent2_evaluator.evaluator import Agent2Evaluator
from agents.agent2_evaluator.loaders import load_evidence

evidence = load_evidence("evaluation/results/BPMNEvidence.json")

evaluator = Agent2Evaluator()
assessments = evaluator.run(
    evidence,
    checklist_path="evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv",
    output_path="evaluation/results/BPMNAssessment.json",
)

# Iteration log available after run
print(evaluator.iteration_log)
```

**Quick test against the 10-item mock:**

```bash
python3 -m agents.agent2_evaluator
```

**Run tests (no API calls):**

```bash
pytest agents/agent2_evaluator/test_evaluator.py -v
```

---

## File layout

```
agent2_evaluator/
├── __init__.py            # exports Agent2Evaluator
├── __main__.py            # end-to-end smoke test (mock or real evidence)
├── evaluator.py           # evaluate_once, _reflect_loop, build_output, Agent2Evaluator
├── planning.py            # generate_analysis_plan — Planning pattern
├── loaders.py             # load_evidence, load_checklist
├── test_evaluator.py      # 39 pytest tests, all mocked
└── mocks/
    ├── mock_bpmn_evidence.json    # 10-item input fixture
    └── mock_bpmn_assessment.json  # canonical output structure reference
```

---

## Contract

Defined in `agents/contracts.py`. Do not change without team alignment.

```python
@dataclass
class BPMNAssessment:
    criterion_id: str
    category: str
    category_weight: float      # from checklist CSV
    status: str                 # cumprido | nao_cumprido | nao_aplicavel
    checklist_penalty: float    # copied from BPMNEvidence.value
    applied_penalty: float      # 0.0 or checklist_penalty, based on status
    justification: str          # LLM reasoning
    confidence: float           # 0.0–1.0, conservative
    flag_review: bool           # True if confidence < CONFIDENCE_THRESHOLD
    plan_log: str | None        # analysis plan, first item only
```
