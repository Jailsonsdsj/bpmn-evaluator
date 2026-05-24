# Agent 3 — Formative Feedback Generator

Receives the human-validated `BPMNAssessment` and the BPMN diagram JSON from the review step.
Generates personalized, actionable formative feedback for the student per penalized item.
Verifies full coverage before emitting — items without feedback trigger a second targeted call.

## Implementação

- Classe principal: `Agent3Feedback` em `agent.py`
- Saída: `BPMNFeedback` (em `agents/contracts.py`)
- Entrada: dicionário com chaves `diagram` e `checklist`, ou arquivos via `run_from_files(...)`
  - `diagram`: JSON **ou** imagem (`.png`, `.jpg`, `.jpeg`) **ou** PDF
  - `BPMNAssessment`
  - O diagrama aceita `elements/flows` e também aliases comuns (`nodes`, `connections`, `sequence_flows`, etc.)

**Observação:** para diagramas em imagem ou PDF, o Agent 1 usa o modelo configurado via `ANTHROPIC_API_KEY` e `MODEL_NAME` no `.env`.


## Execução via terminal

### Pré-requisitos

Ative a venv e instale as dependências:

```bash
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

No `.env`, configure as variáveis (obrigatórias para imagem/PDF):

```
ANTHROPIC_API_KEY=...
MODEL_NAME=...
```
ou
```
GEMINI_API_KEY=...
MODEL_NAME=...
```

Ao rodar sem argumentos, a **interface gráfica** é aberta automaticamente:

```bash
python -m agents.agent3_feedback
```

GUI permite anexar **vários diagramas**, anexar o checklist e executar.  
A pasta de saída é escolhida **no final** e o arquivo é salvo como `BPMNFeedback.json`.

Modo direto com argumentos:

```bash
python -m agents.agent3_feedback --diagram evaluation/dataset/diagram-somnet.json --enunciado evaluation/dataset/Instruções.txt --assessment evaluation/dataset/BPMNEvidence-3-revised.json
```

Para salvar em arquivo:

```bash
python -m agents.agent3_feedback --diagram evaluation/dataset/diagram-somnet.json --enunciado evaluation/dataset/Instruções.txt --assessment evaluation/dataset/BPMNEvidence-3-revised.json --output BPMNFeedback.json
```