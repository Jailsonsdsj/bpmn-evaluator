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

Docker runs the exact same pipeline as [Running the pipeline](#running-the-pipeline) — the container's entrypoint *is* `python main.py` (Agent 1 → 2 → 3) — so you don't need a local Python install. Any flags you pass are forwarded straight to `main.py`.

First create your `.env` (see [Configure environment variables](#4-configure-environment-variables)); the container reads your API key from it.

```bash
docker compose -f docker/docker-compose.yml run --rm pipeline \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --enunciado evaluation/dataset/Instruções.txt \
  --output evaluation/results/
```

The flags are identical to the local run (omit them to use `main.py`'s default dataset paths). The `evaluation/` directory is mounted into the container, so input files are read from your working copy and results are written back to `evaluation/results/` on the host.

As with the local run, the pipeline will pause at the Human Review step and prompt you to edit `BPMNAssessment.json` before continuing. The `pipeline` service runs with an interactive terminal so this prompt works inside Docker.

### Running a single agent

Each agent also has its own compose service (`agent1`, `agent2`, `agent3`) for running the stages one at a time. Flags after the service name are forwarded to that agent:

```bash
# Agent 1 — writes evaluation/results/BPMNEvidence.json
docker compose -f docker/docker-compose.yml run --rm agent1 \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --output evaluation/results/BPMNEvidence.json

# Agent 2 — reads evidence, writes evaluation/results/BPMNAssessment.json
docker compose -f docker/docker-compose.yml run --rm agent2 \
  --evidence evaluation/results/BPMNEvidence.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --output evaluation/results/BPMNAssessment.json

# Agent 3 — reads assessment, writes evaluation/results/BPMNFeedback.json
docker compose -f docker/docker-compose.yml run --rm agent3 \
  --diagram evaluation/dataset/diagram_001.json \
  --enunciado evaluation/dataset/Instruções.txt \
  --assessment evaluation/results/BPMNAssessment.json \
  --output evaluation/results/BPMNFeedback.json
```

See [docker/README.md](docker/README.md) for more detail.

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
