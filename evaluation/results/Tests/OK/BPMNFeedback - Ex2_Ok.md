# Relatório de Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você entregou um trabalho de excelente qualidade, com uma nota final de **9.80 / 10**. Sua modelagem demonstra compreensão sólida dos conceitos de BPMN e você conseguiu representar corretamente a maioria dos elementos esperados: tarefas, eventos, piscinas, raias e gateways. O diagrama está bem estruturado, com nomenclatura adequada e fluxos bem conectados. Há apenas um ponto específico de melhoria relacionado à convergência de gateways que, quando corrigido, tornará seu modelo ainda mais robusto e alinhado com as melhores práticas de modelagem.

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
### Convergência de gateways

Você abriu dois gateways de decisão no seu diagrama — "Resultado da triagem" e "Resultado da proposta" — que criam caminhos divergentes sem convergência posterior. No primeiro gateway, candidatos "Selecionado" prosseguem enquanto "Descartado" terminam o fluxo. No segundo, "Oferta aceita" segue para integração e "Oferta recusada" retorna para selecionar outro candidato. O problema é que esses fluxos paralelos nunca se encontram novamente em um ponto comum.

Em BPMN, quando um gateway abre múltiplos caminhos, eles devem convergir em um gateway de junção antes de continuar o fluxo principal. Isso garante clareza estrutural e evita ambiguidades sobre quando o processo realmente prossegue. Sem convergência, fica confuso se o processo termina quando um candidato é descartado ou se há atividades que devem ocorrer independentemente do caminho escolhido. Além disso, compromete a rastreabilidade e a compreensão do processo por outros stakeholders.

**Para corrigir:** Adicione um gateway de convergência (junção) após o "Resultado da triagem" que receba tanto o fluxo "Descartado" quanto o fluxo "Selecionado", permitindo que o processo continue de forma controlada. Da mesma forma, após o "Resultado da proposta", crie uma convergência que unifique os caminhos "Oferta aceita" e "Oferta recusada" antes de prosseguir para as próximas atividades. Isso tornará o fluxo mais estruturado e fácil de entender.

## O que você acertou

Você demonstrou domínio excelente dos fundamentos de BPMN. Todos os elementos esperados foram modelados corretamente: as tarefas estão bem definidas e no infinitivo, os eventos de início e fim estão presentes em cada piscina com rótulos apropriados, e as raias representam adequadamente os atores (RH e Gestor de Departamento). 

Os gateways foram corretamente identificados e conectados com fluxos de sequência, e você conseguiu capturar a lógica do processo de forma clara. A nomenclatura é consistente, sem abreviaturas desnecessárias, e todas as tarefas estão associadas a apenas uma raia. Além disso, você eliminou redundâncias e garantiu que todos os elementos estejam conectados, criando um diagrama coeso e fácil de seguir.

---

Parabéns pelo excelente trabalho! Você está no caminho certo e demonstra sólida compreensão de modelagem de processos. Com a simples adição de gateways de convergência, seu diagrama estará ainda mais robusto e seguirá rigorosamente as melhores práticas de BPMN. Continue assim!

## Resultado (oficial)

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -0.00 | 2.00 | 2.00 |
| best_practices | 20% | -0.20 | 1.80 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

**Nota final: 9.80 / 10**