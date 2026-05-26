# Docker

Contains the `Dockerfile` and `docker-compose.yml` for running the agents/pipeline in a container.
Use the compose file from the repository root:

```bash
docker compose -f docker/docker-compose.yml run --rm app -m agents.agent1_analyst --help
```

Pipeline (single command):

```bash
docker compose -f docker/docker-compose.yml run --rm pipeline
```

The pipeline container runs the command after `#All` in `commands.txt`.
Update that line with the paths you want to run.

Docker Desktop: running the image directly also executes the `#All` command.

Required files (must exist inside the repo):

- Diagram (JSON/PDF/image)
- Checklist (CSV/TXT/JSON)
- Enunciado (TXT)
