# Agent 3 — Formative Feedback Generator (Agent3Feedback)

Resumo
------
O Agent 3 recebe o `BPMNAssessment` (após revisão humana) e o diagrama BPMN, calcula a nota final por categoria e gera feedbacks formativos e personalizados para cada item penalizado. O agente garante cobertura: itens penalizados sem feedback disparam tentativas adicionais.

Principais responsabilidades
---------------------------
- Calcular a nota final a partir dos `BPMNAssessment` (determinístico, em Python).
- Gerar feedback personalizado apenas para critérios `nao_cumprido` usando o LLM.
- Incluir a frase de feedback pré-escrita do checklist quando necessário e contextualizar com o elemento do estudante.
- Emitir um `BPMNFeedback` consistente com o contrato (`agents/contracts.py`).

Por que chamamos o LLM somente para `nao_cumprido`
------------------------------------------------
Para reduzir tokens e evitar geração desnecessária: itens `cumprido`, `nao_aplicavel` e `nao_avaliado` recebem mensagens fixas; apenas `nao_cumprido` exige explicação e sugestão de correção.

Contrato e cálculo da nota
--------------------------
- `BPMNAssessment` → campos relevantes: `category_weight`, `status`, `applied_penalty` (copiado por Agent 2).
- Nota por item: `item_score = (1.0 - applied_penalty) * category_weight`.
  - `nao_aplicavel` recebe `applied_penalty = 0.0` (não subtrai pontos).
  - `nao_avaliado` é excluído da nota (tratado como 0.0 no relatório).
- Resultado final: soma das notas por categoria e total (escala 0–10 é calculada no pipeline, conforme implementação).

Entrada / Saída
---------------
- Input: `diagram` (JSON) + `BPMNAssessment.json` (output do Agent 2) + `enunciado` (texto da tarefa).
- Output: `BPMNFeedback.json` com `grades_and_feedbacks`: lista de [ItemGrade, feedback_text].

CLI — exemplos
---------------
Executar localmente (usa arquivos já gerados pelos agentes anteriores):

```bash
python -m agents.agent3_feedback --diagram evaluation/dataset/OK_1.json \
  --enunciado evaluation/dataset/Instruções.txt \
  --assessment evaluation/results/BPMNAssessment.json \
  --output evaluation/results/
```

Executar no container (rebuild se for necessário):

```bash
# Rebuild para garantir imagem atual
docker compose -f docker/docker-compose.yml build --no-cache

# Rodar somente o Agent 3 (monta volumes para evaluation/)
docker compose -f docker/docker-compose.yml run --rm agent3 \
  --diagram evaluation/dataset/OK_1.json \
  --enunciado evaluation/dataset/Instruções.txt \
  --assessment evaluation/results/BPMNAssessment.json \
  --output evaluation/results/
```

Problemas comuns e soluções
---------------------------
- Saída antiga mostrando "Sem problemas": provavelmente você está lendo um `BPMNFeedback.json` gerado por uma execução anterior. Verifique o timestamp em `evaluation/results/BPMNFeedback.json` ou remova o arquivo antes de rodar.
- Docker continua mostrando saída antiga: faça `docker compose build --no-cache` e reexecute o serviço `agent3`.
- Permissão negada ao salvar em `evaluation/results/`: rode o container com permissões corretas ou ajuste permissões do diretório no host.
- `get_chat_model()` exige `temperature` (erro de TypeError): o Agent 3 define `get_chat_model(temperature=0.3)`; verifique a versão do módulo `agents.shared_tools.llm` se modificada.

Dicas para depuração rápida
--------------------------
1. Rodar Agent 3 isolado com arquivos existentes (não orquestrar todo o pipeline).
2. Verifique `BPMNAssessment.json` — se `applied_penalty` estiver 0.0 para itens `nao_cumprido`, o problema é no Agent 2 (não editar aqui).
3. Limpe caches e artefatos antigos: remova `evaluation/results/BPMNFeedback.json` antes de rodar.

Referências
-----------
- Contratos: `agents/contracts.py` (BPMNFeedback, ItemGrade)
- Código: `agents/agent3_feedback/agent.py`, `chains.py`, `cli.py`

Contribuição e notas
--------------------
- Modificações de contrato exigem alinhamento de equipe.
- Abra PRs contra `develop` e descreva testes e validações executadas.
