# Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você demonstrou um bom domínio geral da notação BPMN nesta atividade. Sua modelagem cobre os elementos essenciais do processo descrito, com organização clara de raias, tarefas bem nomeadas e uso adequado dos conectores. A nota final reflete um trabalho sólido, com alguns pontos de atenção relacionados principalmente à conectividade entre elementos e a boas práticas de rotulagem e estruturação de gateways — aspectos que, uma vez corrigidos, elevarão significativamente a qualidade do seu diagrama.

---

## Resultado

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -1.50 | 0.50 | 2.00 |
| best_practices | 20% | -0.40 | 1.60 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

**Nota final: 8.10 / 10**

---

## Pontos a melhorar

<!-- criterio:semantics_1 -->
### Tarefa "Selecionar candidato juntamente com o RH" está sem fluxo de entrada

A tarefa **"Selecionar candidato juntamente com o RH"**, posicionada na raia do Gestor do Departamento, não possui nenhuma seta de entrada conectada a ela. Ela até envia um fluxo para a tarefa seguinte ("Enviar oferta ao candidato"), mas nenhum elemento anterior aponta para ela, deixando-a "flutuando" no diagrama.

Em BPMN, toda tarefa — exceto aquelas posicionadas imediatamente após um evento de início — precisa ter ao menos um fluxo de sequência de entrada. Essa regra existe para garantir que qualquer pessoa que leia o diagrama consiga entender *quando* e *por que* aquela atividade é executada. Sem essa conexão, o processo fica ambíguo: não fica claro o que dispara a etapa de seleção do candidato, tornando o modelo semanticamente inválido.

A correção é direta: no enunciado, a seleção ocorre *após* as entrevistas. No seu diagrama, a tarefa **"Realizar entrevista técnica"** é a última etapa de entrevista e não possui fluxo de saída conectado a nada. Basta adicionar uma seta de sequência saindo de "Realizar entrevista técnica" e apontando para "Selecionar candidato juntamente com o RH", tornando explícito que a seleção acontece após a conclusão das entrevistas.

---

<!-- criterio:semantics_2 -->
### Tarefas "Realizar entrevista técnica" e "Candidato eliminado" estão sem fluxo de saída

Duas tarefas no seu diagrama não possuem nenhum fluxo de saída, criando "becos sem saída" no processo: **"Realizar entrevista técnica"** (que recebe a seta vinda de "Realizar entrevista comportamental") e **"Candidato eliminado"** (que recebe a seta do gateway "Resultado da triagem" pelo caminho "Descartado").

Em BPMN, toda tarefa deve ter exatamente um fluxo de sequência de saída, pois o diagrama precisa representar o que acontece *depois* de cada atividade ser concluída. Quando uma tarefa não tem saída, o processo fica semanticamente incompleto — quem lê o diagrama não consegue saber o que ocorre após a entrevista técnica ser realizada ou após um candidato ser descartado. Vale notar também que "Candidato eliminado" descreve um *resultado*, e não uma *ação executada por alguém*, o que compromete adicionalmente a clareza do modelo.

Para corrigir, conecte a saída de **"Realizar entrevista técnica"** à tarefa "Selecionar candidato juntamente com o RH", que já existe no diagrama e representa o passo natural após as entrevistas. Quanto a **"Candidato eliminado"**, considere renomeá-la para algo como "Notificar candidato eliminado" — transformando-a em uma ação real — e conecte sua saída a um evento de fim. Alternativamente, você pode remover essa tarefa e conectar diretamente a saída "Descartado" do gateway a um evento de fim, indicando que aquele caminho do processo se encerra ali.

---

<!-- criterio:best_practices_1 -->
### Evento de fim está sem rótulo

O evento de fim do seu diagrama — aquele conectado à saída da tarefa "Realizar integração e treinamentos" — aparece sem nenhum rótulo, ao contrário do evento de início "Necessidade de contratação", que está corretamente identificado.

Rotular os eventos de início e fim é uma boa prática essencial em BPMN, pois eles comunicam, respectivamente, o que desencadeia o processo e qual é o resultado final alcançado. Um evento de fim sem rótulo deixa o leitor sem saber o que o processo entrega ao terminar — neste caso, não fica claro que o processo se conclui com o novo funcionário integrado à empresa. Isso compromete a legibilidade e a utilidade do modelo como ferramenta de comunicação entre as partes envolvidas.

A correção é simples: adicione um rótulo descritivo ao evento de fim. Sugestões adequadas ao contexto seriam **"Funcionário integrado"** ou **"Contratação concluída"**, refletindo que o processo se encerra após a realização da integração e dos treinamentos.

---

<!-- criterio:best_practices_3 -->
### Gateways de decisão estão sem convergência correspondente

No seu diagrama, os dois gateways de decisão — **"Resultado da triagem"** e **"Resultado da proposta"** — divergem o fluxo em caminhos alternativos, mas nenhum deles possui um gateway de convergência correspondente. O gateway "Resultado da triagem" separa o fluxo em "Selecionado" (que segue para a entrevista comportamental) e "Descartado" (que vai para "Candidato eliminado"), mas esses caminhos nunca se reencontram em um ponto comum. Da mesma forma, o gateway "Resultado da proposta" divide o fluxo em "Oferta aceita" e "Oferta recusada", e o caminho de recusa leva a "Selecionar outro candidato", que reconecta à tarefa "Enviar oferta ao candidato" — criando um loop sem gateway de convergência formal.

Em BPMN, quando um gateway exclusivo (XOR) abre caminhos alternativos, espera-se que haja um gateway de convergência para reunir esses caminhos antes de o processo continuar. Sem isso, o diagrama fica estruturalmente incompleto e ambíguo, dificultando a compreensão de onde o processo retoma um fluxo único após cada decisão.

Para corrigir: no gateway **"Resultado da triagem"**, adicione um evento de fim após "Candidato eliminado", sinalizando que aquele caminho encerra o processo para esse candidato específico. No gateway **"Resultado da proposta"**, insira um gateway de convergência XOR após "Selecionar outro candidato" e após "Realizar integração e treinamentos", reunindo os fluxos antes do evento de fim já existente no diagrama. Essas mudanças tornarão o modelo bem-formado e muito mais fácil de interpretar.

---

## O que você acertou

Você teve um desempenho excelente em sintaxe e na proposta de modelagem, atingindo a pontuação máxima nessas categorias. Isso demonstra que você compreende bem as regras estruturais do BPMN e soube interpretar corretamente o processo descrito no enunciado.

Em termos de **sintaxe**, você utilizou corretamente o conector de fluxo de sequência, inclusive nas conexões entre raias e nos gateways. Inseriu eventos de início e fim adequadamente, mantendo apenas um evento inicial por piscina, e os gateways foram conectados com mais de um fluxo de saída, como esperado.

Quanto à **proposta**, todas as tarefas esperadas para o processo foram modeladas, os atores corretos foram representados em suas respectivas raias, os eventos e gateways necessários estão presentes, e cada tarefa foi associada a apenas uma raia. Não há tarefas redundantes nem tarefas que representem resultados em vez de ações.

Na **legibilidade**, você também acertou em cheio: as tarefas estão nomeadas com substantivo e verbo no infinitivo, as descrições são breves e objetivas, sem uso de siglas ou abreviações, e todos os elementos estão conectados entre si.

---

No geral, este é um trabalho bem construído e que demonstra clareza no entendimento de BPMN. Os ajustes necessários são pontuais — conectar algumas setas, adicionar um rótulo e incluir gateways de convergência — e não comprometem a estrutura geral do seu diagrama. Com essas correções, seu modelo estará completo e alinhado às boas práticas da notação. Continue assim!