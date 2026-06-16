# Agent 1 — Criteria Mapper (Agent1Analyst)

Resumo
------
O Agent 1 recebe um diagrama BPMN (JSON/PNG/PDF) e a checklist de avaliação e produz uma lista de evidências (BPMNEvidence). Ele não decide pontuações: mapeia apenas se cada critério foi cumprido, não cumprido, não aplicável ou não avaliado.

Por que isso importa
--------------------
- Garante auditabilidade: toda decisão é baseada em elementos presentes no diagrama.
- Evita alocações de nota automatizadas nessa etapa — isso fica para o Agent 2/3.

Contrato de entrada/saída
-------------------------
- Entrada: `diagram` (JSON/PNG/PDF) e `checklist` (CSV/JSON/TXT).
- Saída: lista serializável de `BPMNEvidence` (ver `agents/contracts.py`).

Status possíveis em cada evidência
----------------------------------
- `cumprido`: critério claramente atendido.
- `nao_cumprido`: critério existe no diagrama mas não atende.
- `nao_aplicavel`: elemento de referência ausente → critério fora de escopo.
- `nao_avaliado`: evidência insuficiente para decidir (requer revisão humana).

Regra importante: `nao_aplicavel` vs `nao_cumprido`
-------------------------------------------------
Um critério é `nao_aplicavel` apenas quando o elemento de referência NÃO existe no diagrama. Se o elemento existe e viola a regra, o status deve ser `nao_cumprido`.

Campo `value`
--------------
`value` copia a penalidade indicada no checklist (se presente). Caso o checklist não informe pontuação, usa-se fallback: `cumprido=1.0`, outros=0.0.

Exemplo de uso rápido
---------------------
```python
from agents.agent1_analyst import Agent1Analyst
agent = Agent1Analyst()
evidences = agent.run_from_files("evaluation/dataset/diagram_001.json", "evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv")
print(agent.serialize(evidences))
```

Modo CLI / Execução
-------------------
Pré-requisitos:
```bash
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Rodar em modo interativo (pergunta caminhos no terminal):
```bash
python -m agents.agent1_analyst --interactive
```

Rodar direto (arquivo de entrada → saída):
```bash
python -m agents.agent1_analyst --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/Checklist.csv --output evaluation/results
```

Suporte a PDF/Imagem
--------------------
PDFs e imagens exigem chaves de API (visão/OCR) e o `MODEL_NAME` apropriado no `.env`.

Dicas de troubleshooting
------------------------
- Se um critério está marcado `nao_aplicavel` mas você espera `nao_cumprido`, verifique se o elemento de referência realmente existe no JSON.
- Não edite `evaluation/dataset/` diretamente — crie cópias para testes.
- Para debug rápido, serialize a saída e inspecione o campo `observation` em cada evidence.

Referências
----------
- Contratos: `agents/contracts.py` (BPMNEvidence)
- Pipeline orchestration: `main.py` (Agent 1 → Agent 2 → Agent 3)

Licença / Contribuição
----------------------
Faça PRs para a branch `develop`. Consulte o guia de commits no repositório.
