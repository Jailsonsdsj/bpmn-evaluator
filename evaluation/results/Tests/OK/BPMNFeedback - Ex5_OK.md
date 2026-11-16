# Avaliação – Modelagem do Processo de Recrutamento e Seleção

Você entregou uma modelagem bastante sólida do processo de Recrutamento e Seleção. Seu diagrama demonstra domínio consistente dos elementos fundamentais do BPMN: os atores estão corretamente representados em raias, os eventos e gateways foram aplicados com propriedade, e a legibilidade do modelo é excelente. A nota final reflete esse desempenho elevado, com apenas um ponto de melhoria identificado, relacionado a uma boa prática de convergência de gateways.

---

## Resultado

| Categoria | Peso | Penalidade | Nota | Máximo |
|---|---|---|---|---|
| syntax | 30% | -0.00 | 3.00 | 3.00 |
| proposal | 20% | -0.00 | 2.00 | 2.00 |
| semantics | 20% | -0.00 | 2.00 | 2.00 |
| best_practices | 20% | -0.20 | 1.80 | 2.00 |
| readability | 10% | -0.00 | 1.00 | 1.00 |

**Nota final: 9.80 / 10**

---

## Pontos a melhorar

<!-- criterio:best_practices_3 -->
### Adicionar gateways de convergência onde os fluxos se reencontram

No seu diagrama, dois gateways divergentes — **"Resultado da triagem"** e **"Resultado da proposta"** — abrem caminhos alternativos, mas nenhum deles conta com um gateway de convergência correspondente que reúna esses caminhos antes de o processo continuar.

No gateway **"Resultado da proposta"**, o caminho "Oferta aceita" segue para "Realizar integração e treinamentos", enquanto o caminho "Oferta recusada" leva a "Selecionar outro candidato", que por sua vez retorna diretamente à tarefa "Enviar oferta ao candidato" — sem passar por um gateway de convergência. Isso torna o ponto de reunião dos fluxos implícito e ambíguo.

Em BPMN, a boa prática estabelece que todo gateway que divide o fluxo (divergente) deve ter um gateway correspondente que o una (convergente), sempre que os caminhos alternativos precisarem se juntar antes de prosseguir. Sem essa convergência explícita, quem lê o modelo não consegue identificar com clareza onde os caminhos se reencontram, o que dificulta tanto a compreensão do processo quanto sua eventual implementação ou análise.

**Como corrigir:** para o gateway "Resultado da proposta", insira um gateway de convergência do tipo XOR logo antes da tarefa "Enviar oferta ao candidato". Dessa forma, tanto o fluxo vindo de "Selecionar candidato juntamente com o RH" quanto o fluxo vindo de "Selecionar outro candidato" passarão por esse gateway antes de prosseguir para o envio da oferta. Quanto ao gateway "Resultado da triagem", o caminho "Descartado" já termina em um evento de fim ("Candidato eliminado"), portanto a convergência não se aplica a esse caso — ele está correto e não precisa de nenhum ajuste.

---

## O que você acertou

Você acertou em praticamente todos os aspectos avaliados. Veja os destaques:

- **Sintaxe e conectores:** os fluxos de sequência foram utilizados corretamente, conectando apenas elementos dentro das raias, e os gateways estão todos ligados por conectores adequados. Todas as tarefas possuem exatamente um fluxo de saída e estão integradas ao restante do processo.

- **Estrutura da piscina e das raias:** cada ator está representado em sua respectiva raia, as tarefas estão associadas a apenas uma raia, e o nome da piscina corresponde corretamente ao nome do processo.

- **Eventos:** você inseriu eventos de início e fim para cada piscina, garantiu a existência de apenas um evento inicial, e todos os eventos estão devidamente rotulados.

- **Gateways:** os desvios esperados para o processo foram modelados, cada gateway possui mais de um fluxo de saída, e os tipos de gateway estão corretos para o contexto representado.

- **Tarefas:** todas as tarefas esperadas foram modeladas, estão redigidas com verbo no infinitivo acompanhado de substantivo, apresentam descrições breves e objetivas, não utilizam siglas ou abreviações, e não há tarefas redundantes nem tarefas que representem resultados em vez de ações.

- **Proposta e semântica:** o modelo representa fielmente o processo descrito no enunciado, com os atores corretos e os elementos esperados devidamente contemplados.

---

Parabéns pelo excelente trabalho! Você demonstrou segurança no uso do BPMN e atenção aos detalhes do processo modelado. O único ajuste necessário é pontual e, uma vez corrigido, seu diagrama estará em plena conformidade com as boas práticas da notação. Continue assim — você está no caminho certo para produzir modelos de processos cada vez mais precisos e profissionais.