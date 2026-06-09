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

Open `.env` and choose your provider with `LLM_PROVIDER`, set the matching model id, and fill in the API key for that provider.

Anthropic (default):

```
LLM_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6
ANTHROPIC_API_KEY=sk-ant-...
```

Google AI (Gemini):

```
LLM_PROVIDER=google_genai
MODEL_NAME=gemma-4-31b-it
GEMINI_API_KEY=...
```

OpenAI:

```
LLM_PROVIDER=openai
MODEL_NAME=gpt-4o
OPENAI_API_KEY=...
```

`LLM_PROVIDER` selects the LLM framework for all agents through a single shared factory (`agents/shared_tools/llm.py`), built on LangChain's `init_chat_model`. Any provider it supports works once you install that provider's package — `anthropic` and `google_genai` are installed by default; for others uncomment the matching line in `requirements.txt` (e.g. `langchain-openai`). The built-in shortcuts are `anthropic`, `google_genai`, `openai`, `groq`, `mistralai`, and `ollama`.

> If `LLM_PROVIDER` is unset, the factory falls back to inferring the provider from whichever API key is present (backward compatibility).

The other variables have working defaults and do not need to be changed for a first run:

| Variable | Default | What it controls |
|---|---|---|
| `LLM_PROVIDER` | `anthropic` | Which LLM provider all agents use |
| `MODEL_NAME` | `claude-sonnet-4-6` | Model id for the selected provider |
| `MAX_ITERATIONS` | `3` | Max Reflection loop iterations for Agent 2 |
| `CONFIDENCE_THRESHOLD` | `0.6` | Minimum confidence before Agent 2 stops iterating |

> **Never commit `.env`** — it is already in `.gitignore`.

### Local models

You can run entirely on local/self-hosted models — no API key, no network. Two routes:

**Ollama** (simplest). Install [Ollama](https://ollama.com), pull a model, install the integration, then point `.env` at it:

```bash
ollama pull llama3.1
pip install langchain-ollama
```

```
LLM_PROVIDER=ollama
MODEL_NAME=llama3.1
```

Local Ollama on its default `http://localhost:11434` needs nothing more. If Ollama runs on another host — or you run the pipeline **in Docker** (where `localhost` is the container, not your machine) — also set the endpoint:

```
LLM_BASE_URL=http://host.docker.internal:11434
```

**OpenAI-compatible server** (LM Studio, llama.cpp `server`, vLLM, text-generation-webui). These expose an OpenAI-style API, so use the `openai` provider pointed at the local URL:

```
LLM_PROVIDER=openai
MODEL_NAME=<model id the server exposes>
LLM_BASE_URL=http://localhost:1234/v1
OPENAI_API_KEY=not-needed
```

> `OPENAI_API_KEY` must be a non-empty string — the OpenAI client requires one — but the local server ignores its value.

`LLM_BASE_URL` is forwarded to the provider as `base_url`; it is optional and only needed to override the default endpoint.

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

### Rebuilding the image

Dependencies and agent code are baked into the image, so rebuild after changes to `requirements.txt`, the agents, or the `Dockerfile` (all four services share one image). Files under `evaluation/` and `.env` are read at runtime and need no rebuild.

```bash
docker compose -f docker/docker-compose.yml build           # rebuild
docker compose -f docker/docker-compose.yml run --build ...  # or rebuild + run in one step
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
