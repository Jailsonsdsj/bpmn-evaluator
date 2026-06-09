FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# The container runs the full pipeline exactly like `python main.py`:
# Agent 1 → Agent 2 → Human Review pause → Agent 3.
# Any extra arguments (--diagram / --checklist / --enunciado / --output)
# are forwarded straight to main.py.
ENTRYPOINT ["python", "main.py"]
