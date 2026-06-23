# Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você entregou um trabalho sólido e bem estruturado! Sua modelagem demonstra boa compreensão dos elementos fundamentais do BPMN: os atores estão corretamente representados em raias, as tarefas seguem as convenções de nomenclatura, os gateways capturam os pontos de decisão do processo e o fluxo geral reflete com fidelidade o enunciado proposto. A nota final de **8,10 / 10** confirma esse bom desempenho. Os ajustes necessários são pontuais e, uma vez corrigidos, elevarão significativamente a qualidade semântica e a clareza do seu diagrama.

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
### Tarefa "Selecionar candidato juntamente com o RH" está desconectada do fluxo de entrada

A tarefa *"Selecionar candidato juntamente com o RH"*, atribuída ao Gestor do Departamento, envia seu fluxo corretamente para *"Enviar oferta ao candidato"*, mas nenhum elemento anterior aponta para ela — ela está, por assim dizer, "solta" no diagrama, sem nenhuma conexão de entrada.

Em BPMN, toda tarefa (exceto aquelas posicionadas imediatamente após um evento de início) precisa ter ao menos uma seta de entrada, indicando o que a desencadeia. Sem essa ligação, o diagrama fica ambíguo: quem lê o modelo não consegue saber quando nem como essa etapa de seleção é ativada. Do ponto de vista do processo, a decisão de selecionar um candidato só faz sentido após as entrevistas terem sido concluídas — portanto, a ausência dessa conexão compromete a rastreabilidade e a lógica sequencial do fluxo.

**Como corrigir:** conecte a tarefa *"Realizar entrevista técnica"* à tarefa *"Selecionar candidato juntamente com o RH"* por meio de uma seta de sequência. A sequência ficaria: *Realizar entrevista comportamental* → *Realizar entrevista técnica* → *Selecionar candidato juntamente com o RH* → *Enviar oferta ao candidato*, representando corretamente a ordem em que gestor e RH tomam a decisão após as entrevistas.

---

<!-- criterio:semantics_2 -->
### Tarefas "Realizar entrevista técnica" e "Candidato eliminado" não possuem fluxo de saída

Duas tarefas do seu diagrama recebem conexões de entrada, mas não levam a nenhum elemento seguinte: *"Realizar entrevista técnica"* e *"Candidato eliminado"*. Isso deixa o fluxo "pendurado", sem continuidade.

Em BPMN, toda tarefa deve ter ao menos um fluxo de saída, pois o diagrama precisa mostrar o que acontece *depois* que cada atividade é concluída. Quando uma tarefa não tem saída, o processo fica incompleto e ambíguo: o leitor não consegue saber se o processo termina ali, retorna a algum ponto anterior ou avança para outra etapa. No caso de *"Realizar entrevista técnica"*, o processo de seleção simplesmente para sem chegar à avaliação dos candidatos; já em *"Candidato eliminado"*, não fica claro se o processo encerra para aquele candidato ou se há algum retorno ao fluxo principal.

**Como corrigir:** para *"Realizar entrevista técnica"*, conecte sua saída à tarefa *"Selecionar candidato juntamente com o RH"*, que é a etapa seguinte natural após as entrevistas. Para *"Candidato eliminado"*, como esse caminho representa o encerramento do fluxo para candidatos descartados na triagem, conecte sua saída a um evento de fim (círculo com borda grossa), sinalizando explicitamente que aquele ramo do processo se encerra ali.

---

<!-- criterio:best_practices_1 -->
### Evento de fim sem rótulo

O evento de fim do seu diagrama — o círculo com borda grossa posicionado após a tarefa *"Realizar integração e treinamentos"* — não possui nenhum rótulo; o campo de texto está vazio.

Em BPMN, eventos de início e fim devem ser rotulados para comunicar claramente *o que* desencadeia o processo e *o que* representa sua conclusão. Um evento sem nome deixa o leitor sem saber qual é o estado final alcançado — neste caso, algo como *"Funcionário integrado"* ou *"Contratação concluída"*. A ausência do rótulo compromete a legibilidade e a capacidade comunicativa do modelo, que é justamente o propósito central de um diagrama de processo.

**Como corrigir:** adicione um rótulo descritivo ao evento de fim. Considerando o contexto do diagrama, uma sugestão adequada seria **"Funcionário contratado e integrado"**, encerrando o fluxo após a integração. O evento de início *"Necessidade de contratação"* já está corretamente rotulado, portanto apenas o evento final precisa dessa correção.

---

<!-- criterio:best_practices_3 -->
### Gateways de decisão sem convergência correspondente

Seu diagrama possui dois gateways de decisão — *"Resultado da triagem"* e *"Resultado da proposta"* — que divergem o fluxo em múltiplos caminhos, mas nenhum deles conta com um gateway de convergência correspondente. Por exemplo, o gateway *"Resultado da triagem"* separa o fluxo em *"Selecionado"* (que segue para as entrevistas) e *"Descartado"* (que vai para *"Candidato eliminado"*), mas esses caminhos nunca se reencontram formalmente. O mesmo ocorre com *"Resultado da proposta"*, cujos ramos *"Oferta aceita"* e *"Oferta recusada"* não convergem por meio de um gateway explícito de junção antes de prosseguir.

Em BPMN, quando um gateway abre múltiplos caminhos alternativos, a boa prática exige um gateway de convergência (geralmente um XOR de junção) para reunir esses caminhos antes de continuar o fluxo. Sem isso, o diagrama fica ambíguo: não fica claro em que ponto o processo retoma um fluxo único, o que pode gerar confusão para quem for implementar ou automatizar o processo.

**Como corrigir:** para o gateway *"Resultado da proposta"*, insira um gateway XOR de convergência logo antes da tarefa *"Realizar integração e treinamentos"*, reunindo os caminhos *"Oferta aceita"* e o retorno de *"Selecionar outro candidato"*. Para o gateway *"Resultado da triagem"*, uma alternativa válida é adicionar um evento de fim específico para o caminho *"Descartado"* — indicando que aquele candidato encerra seu fluxo ali —, enquanto o caminho principal converge adequadamente antes de prosseguir para as entrevistas.

---

## O que você acertou

Você demonstrou domínio consistente dos aspectos estruturais e de boas práticas do BPMN. Veja os destaques:

- **Sintaxe impecável:** você utilizou corretamente os conectores de fluxo de sequência, aplicando-os apenas entre elementos dentro das raias e garantindo que os gateways estejam ligados pelo tipo correto de conector. Isso resultou em nota máxima na categoria de sintaxe.

- **Proposta completa:** todas as tarefas esperadas para o processo foram modeladas, os atores corretos estão representados em suas respectivas raias, os eventos de início e fim foram inseridos adequadamente em cada piscina, e os gateways necessários para capturar os pontos de decisão do processo estão presentes.

- **Boas práticas de nomenclatura:** suas tarefas estão escritas com verbo no infinitivo acompanhado de substantivo, as descrições são breves e objetivas, não há uso de siglas ou abreviações, e tarefas redundantes foram eliminadas. Cada raia identifica claramente seu responsável e as tarefas estão associadas a apenas uma raia.

- **Legibilidade total:** o diagrama obteve nota máxima em legibilidade, o que demonstra cuidado com a organização visual e a clareza da comunicação do modelo.

---

Você está no caminho certo! Os erros encontrados são todos corrigíveis com ajustes pontuais de conexão e rotulagem — nada que comprometa a estrutura geral do seu trabalho. Revise as conexões de entrada e saída das tarefas indicadas, adicione o rótulo ao evento de fim e inclua os gateways de convergência, e seu diagrama estará muito próximo de um modelo profissional e completo. Continue assim!