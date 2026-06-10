# Agent 1 — Criteria Mapper

Receives the BPMN diagram JSON and the evaluation checklist.
For each criterion, maps whether the corresponding element is cumprido, nao_cumprido, nao_aplicavel, or nao_avaliado.
Outputs a list of `BPMNEvidence` objects — no judgment, only evidence mapping.

## Implementação

- Classe principal: `Agent1Analyst` em `agent.py`
- Contrato de saída: `BPMNEvidence` (em `agents/contracts.py`)
- Entrada: dicionário com chaves `diagram` e `checklist`, ou arquivos via `run_from_files(...)`
  - `diagram`: JSON **ou** imagem (`.png`, `.jpg`, `.jpeg`) **ou** PDF
  - `checklist`: JSON **ou** TXT no formato `[(categoria, criterio), ...]` **ou** CSV (colunas: `Categoria`, `Itens avaliados`)
  - O diagrama aceita `elements/flows` e também aliases comuns (`nodes`, `connections`, `sequence_flows`, etc.)

**Observação:** para diagramas em imagem ou PDF, o Agent 1 usa o modelo configurado via `ANTHROPIC_API_KEY` e `MODEL_NAME` no `.env`.

### Campo `value`

O `BPMNEvidence` inclui `value` (0–1) com base na pontuação do checklist:

- Quando o checklist fornece pontuação, `value = pontuação` se `cumprido` e `value = 0.0` se `nao_cumprido/nao_aplicavel/nao_avaliado`.
- Se não houver pontuação no checklist, o fallback é: `cumprido = 1.0`, `nao_cumprido = 0.0`, `nao_aplicavel = 0.0`, `nao_avaliado = 0.0`.

### Significado dos Status

- **`cumprido`**: Critério claramente atendido no diagrama
- **`nao_cumprido`**: Critério não atendido; há evidência clara de falha
- **`nao_aplicavel`**: Critério não se aplica a este diagrama (ex: critério sobre pools em diagrama sem pools)
- **`nao_avaliado`**: Critério não pôde ser avaliado; Agent 1 não conseguiu coletar evidências suficientes para julgar (requer análise manual ou critério muito vago)

### Campo `observation`

Quando não há observação específica, o Agent 1 gera uma mensagem padrão baseada no status:
- Para `cumprido`: "Critério atendido"
- Para `nao_cumprido`: "Critério não atendido" + motivo se disponível
- Para `nao_aplicavel`: "Critério não aplicável" + razão
- Para `nao_avaliado`: "Critério não avaliado" + explicação de que não há evidência

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
