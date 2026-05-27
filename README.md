# BPMN Hybrid Evaluator

Prototype pipeline for the master's research proposal *"Application of Hybrid Human-AI Methodologies for BPMN Modeling Assessment and Formative Feedback"* — CIn-UFPE.

Three AI agents (Mapper → Evaluator → Feedback Generator) process a BPMN diagram JSON, apply the course checklist, and produce a scored evaluation with formative feedback. A human review step sits between Agent 2 and Agent 3.

---

## Prerequisites

- Python 3.11 or higher
- An [Anthropic API key](https://console.anthropic.com)
- Or a [Google AI API key](https://aistudio.google.com/) Obs: set as GEMINI_API_KEY
- Git

---

## Local installation

### 1. Clone the repository

```bash
git clone https://github.com/Jailsonsdsj/bpmn-evaluator.git
cd bpmn-evaluator
```

### 2. Create and activate a virtual environment

```bash
python3.11 -m venv .venv
```

**macOS / Linux**
```bash
source .venv/bin/activate
```

**Windows**
```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your Anthropic API key:

```
ANTHROPIC_API_KEY=sk-ant-...
MODEL_NAME=claude-sonnet-4-6
```

Or Google AI API key:

```
GEMINI_API_KEY=...
MODEL_NAME=gemma-4-31b-it
```

The other variables have working defaults and do not need to be changed for a first run:

| Variable | Default | What it controls |
|---|---|---|
| `MODEL_NAME` | `claude-sonnet-4-6` | Claude/Google AI model used by all agents |
| `MAX_ITERATIONS` | `3` | Max Reflection loop iterations for Agent 2 |
| `CONFIDENCE_THRESHOLD` | `0.6` | Minimum confidence before Agent 2 stops iterating |

> **Never commit `.env`** — it is already in `.gitignore`.

---

## Running the pipeline

```bash
python main.py \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --enunciado evaluation/dataset/Instruções.txt \
  --output evaluation/results/
```

The pipeline will pause at the Human Review step and prompt you to edit `assessment_review.json` before continuing.

---

## Running with Docker

```bash
docker compose -f docker/docker-compose.yml run --rm pipeline
```

The pipeline container runs the command after `#All` in `run_all.sh`.
Update that line with the diagram/checklist/enunciado/assessment paths you want to run.

When you click **Run** on the image in Docker Desktop, it also executes the same `#All` command from `run_all.sh`.

**Required files (must exist inside the repo):**

- Diagram: e.g. `evaluation/dataset/diagram_001.json`
- Checklist: e.g. `evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv`
- Enunciado: e.g. `evaluation/dataset/Instruções.txt`

If any path in the `#All` command points to a missing file, the pipeline will fail with `FileNotFoundError`.

Run Agent 1 only:

```bash
docker compose -f docker/docker-compose.yml run --rm app -m agents.agent1_analyst \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist evaluation/dataset/checklist.json \
  --output evaluation/results
```

Run Agent 2 (uses the default paths inside `__main__.py`):

```bash
docker compose -f docker/docker-compose.yml run --rm app -m agents.agent2_evaluator
```

Run Agent 3 (requires enunciado + assessment):

```bash
docker compose -f docker/docker-compose.yml run --rm app -m agents.agent3_feedback \
  --diagram evaluation/dataset/diagram_001.json \
  --enunciado evaluation/dataset/Instruções.txt \
  --assessment evaluation/results/BPMNAssessment.json \
  --output evaluation/results
```

---

## Running tests

```bash
pytest agents/ -v
```

---

## Branching model

| Branch | Purpose |
|---|---|
| `main` | Stable — PR + 1 approval required |
| `develop` | Integration — PR + 1 approval required |
| `feat/agent-1` | Member A — Criteria Mapper |
| `feat/agent-2` | Member B — Critic Evaluator |
| `feat/agent-3` | Member C — Feedback Generator |

Merge flow: `feat/*` → `develop` → `main`. Never push directly to `main` or `develop`.

Commit format: `type(scope): message` — e.g. `feat(agent1): implement evidence mapper`.

---

## Project structure

```
bpmn-evaluator/
├── agents/
│   ├── agent1_analyst/     # Criteria Mapper
│   ├── agent2_evaluator/   # Critic Evaluator (Reflection loop)
│   ├── agent3_feedback/    # Formative Feedback Generator
│   └── contracts.py        # BPMNEvidence and BPMNAssessment dataclasses
├── evaluation/
│   ├── dataset/            # Input diagrams + ground truth (do not modify)
│   └── results/            # Per-run output files
├── docker/                 # Dockerfile and docker-compose.yml
├── paper/                  # Article in progress
├── main.py                 # Pipeline orchestrator
├── requirements.txt
├── pyproject.toml
└── .env.example
```

See [CLAUDE.md](CLAUDE.md) for full architecture, agent contracts, and contribution guidelines.
