# Agent 1 — Criteria Mapper

Receives the BPMN diagram JSON and the evaluation checklist.
For each criterion, maps whether the corresponding element is present, absent, or incorrect.
Outputs a list of `BPMNEvidence` objects — no judgment, only evidence mapping.

## Implementação

- Classe principal: `Agent1Analyst` em `agent.py`
- Contrato de saída: `BPMNEvidence` (em `agents/contracts.py`)
- Entrada: dicionário com chaves `diagram` e `checklist`, ou arquivos via `run_from_files(...)`
  - `diagram`: JSON **ou** imagem (`.png`, `.jpg`, `.jpeg`) **ou** PDF
  - `checklist`: JSON **ou** TXT no formato `[(categoria, criterio), ...]` **ou** CSV (colunas: `Categoria`, `Itens avaliados`)
  - O diagrama aceita `elements/flows` e também aliases comuns (`nodes`, `connections`, `sequence_flows`, etc.)

**Observação:** para diagramas em imagem ou PDF, o Agent 1 usa o modelo configurado via `ANTHROPIC_API_KEY` e `MODEL_NAME` no `.env`.

### Exemplo rápido

```python
from agents.agent1_analyst import Agent1Analyst

agent = Agent1Analyst()
evidences = agent.run_from_files("evaluation/dataset/diagram_001.json", "evaluation/dataset/checklist.txt")
print(agent.serialize(evidences))
```

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

Ao rodar sem argumentos, a **interface gráfica** é aberta automaticamente:

```bash
python -m agents.agent1_analyst
```

A GUI permite anexar **vários diagramas**, anexar o checklist e executar.  
A pasta de saída é escolhida **no final** e o arquivo é salvo como `BPMNEvidence.json`.

Se mais de um diagrama for anexado, cada saída fica em uma subpasta com o nome do diagrama:

```
<pasta_saida>\<nome_do_diagrama>\BPMNEvidence.json
```

Modo interativo (pergunta os caminhos no terminal):

```bash
python -m agents.agent1_analyst --interactive
```

Modo direto com argumentos:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/checklist.json
```

Imagem como diagrama:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.png --checklist evaluation/dataset/checklist.csv
```

PDF como diagrama:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.pdf --checklist evaluation/dataset/checklist.csv
```

Para salvar em arquivo:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/checklist.json --output evaluation/results
```

Com `--output`, o arquivo final também é `BPMNEvidence.json`.
