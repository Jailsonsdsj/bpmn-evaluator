# Relatório de Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você entregou uma modelagem bem estruturada do processo de recrutamento e seleção em BPMN, demonstrando compreensão sólida dos elementos fundamentais: piscinas, raias, tarefas, eventos e gateways. Sua nota final foi **8.10 / 10**, o que indica um trabalho de boa qualidade com alguns pontos de refinamento necessários, principalmente relacionados à conectividade do fluxo e à convergência de gateways. Os erros identificados são corrigíveis e não comprometem a estrutura geral do diagrama.

## Resultado

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -1.50 | 0.50 | 2.00 |
| best_practices | 20% | -0.40 | 1.60 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

## Pontos a melhorar

<!-- criterio:semantics_1 -->
### Conectar tarefas desconectadas ao fluxo principal

Você tem uma tarefa importante — "Selecionar candidato juntamente com o RH" — que está flutuando no diagrama sem receber uma seta de entrada do fluxo anterior. Especificamente, ela não está conectada à tarefa "Realizar entrevista comportamental". Em BPMN, toda tarefa precisa estar integrada ao fluxo contínuo, com pelo menos uma entrada e uma saída, para que fique claro quando ela deve ser executada e de onde vêm seus dados. Sem essa conexão, o diagrama fica ambíguo e impede que o processo seja automatizado ou compreendido corretamente.

**Como corrigir:** Desenhe uma seta de fluxo saindo de "Realizar entrevista comportamental" e conecte-a à tarefa "Selecionar candidato juntamente com o RH". Isso garantirá que a sequência de execução seja clara: após a entrevista comportamental, o fluxo segue naturalmente para a seleção do candidato, que então prossegue para o gateway "Resultado da proposta".

<!-- criterio:semantics_2 -->
### Completar fluxos de saída das tarefas

Duas tarefas em seu diagrama terminam abruptamente sem indicar o que acontece depois: "Realizar entrevista técnica" (na raia do Gestor do departamento) e "Candidato eliminado" (na raia de Recursos Humanos). Sem fluxos de saída, o processo fica travado — não está claro se o candidato segue para a próxima etapa, se o processo continua com outros candidatos ou se termina ali.

**Como corrigir:** Para "Realizar entrevista técnica", adicione uma seta conectando-a à tarefa "Realizar entrevista comportamental", completando a sequência de entrevistas. Para "Candidato eliminado", conecte-a a um evento final apropriado (como "Processo finalizado para candidato descartado") ou, se o processo deve continuar avaliando outros candidatos, reconecte-a ao ponto onde novos candidatos são considerados. Assim, cada tarefa terá um destino claro.

<!-- criterio:best_practices_1 -->
### Adicionar rótulo ao evento final

O evento de fim que aparece após "Realizar integração e treinamentos" está vazio, sem um rótulo identificador. Enquanto seu evento inicial "Necessidade de contratação" tem o nome claramente escrito, o evento final não possui descrição. Isso deixa ambíguo qual é o estado final alcançado — o funcionário foi efetivamente integrado? O processo terminou com sucesso?

**Como corrigir:** Adicione um rótulo descritivo ao evento final. Uma sugestão apropriada seria "Funcionário integrado e pronto para atuar" ou "Processo de integração concluído". Isso deixará evidente que o processo se encerra quando o novo funcionário completa seu treinamento e está apto a trabalhar no departamento.

<!-- criterio:best_practices_3 -->
### Implementar convergência de gateways

Seu diagrama possui dois gateways de divergência — "Resultado da triagem" e "Resultado da proposta" — que abrem caminhos alternativos (candidatos descartados vs. selecionados; oferta aceita vs. recusada), mas esses caminhos nunca se encontram novamente em um gateway de convergência. Por exemplo, após "Resultado da triagem", o fluxo se divide em "Candidato eliminado" e "Realizar entrevista comportamental", mas essas alternativas não convergem antes de prosseguir.

**Como corrigir:** Adicione um gateway de convergência após cada divergência. Por exemplo, após "Resultado da triagem", os fluxos de "Candidato eliminado" e "Realizar entrevista comportamental" devem se reunir em um único gateway antes de continuar. Da mesma forma, após "Resultado da proposta", os fluxos de "Realizar integração" e "Selecionar outro candidato" devem convergir em um gateway que encerre ou reinicie o ciclo apropriadamente. Isso garante uma estrutura clara e controlada do processo.

## O que você acertou

Você demonstrou excelente domínio dos fundamentos de BPMN. Todos os elementos esperados foram modelados corretamente: as tarefas estão bem descritas (com substantivos e infinitivos), as raias representam adequadamente os atores (RH e Gestor do departamento), os eventos de início foram inseridos, os gateways possuem múltiplos fluxos e estão conectados por sequências apropriadas. 

Além disso, você identificou corretamente as tarefas necessárias para o processo (triagem, entrevistas, seleção, integração), evitou redundâncias, não usou abreviaturas e manteve as descrições breves e objetivas. A sintaxe do diagrama está impecável, e a proposta geral do modelo reflete bem o processo descrito no enunciado.

---

Você está no caminho certo! Os erros identificados são questões de refinamento — conectividade e estrutura — que são facilmente corrigíveis. Com as ajustes sugeridos, seu diagrama ficará ainda mais robusto e pronto para ser utilizado como base para automação ou comunicação do processo. Continue praticando e refinando seus diagramas BPMN; você já tem uma base sólida.

## Resultado (oficial)

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -1.50 | 0.50 | 2.00 |
| best_practices | 20% | -0.40 | 1.60 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

**Nota final: 8.10 / 10**