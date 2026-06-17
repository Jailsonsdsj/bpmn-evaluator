FROM python:3.11-slim

WORKDIR /app

# HOME=/tmp: the container may run as an arbitrary host uid with no home dir.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOME=/tmp

# gosu: the entrypoint drops root -> the host user's uid/gid at runtime.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# entrypoint.sh drops root -> owner of the bind-mounted evaluation/ so result
# files are written as the host user. Extra args (--diagram / --checklist /
# --enunciado / --output) are still forwarded to main.py; single agents
# override the program part (see docker-compose.yml).
ENTRYPOINT ["/usr/local/bin/entrypoint.sh", "python", "main.py"]
