FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENTRYPOINT ["sh", "-lc"]
CMD ["set -e; cmd=$(awk 'p {print; exit} /^#[[:space:]]*All/ {p=1}' /app/commands.txt | tr -d '\\r'); if [ -z \"$cmd\" ]; then echo \"Linha #All não encontrada em commands.txt\"; exit 1; fi; eval \"$cmd\""]
