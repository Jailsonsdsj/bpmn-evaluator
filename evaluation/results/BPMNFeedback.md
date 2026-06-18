# Relatório de Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você apresentou uma modelagem muito sólida do processo de recrutamento e seleção, demonstrando compreensão clara dos elementos fundamentais de BPMN. Seu diagrama está bem estruturado, com sintaxe correta, elementos apropriados e uma representação fiel do processo descrito. A nota final de **9.80 / 10** reflete um trabalho de excelente qualidade, com apenas um ajuste necessário relacionado à convergência de gateways.

## Resultado

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -0.00 | 2.00 | 2.00 |
| best_practices | 20% | -0.20 | 1.80 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

## Pontos a melhorar

<!-- criterio:best_practices_3 -->
### Gateways sem convergência correspondente

No seu diagrama, você utilizou dois gateways de divergência — "Resultado da triagem" e "Resultado da proposta" — que abrem múltiplos caminhos alternativos, mas esses caminhos não se reúnem em um gateway de convergência. Por exemplo, após o gateway "Resultado da triagem", o fluxo se divide entre "Selecionado" (levando à entrevista comportamental) e "Descartado" (levando a "Candidato eliminado"), mas essas duas trajetórias nunca convergem novamente. O mesmo acontece com "Resultado da proposta", cujos caminhos não se encontram antes de prosseguir.

Essa falta de convergência é problemática porque viola um princípio fundamental de BPMN: quando um gateway abre múltiplos caminhos, ele deve fechá-los em um ponto comum. Sem isso, fica ambíguo qual é o próximo passo do processo após determinadas atividades — por exemplo, o que acontece depois que um candidato é eliminado ou quando uma oferta é recusada. Isso prejudica a clareza e a executabilidade do processo.

**Para corrigir**, adicione um gateway de convergência (XOR ou AND, conforme apropriado) após cada divergência. Por exemplo: os caminhos "Selecionado" e "Descartado" do gateway "Resultado da triagem" devem convergir em um único gateway antes de prosseguir para a próxima etapa comum. Da mesma forma, após "Resultado da proposta", os caminhos "Oferta aceita" e "Oferta recusada" devem se reunir em um gateway que dirija o fluxo para a integração ou para a seleção de outro candidato, conforme o caso.

## O que você acertou

Você demonstrou excelente domínio dos elementos essenciais de BPMN:

- **Sintaxe impecável**: Todos os conectores, eventos e gateways foram utilizados corretamente, sem erros de notação.
- **Estrutura clara**: As piscinas e raias representam adequadamente os atores (RH, Gestor, Candidato), e cada elemento está associado ao responsável correto.
- **Cobertura completa**: Você modelou todas as tarefas esperadas, eventos de início e fim, gateways de decisão e os atores envolvidos no processo.
- **Nomenclatura apropriada**: As tarefas estão bem descritas, em infinitivo, sem abreviaturas, e todas as atividades representam ações concretas.
- **Conectividade**: Todos os elementos estão adequadamente conectados, e o fluxo é facilmente rastreável de ponta a ponta.

## Considerações finais

Você está no caminho certo! Esse é um trabalho de alta qualidade que demonstra compreensão sólida de modelagem de processos. O ajuste necessário é pontual e fácil de implementar — trata-se apenas de adicionar gateways de convergência para fechar os caminhos abertos pelas divergências. Com essa pequena melhoria, seu diagrama será ainda mais robusto e seguirá rigorosamente as melhores práticas de BPMN. Continue assim!

## Resultado (oficial)

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -0.00 | 2.00 | 2.00 |
| best_practices | 20% | -0.20 | 1.80 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

**Nota final: 9.80 / 10**