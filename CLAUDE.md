# Hybrid Evaluation of BPMN Models with AI Agents

> Base prototype for the master's research proposal: *"Application of Hybrid Human-AI Methodologies for BPMN Modeling Assessment and Formative Feedback"*

---

## Problem context

The Business Process Management (BPM) course at CIn-UFPE produced ~223 manual evaluations of BPMN diagrams between 2022.2 and 2024.2. This volume creates two problems documented empirically:

1. **Inter-evaluator variability** — professors and monitors with different levels of experience produce inconsistencies in penalties.
2. **Checklist inflation** — the assessment instrument grows without hierarchization, diluting the weight of critical errors.

This project implements a pipeline of three agents that receives a BPMN diagram as structured JSON, applies the course's checklist, and produces evaluation + formative feedback, with a tracked human review step between the agents.

---

## Repository structure

```
bpmn-hybrid-eval/
├── agents/
│   ├── agent1_analyst/       # Criteria mapper (Member A)
│   ├── agent2_evaluator/     # Critic evaluator with Reflection (Member B)
│   ├── agent3_feedback/      # Formative feedback generator (Member C)
│   └── contracts.py          # BPMNEvidence and BPMNAssessment dataclasses
├── evaluation/
│   ├── dataset/              # 5 JSON diagrams + anonymized ground truth
│   └── results/              # Per-run JSON results
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
Diagram JSON + checklist + task statement
        │
        ▼
[ Agent 1 — Mapper ]         Prompt Chaining · Tool Use
        │ BPMNEvidence
        ▼
[ Agent 2 — Evaluator ]      Reflection (Producer-Critic) · Planning
        │ BPMNAssessment
        ▼
[ Human Review ]             Human-in-the-Loop (editable file)
        │ validated assessment
        ▼
[ Agent 3 — Feedback ]       Multi-Agent · Goal Setting & Monitoring
        │
        ▼
Final report (score · feedback per error · suggestions · review log)
```

---

## Inter-agent contracts — DO NOT change without team alignment

```python
# agents/contracts.py

@dataclass
class BPMNEvidence:
    criterion_id: str
    category: str               # syntax | semantics | best_practices | proposal
    status: str                 # present | absent | incorrect
    element: str                # name/id of the element in the diagram
    observation: str | None     # description of the problem (for status=incorrect)

@dataclass
class BPMNAssessment:
    criterion_id: str
    category: str
    penalty: float              # checklist value (0.0 if no penalty)
    justification: str
    confidence: float           # 0.0–1.0 (never inflate)
    flag_review: bool           # True if confidence < CONFIDENCE_THRESHOLD
    plan_log: str | None        # Agent 2's plan (only on the first item)
```

Serialization: `dataclasses.asdict()` → `json.dumps()`. Reading: `json.loads()` → instantiate manually.

---

## Agent 1 — Criteria Mapper

**Owner:** Member A | **Branch:** `feat/agent-1`

**Responsibility:** receive the diagram JSON and the checklist; for each criterion, check whether the corresponding element is present, absent, or incorrect. **Does not emit judgment** — only maps evidence.

**Patterns:** Prompt Chaining (3 chained steps), Tool Use (JSON file reading).

**Prompt Chaining steps:**
1. Load and structure the diagram JSON
2. Load the checklist by category
3. Map each criterion → element found (or not)

**Critical rule:** Agent 1 may only reference elements present in the input JSON. Zero hallucinations of nonexistent elements.

**Output:** list of `BPMNEvidence` serialized as JSON.

---

## Agent 2 — Critic Evaluator

**Owner:** Member B | **Branch:** `feat/agent-2`

**Responsibility:** receive `BPMNEvidence` and apply the checklist's penalty criteria, with justification and confidence score per item. Refine its own output via a Reflection loop.

**Patterns:** Planning (per-category plan before evaluating), Reflection Producer-Critic (self-critique loop).

**Internal flow:**
1. Generate an analysis plan: syntax → semantics → best practices → proposal
2. For each item with `status != present`: apply penalty + justification + confidence
3. Review its own output: "is the penalty justified by the evidence?"
4. Refine items with insufficient justification
5. Repeat until stopping criterion is met

**Loop stopping criterion:**
- `average_confidence >= CONFIDENCE_THRESHOLD` **OR**
- `iteration >= MAX_ITERATIONS` (default: 3) **OR**
- confidence stagnant between iteration N and N-1

**Critical rule:** Agent 2 may only penalize items present in the received `BPMNEvidence`. Items with `confidence < CONFIDENCE_THRESHOLD` get `flag_review=True`.

**Output:** list of `BPMNAssessment` + partial score per category + iteration log.

---

## Human Review (Human-in-the-Loop)

Between Agent 2 and Agent 3. Simplified implementation via editable file.

**Flow:**
1. Agent 2 generates `assessment_review.json` with clearly marked editable fields
2. Pipeline pauses and waits for confirmation (terminal input)
3. Human evaluator edits `penalty` and/or `justification` of items they disagree with
4. Pipeline re-reads the file and computes diff (original vs edited)
5. Diff saved to `evaluation/results/human_interventions_<timestamp>.json`
6. Validated file is passed to Agent 3

**The diff is primary research data** — it records when, how, and why the human diverges from the model.

---

## Agent 3 — Formative Feedback Generator

**Owner:** Member C | **Branch:** `feat/agent-3`

**Responsibility:** receive the validated `BPMNAssessment` and generate personalized formative feedback for the student.

**Patterns:** Multi-Agent Collaboration (integrates artifacts from A1 and A2), Goal Setting & Monitoring (verifies coverage before emitting).

**For each penalized item, the feedback must contain:**
1. Explanation of the error in accessible language (second person, no unnecessary jargon)
2. Reference to the specific element (name + type)
3. Concrete, actionable correction suggestion

**Goal Monitoring (in Python, no additional LLM call):**
- Verify that every item with `penalty > 0` has a corresponding feedback block
- Items without coverage trigger a second targeted call

**Output:** report with score per category, feedback per error, summary of strengths, log of human interventions.

---

## MVC scope — Delivery 1 restrictions

- **Single-pool** diagrams, no subprocesses, no complex intermediate events
- **Syntax category** implemented and validated before expanding to others
- Input via **manually filled JSON** (no automatic XML conversion)
- Human review via **editable file** (no GUI)
- Output in **Markdown or structured JSON** (no formatted report)

Delivery 2 scales to all 4 categories of the checklist.

---

## Input JSON schema (simplified BPMN diagram)

```json
{
  "id": "diagram_001",
  "name": "Purchase Process",
  "elements": [
    {
      "id": "e1",
      "type": "startEvent",
      "name": "Start",
      "outgoing": ["f1"]
    },
    {
      "id": "t1",
      "type": "task",
      "name": "Request quote",
      "incoming": ["f1"],
      "outgoing": ["f2"]
    },
    {
      "id": "g1",
      "type": "exclusiveGateway",
      "name": "Quote approved?",
      "incoming": ["f2"],
      "outgoing": ["f3", "f4"]
    },
    {
      "id": "e2",
      "type": "endEvent",
      "name": "End",
      "incoming": ["f3"]
    }
  ],
  "flows": [
    {"id": "f1", "source": "e1", "target": "t1"},
    {"id": "f2", "source": "t1", "target": "g1"},
    {"id": "f3", "source": "g1", "target": "e2", "name": "Yes"},
    {"id": "f4", "source": "g1", "target": "t1", "name": "No"}
  ]
}
```

Valid element types: `startEvent`, `endEvent`, `task`, `userTask`, `serviceTask`, `exclusiveGateway`, `parallelGateway`, `inclusiveGateway`, `sequenceFlow`, `pool`, `lane`, `subProcess` (collapsed).

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
python main.py --diagram evaluation/dataset/diagram_001.json \
               --checklist evaluation/dataset/checklist.json \
               --output evaluation/results/

# Run with Docker (recommended)
docker compose up
docker compose run pipeline python main.py \
  --diagram /data/diagram_001.json \
  --checklist /data/checklist.json \
  --output /output/

# Run tests
pytest agents/ -v
```

---

## Gitflow

- `main` — protected, PR required + 1 approval
- `develop` — protected, PR required + 1 approval
- `feat/agent-1` — Member A
- `feat/agent-2` — Member B
- `feat/agent-3` — Member C

**Merge flow:** `feat/*` → `develop` → `main`  
**Never** push directly to `main` or `develop`.

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

---

## Evaluation dataset

5 BPMN diagrams from the historical corpus of the BPM course (2022.2–2024.2), anonymized:

| ID | Complexity | Flow elements | Ground truth |
|----|-----------|---------------|--------------|
| diagram_001 | Simple | ≤ 5 | Original human evaluation |
| diagram_002 | Simple | ≤ 5 | Original human evaluation |
| diagram_003 | Medium | 6–15 | Original human evaluation |
| diagram_004 | Medium | 6–15 | Original human evaluation |
| diagram_005 | Complex | > 15 | Original human evaluation |

**Rule:** never modify files in `evaluation/dataset/`. Never add personally identifiable data.

---

## Evaluation metrics collected per run

| Metric | Where to save | Who collects |
|--------|---------------|--------------|
| Execution time per agent | results_vN.json | main.py |
| Number of A2 loop iterations | results_vN.json | Agent 2 |
| Final A2 average confidence | results_vN.json | Agent 2 |
| Accuracy vs ground truth | fp_fn_analysis.md | Manual (all) |
| FP and FN rate per category | fp_fn_analysis.md | Manual (all) |
| Feedback quality score | feedback_rubric.md | Manual (Member C) |
| Number of human interventions | human_interventions_*.json | Human review |

---

## Active risks

| Risk | Mitigation |
|------|-----------|
| Agent 2 penalizes items without basis in evidence | A2 may only reference items in `BPMNEvidence`; confidence < threshold forces human review |
| Reflection loop does not converge | `MAX_ITERATIONS=3` + stagnation detection — terminates with uncertainty flag |
| Loop artificially inflates confidence | A2 system prompt explicitly instructs conservative scoring; calibrate with thresholds 0.5/0.6/0.7 in issue #19 |
| Dataset unavailable in time | Contact the BPM course professor immediately; Member A is responsible for curation |
| JSON does not cover relevant checklist element | Schema validated against 2 real diagrams before any coding starts (issue #4) |

