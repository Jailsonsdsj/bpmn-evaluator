# Hybrid Evaluation of BPMN Models with AI Agents

> Undergraduate Project — CIn/UFPE
> Base prototype for the master's research proposal: *"Application of Hybrid Human-AI Methodologies for BPMN Modeling Assessment and Formative Feedback"*

---

## Problem context

The Business Process Management (BPM) course at CIn-UFPE produced ~223 manual evaluations of BPMN diagrams between 2022.2 and 2024.2. This volume creates two problems documented empirically:

1. **Inter-evaluator variability** — professors and monitors with different levels of experience produce inconsistencies in penalties.
2. **Checklist inflation** — the assessment instrument grows without hierarchization, diluting the weight of critical errors.

This project implements a pipeline of three agents that receives a BPMN diagram as structured JSON, applies the course's scored checklist, and produces evaluation + formative feedback, with a tracked human review step between the agents.

---

## Key design principle — the checklist is the source of truth for scoring

The course checklist (provided as a CSV) is **not just a list of criteria — it is a complete scoring instrument**. Each row already carries:

- The **category** with its global weight (syntax 30%, proposal 20%, semantics 20%, best practices 20%, readability 10%)
- The **evaluated item** as a question
- The **pre-written feedback** — the exact sentence describing the error when the criterion fails
- The **penalty** — the points lost if the criterion is not met

**Consequence for the architecture:** the LLM does NOT decide how many points to deduct. Penalties come from the checklist table. This makes the scoring **deterministic and auditable** — two students with the same error always lose the same points. The LLM is used where it is strong (perceiving the diagram, validating findings, personalizing text) and kept out of where it is risky (assigning grades).

---

## Repository structure

```
bpmn-hybrid-eval/
├── agents/
│   ├── agent1_analyst/       # Criteria mapper (Member A)
│   ├── agent2_evaluator/     # Critic validator (Member B)
│   ├── agent3_feedback/      # Feedback generator + grade calculator (Member C)
│   └── contracts.py          # BPMNEvidence and BPMNAssessment dataclasses
├── evaluation/
│   ├── dataset/              # 5 JSON diagrams + checklist CSV + ground truth
│   └── results/              # Per-run JSON results
├── mocks/                    # Mock evidence/assessment for parallel development
├── docker/                   # Dockerfile + docker-compose
├── paper/                    # Article in progress
├── main.py                   # Full pipeline orchestrator
├── requirements.txt
├── .env.example
└── CLAUDE.md                 # this file
```

---

## Pipeline

```
Diagram JSON + checklist CSV + task statement
        │
        ▼
[ Agent 1 — Mapper ]         Prompt Chaining · Tool Use
        │ BPMNEvidence
        ▼
[ Agent 2 — Validator ]      Reflection (Producer-Critic) · Planning
        │ BPMNAssessment
        ▼
[ Human Review ]             Human-in-the-Loop (editable file)
        │ validated assessment
        ▼
[ Agent 3 — Feedback ]       Multi-Agent · Goal Setting & Monitoring
        │  (also receives the checklist CSV)
        ▼
Final report (weighted grade · personalized feedback per error · review log)
```

---

## Checklist input format (CSV)

The checklist CSV is an input to the pipeline, consumed by Agent 1 and Agent 3. Columns:

| Column | Description |
|--------|-------------|
| Categoria | Category name + global weight (e.g. "sintaxe 30%") |
| Itens avaliados | The criterion phrased as a question |
| Feedback | Pre-written sentence describing the error when the criterion fails |
| Pontuação geral | Penalty value lost if the criterion is not met |

Categories and weights: syntax 30%, proposal 20%, semantics 20%, best practices 20%, readability 10%. Total = 10.

Individual penalties vary (0.1 to 0.8). The heaviest single item is "expected gateways not modeled" (0.8). Penalties are NOT uniform — the system does not treat all errors equally.

---

## Inter-agent contracts — DO NOT change without team alignment

```python
# agents/contracts.py

@dataclass
class BPMNEvidence:
    criterion_id: str
    category: str               # syntax | proposal | semantics | best_practices | readability
    status: str                 # cumprido | nao_cumprido | nao_aplicavel
    value: float                # checklist penalty score to deduct if not met
    element: str | None         # name/id of the element in the diagram
    observation: str | None     # description of the problem (for nao_cumprido)
    question: str               # the criterion text from the checklist

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
    plan_log: str | None        # Agent 2's analysis plan (only on the first item)
```

Serialization: `dataclasses.asdict()` → `json.dumps()`. Reading: `json.loads()` → instantiate manually.

**Notes on the contract:**
- `value` in `BPMNEvidence` carries the checklist penalty; Agent 2 copies it into `checklist_penalty`. The `status` field already encodes met/not-met, so a separate fractional value was redundant.
- `nao_aplicavel` items always have `applied_penalty=0.0` — a criterion out of scope must NOT subtract points from the student.
- `checklist_penalty` is COPIED from the checklist CSV (via `BPMNEvidence.value`), never decided by the LLM.
- The pre-written feedback sentence does NOT travel in `BPMNEvidence`. Agent 3 looks it up in the checklist CSV using `criterion_id`.

---

## Agent 1 — Criteria Mapper

**Owner:** Member A | **Branch:** `feat/agent-1`

**Responsibility:** receive the diagram JSON and the checklist CSV; for each criterion, check whether it is met in the diagram. **Does not emit judgment or scoring** — only reports findings.

**Patterns:** Prompt Chaining (3 chained steps), Tool Use (JSON + CSV file reading).

**Prompt Chaining steps:**
1. Load and structure the diagram JSON
2. Load the checklist CSV by category
3. Map each criterion → status (`cumprido` / `nao_cumprido` / `nao_aplicavel`)

**Critical rule:** Agent 1 may only reference elements present in the input JSON. Zero hallucinations of nonexistent elements. Criteria that the diagram's characteristics do not reach get `nao_aplicavel` (e.g. message-flow criteria in a single-pool diagram).

**Output:** list of `BPMNEvidence` serialized as JSON.

---

## Agent 2 — Critic Validator

**Owner:** Member B | **Branch:** `feat/agent-2`

**Responsibility (REDUCED scope):** receive `BPMNEvidence` and produce `BPMNAssessment`. The agent does **NOT invent penalties** — it copies `checklist_penalty` from the checklist. Its real job is:

1. **Validate** whether Agent 1's finding is correct ("did A1 correctly judge this criterion as not met?")
2. **Resolve `nao_aplicavel` cases** correctly — confirm a criterion is genuinely out of scope
3. **Assign a confidence score** (0.0–1.0) per item
4. Copy `checklist_penalty` and set `applied_penalty` (0.0 for cumprido/nao_aplicavel, equal to penalty for nao_cumprido)

**Patterns:** Planning (per-category analysis plan before validating), Reflection Producer-Critic (self-critique loop).

**The Reflection loop now validates JUDGMENT, not scoring.** It asks "is Agent 1's finding well supported by the evidence?" — not "how many points should this cost?"

**Loop stopping criterion (any one):**
- `average_confidence >= CONFIDENCE_THRESHOLD` (default 0.6)
- `iteration >= MAX_ITERATIONS` (default 3)
- confidence stagnant between iteration N and N-1

**Critical rule:** Agent 2 may only assess criteria present in the received `BPMNEvidence`. Items with `confidence < CONFIDENCE_THRESHOLD` get `flag_review=True`.

**Output:** list of `BPMNAssessment` + iteration log.

---

## Human Review (Human-in-the-Loop)

Between Agent 2 and Agent 3. Simplified implementation via editable file.

**Flow:**
1. Agent 2 generates `assessment_review.json` with clearly marked editable fields
2. Pipeline pauses and waits for confirmation (terminal input)
3. Human evaluator edits `status` and/or `applied_penalty` and/or `justification` of items they disagree with — focusing on `flag_review=True` items
4. Pipeline re-reads the file and computes diff (original vs edited)
5. Diff saved to `evaluation/results/human_interventions_<timestamp>.json`
6. Validated file is passed to Agent 3

**The diff is primary research data** — it records when, how, and why the human diverges from the model.

---

## Agent 3 — Feedback Generator and Grade Calculator

**Owner:** Member C | **Branch:** `feat/agent-3`

**Responsibility:** receive the validated `BPMNAssessment` AND the checklist CSV. Two jobs:

**Job 1 — Calculate the final grade.** Deterministic, in Python (no LLM):
- Start from the full grade (10)
- Subtract `applied_penalty` of every `nao_cumprido` item
- Apply category weights for the per-category breakdown
- `nao_aplicavel` items never subtract points

**Job 2 — Generate personalized formative feedback.** For each penalized item:
- Look up the pre-written feedback sentence in the checklist CSV via `criterion_id`
- Personalize it: contextualize in the student's specific diagram (which element, which point of the flow)
- Add a concrete, actionable correction suggestion (the checklist does not provide this)

**Patterns:** Multi-Agent Collaboration (integrates artifacts from A1 and A2), Goal Setting & Monitoring (verifies every penalized item has feedback before emitting).

**Goal Monitoring (in Python, no extra LLM call):** verify that every item with `applied_penalty > 0` has a corresponding feedback block. Items without coverage trigger a second targeted call.

**Output:** report with weighted grade, per-category breakdown, personalized feedback per error, summary of strengths, log of human interventions.

---

## MVC scope — Delivery 1 restrictions

- **Single-pool** diagrams, no subprocesses, no complex intermediate events
- **Syntax category** implemented and validated before expanding to others
- Input via **manually filled JSON** (no automatic XML conversion)
- Human review via **editable file** (no GUI)
- Output in **Markdown or structured JSON** (no formatted report)

Delivery 2 scales to all 5 categories of the checklist.

---

## Input JSON schema (simplified BPMN diagram)

```json
{
  "id": "diagram_001",
  "name": "Purchase Process",
  "elements": [
    { "id": "e1", "type": "startEvent", "name": "Start", "outgoing": ["f1"] },
    { "id": "t1", "type": "task", "name": "Request quote", "incoming": ["f1"], "outgoing": ["f2"] },
    { "id": "g1", "type": "exclusiveGateway", "name": "Quote approved?", "incoming": ["f2"], "outgoing": ["f3", "f4"] },
    { "id": "e2", "type": "endEvent", "name": "End", "incoming": ["f3"] }
  ],
  "flows": [
    { "id": "f1", "source": "e1", "target": "t1" },
    { "id": "f2", "source": "t1", "target": "g1" },
    { "id": "f3", "source": "g1", "target": "e2", "name": "Yes" },
    { "id": "f4", "source": "g1", "target": "t1", "name": "No" }
  ]
}
```

Valid element types: `startEvent`, `endEvent`, `task`, `userTask`, `serviceTask`, `exclusiveGateway`, `parallelGateway`, `inclusiveGateway`, `sequenceFlow`, `pool`, `lane`, `subProcess` (collapsed).

---

## Mocks for parallel development

`mocks/` contains `mock_bpmn_evidence.json` and `mock_bpmn_assessment.json` so Agents 2 and 3 can be developed without waiting for upstream agents. See `mocks/README.md`. Mock field names match the contracts above. The format must stay identical to the contracts — any schema change requires team alignment.

---

## Environment and variables

```bash
# .env.example
ANTHROPIC_API_KEY=your_api_key_here
MODEL_NAME=claude-sonnet-4-20250514
MAX_ITERATIONS=3
CONFIDENCE_THRESHOLD=0.6
```

Never hardcode the API key. Always load via `python-dotenv`.

---

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run pipeline on a diagram
python main.py --diagram "evaluation/dataset/Diagrama.json" \
               --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
               --output evaluation/results/

# Run with Docker (recommended)
docker compose up
docker compose run pipeline python main.py \
  --diagram "/data/Diagrama.json" \
  --checklist "/data/Checklist completo - Modelagem 1 - Básico.csv" \
  --output /output/

# Run tests
pytest agents/ -v
```

---

## Gitflow

- `main` — main branch
- `develop` — integration branch
- `feat/agent-1` — Member A
- `feat/agent-2` — Member B
- `feat/agent-3` — Member C

**Merge flow:** `feat/*` → `develop` → `main`. Merges go through PR with review by one colleague.

**Commit format:** `type(scope): message`
Types: `feat`, `fix`, `refactor`, `test`, `chore`, `docs`
Scopes: `agent1`, `agent2`, `agent3`, `pipeline`, `eval`, `docker`, `paper`

---

## Code conventions

- Python 3.11+
- Type hints on all function signatures
- Dataclasses for all inter-agent contracts
- Each agent is a class with a `.run(input) -> output` method
- Structured logging with `structlog` at `INFO` level at each step
- Agents do not import each other directly — communicate only via dataclasses
- All file I/O uses paths from `.env`, never hardcoded
- Grade calculation is deterministic Python — never delegated to the LLM

---

## Evaluation dataset

BPMN diagrams from the historical corpus of the BPM course (2022.2–2024.2), anonymized.
Currently 2 diagrams are in the repository; more will be added as curation progresses.

| File | Complexity | Source format | Ground truth |
|----|-----------|---------------|--------------|
| Diagrama.json | Medium | LucidChart export (normalized by Agent 1) | Original human evaluation |
| Diagrama2.json | Medium | LucidChart export (normalized by Agent 1) | Original human evaluation |

**Rule:** never modify files in `evaluation/dataset/`. Never add personally identifiable data.

---

## Evaluation metrics collected per run

| Metric | Where to save | Who collects |
|--------|---------------|--------------|
| Execution time per agent | results_vN.json | main.py |
| Number of A2 loop iterations | results_vN.json | Agent 2 |
| Final A2 average confidence | results_vN.json | Agent 2 |
| Final grade vs ground truth grade | fp_fn_analysis.md | Manual (all) |
| FP and FN rate per category | fp_fn_analysis.md | Manual (all) |
| Feedback quality score | feedback_rubric.md | Manual (Member C) |
| Number of human interventions | human_interventions_*.json | Human review |

---

## Issue schedule

| Delivery | Date | Issues |
|----------|------|--------|
| **Delivery 1** | May 26 | #1 – #18 |
| **Delivery 2** | Jun 16 | #19 – #27 |
| **Delivery 3** | Jun 18 | no new issues (uses #15 + #27) |
| **Delivery 4** | Jun 25 | no new issues (refinement of #27) |

**Internal checkpoints:** May 07 (#1–#6) · May 12 (#7–#10, #12) · May 14 (#11, #13) · May 19 (#14–#16) · May 21 (#17) · May 26 Delivery 1 (#18) · May 28 (#19–#20) · Jun 02 (#21–#22) · Jun 09 (#23–#24) · Jun 11 (#25–#26) · Jun 16 Delivery 2 (#27).

---

## Active risks

| Risk | Mitigation |
|------|-----------|
| Agent 2 assesses criteria without basis in evidence | A2 may only reference items in `BPMNEvidence`; confidence < threshold forces human review |
| Reflection loop does not converge | `MAX_ITERATIONS=3` + stagnation detection — terminates with uncertainty flag |
| Loop artificially inflates confidence | A2 system prompt explicitly instructs conservative scoring; calibrate thresholds 0.5/0.6/0.7 in issue #19 |
| Wrong handling of `nao_aplicavel` inflates or deflates the grade | `nao_aplicavel` items always have `applied_penalty=0.0`; never subtract points |
| Dataset unavailable in time | Contact the BPM course professor immediately; Member A responsible for curation |
| Checklist CSV format changes between semesters | Pin the checklist version used; document it explicitly in `evaluation/dataset/` |

---

## Agentic patterns applied (reference to the book)

| Pattern | Agent | Chapter |
|---------|-------|---------|
| Prompt Chaining | Agent 1 | 3 |
| Tool Use | Agent 1 | 5 |
| Planning | Agent 2 | 6 |
| Reflection (Producer-Critic) | Agent 2 | 4 |
| Human-in-the-Loop | Review between A2 and A3 | 8 |
| Goal Setting & Monitoring | Agent 3 | 11 |
| Multi-Agent Collaboration | Orchestrator (main.py) | 7 |

Source: *Agentic Design Patterns* (2024) — copy in `paper/references/`.

---

## Link to the master's research

This project implements **stage 3** of the master's proposal (development of the hybrid system). The data collected here — especially the human intervention log and the FP/FN analysis — is the initial corpus for stages 2 and 4 (LLM calibration and empirical evaluation). The master's work continues with: real XML parser, corpus of 223 evaluations, multiple evaluators, and formal concordance metrics (Cohen's kappa).