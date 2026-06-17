# Agent 2 — Critic Validator (Agent2Evaluator)

Resumo
------
O Agent 2 recebe a lista de evidências do Agent 1 e valida cada achado. Ele não inventa penalidades: copia a penalidade do checklist e decide se ela deve ser aplicada (status `nao_cumprido`) ou não. Além disso, atribui uma confiança conservadora (0.0–1.0) a cada avaliação e marca itens para revisão humana quando necessário.

Responsabilidades principais
---------------------------
1. Validar se o status reportado pelo Agent 1 é bem suportado pela evidência.
2. Confirmar casos `nao_aplicavel` quando o elemento de referência realmente está ausente.
3. Atribuir `confidence` e sinalizar (`flag_review`) itens abaixo de `CONFIDENCE_THRESHOLD`.
4. Determinar `applied_penalty` de forma determinística: `nao_cumprido` → `checklist_penalty`, caso contrário `0.0`.

Input e Output
---------------
- Input: lista de `BPMNEvidence` (JSON) produzida pelo Agent 1 + checklist CSV (para pesos de categoria).
- Output: arquivo JSON com `summary` e `assessments` (veja `agents/contracts.py` para o contrato `BPMNAssessment`).

Regras de cálculo de penalidade (imutáveis)
-------------------------------------------
- `cumprido` → `applied_penalty = 0.0`
- `nao_aplicavel` → `applied_penalty = 0.0`
- `nao_cumprido` → `applied_penalty = checklist_penalty`

Loop de reflexão
----------------
Antes de finalizar, o agente executa um loop de reflexão (Producer–Critic) que pode iterar até `MAX_ITERATIONS` vezes. O loop para quando:
- `avg_confidence >= CONFIDENCE_THRESHOLD` → `threshold_reached`
- não há mais itens fracos → `no_weak_items`
- atingiu `MAX_ITERATIONS` → `max_iterations`
- confiança estagnou → `stagnant`

Variáveis de ambiente importantes
---------------------------------
Carregadas via `.env`:
- `ANTHROPIC_API_KEY` — requerido para providers que necessitam de chave
- `MODEL_NAME` — modelo usado nas chamadas LLM
- `CONFIDENCE_THRESHOLD` — default `0.6`
- `MAX_ITERATIONS` — default `3`

Como executar
-------------
Exemplo de uso em Python (pipeline local):
```python
from agents.agent2_evaluator.loaders import load_evidence
from agents.agent2_evaluator.evaluator import Agent2Evaluator

evidence = load_evidence('evaluation/results/BPMNEvidence.json')
evaluator = Agent2Evaluator()
assessments = evaluator.run(evidence, checklist_path='evaluation/dataset/Checklist completo - Modelagem 1 - Básico.csv', output_path='evaluation/results/BPMNAssessment.json')
```

Execução rápida para desenvolvimento:
```bash
python -m agents.agent2_evaluator
```

Executar testes (mockados, sem chamadas externas):
```bash
pytest agents/agent2_evaluator/test_evaluator.py -v
```

Estrutura de arquivos
---------------------
```
agent2_evaluator/
├── __init__.py
├── __main__.py
├── evaluator.py
├── planning.py
├── loaders.py
├── test_evaluator.py
└── mocks/
```

Dicas de troubleshooting
-----------------------
- Se `applied_penalty` está 0.0 para muitos `nao_cumprido`, verifique se o campo `checklist_penalty` foi corretamente copiado do `BPMNEvidence` de entrada.
- Para mensagens estranhas no terminal, verifique encoding (Windows CP1252) e remova caracteres especiais nas `print()` se necessário.

Referências
-----------
- Contratos: `agents/contracts.py` (BPMNAssessment)
- Orquestração: `main.py`

Contribuindo
------------
Abra PRs na branch `develop`. Mantenha compatibilidade com o contrato e não altere `applied_penalty` sem coordenação.
