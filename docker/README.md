# Docker

Contains the `Dockerfile` and `docker-compose.yml` for running the pipeline in a container.
The container does exactly what `python main.py` does — it runs the full pipeline
(Agent 1 → Agent 2 → Human Review pause → Agent 3). The Dockerfile's entrypoint is
`python main.py`, so any flags you pass are forwarded straight to it.

Run from the repository root. First create your `.env` (the container reads the API key from it).

Run with the default dataset paths:

```bash
docker compose -f docker/docker-compose.yml run --rm pipeline
```

Run against specific files (same flags as `main.py`):

```bash
docker compose -f docker/docker-compose.yml run --rm pipeline \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --enunciado evaluation/dataset/Instruções.txt \
  --output evaluation/results/
```

## Running a single agent

Each agent has its own compose service (`agent1`, `agent2`, `agent3`) whose entrypoint
is the agent's module, so any flags after the service name are forwarded to that agent.
This is the same invocation `main.py` uses for each step, so you can run the stages
one at a time (each reads the previous stage's file from `evaluation/results/`).

Agent 1 — Criteria Mapper (writes `BPMNEvidence.json`):

```bash
docker compose -f docker/docker-compose.yml run --rm agent1 \
  --diagram evaluation/dataset/diagram_001.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --output evaluation/results/BPMNEvidence.json
```

Agent 2 — Critic Validator (reads evidence, writes `BPMNAssessment.json`):

```bash
docker compose -f docker/docker-compose.yml run --rm agent2 \
  --evidence evaluation/results/BPMNEvidence.json \
  --checklist "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv" \
  --output evaluation/results/BPMNAssessment.json
```

Agent 3 — Feedback Generator (reads assessment, writes `BPMNFeedback.json`):

```bash
docker compose -f docker/docker-compose.yml run --rm agent3 \
  --diagram evaluation/dataset/diagram_001.json \
  --enunciado evaluation/dataset/Instruções.txt \
  --assessment evaluation/results/BPMNAssessment.json \
  --output evaluation/results/BPMNFeedback.json
```

Each agent also accepts no flags (it falls back to its own default paths), and
`agent1`/`agent3` support `--interactive` for terminal prompts.

Notes:

- `evaluation/` is mounted from the host, so inputs are read from your working copy and
  results are written back to `evaluation/results/` on the host.
- The container runs with an interactive TTY, so the Human Review pause works:
  the pipeline stops after Agent 2 for you to edit `BPMNAssessment.json`, then
  press ENTER to continue.
- Required input files (must exist in the repo): a diagram JSON, the checklist CSV,
  and the enunciado TXT. A missing path makes the pipeline fail with `FileNotFoundError`.
- Dependencies and agent code are baked into the image — rebuild after changing
  `requirements.txt`, the agents, or the `Dockerfile`:
  `docker compose -f docker/docker-compose.yml build` (or add `--build` to a `run`).
