# Agent 1 — Criteria Mapper

Receives the BPMN diagram JSON and the evaluation checklist.
For each criterion, maps whether the corresponding element is present, absent, or incorrect.
Outputs a list of `BPMNEvidence` objects — no judgment, only evidence mapping.

## Implementação

- Classe principal: `Agent1Analyst` em `agent.py`
- Contrato de saída: `BPMNEvidence` (em `agents/contracts.py`)
- Entrada: dicionário com chaves `diagram` e `checklist`, ou arquivos via `run_from_files(...)`
  - `diagram`: JSON
  - `checklist`: JSON **ou** TXT no formato `[(categoria, criterio), ...]`
  - O diagrama aceita `elements/flows` e também aliases comuns (`nodes`, `connections`, `sequence_flows`, etc.)

### Exemplo rápido

```python
from agents.agent1_analyst import Agent1Analyst

agent = Agent1Analyst()
evidences = agent.run_from_files("evaluation/dataset/diagram_001.json", "evaluation/dataset/checklist.txt")
print(agent.serialize(evidences))
```

## Execução via terminal

Modo interativo (pergunta os caminhos no terminal):

```bash
python -m agents.agent1_analyst --interactive
```

Modo com seleção gráfica de arquivos:

```bash
python -m agents.agent1_analyst --gui
```

No modo GUI, você escolhe a pasta de saída **apenas no final** e o arquivo é salvo como `BPMNEvidence.json`.

Modo direto com argumentos:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/checklist.json
```

Para salvar em arquivo:

```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/checklist.json --output evaluation/results
```

Com `--output`, o arquivo final também é `BPMNEvidence.json`.
