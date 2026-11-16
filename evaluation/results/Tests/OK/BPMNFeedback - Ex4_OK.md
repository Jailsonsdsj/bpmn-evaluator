# Avaliação — Modelagem do Processo de Recrutamento e Seleção

Você entregou uma modelagem bastante sólida do processo de Recrutamento e Seleção. Seu diagrama demonstra domínio consistente dos elementos fundamentais do BPMN: os atores estão corretamente representados em raias, os eventos de início e fim estão presentes e rotulados, os gateways capturam os desvios do processo e as tarefas seguem as convenções de nomenclatura esperadas. A única ressalva identificada diz respeito a uma boa prática de modelagem relacionada à convergência de gateways, o que resultou em uma penalidade pequena. No geral, trata-se de um trabalho muito bem executado.

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
### Adicione gateways de convergência onde os fluxos se reencontram

No seu diagrama, você utilizou dois gateways de divergência — **"Resultado da triagem"** e **"Resultado da proposta"** — mas nenhum deles possui um gateway de convergência correspondente. O caso mais evidente está no gateway **"Resultado da proposta"**: o caminho *"Oferta aceita"* leva à tarefa *"Realizar integração e treinamentos"*, enquanto o caminho *"Oferta recusada"* leva a *"Selecionar outro candidato"*, que por sua vez se conecta diretamente a *"Enviar oferta ao candidato"*. Os dois caminhos se reencontram nesse ponto, mas sem que haja um gateway explícito marcando essa junção.

Em BPMN, a boa prática é que todo gateway que divide o fluxo em múltiplos caminhos tenha um gateway correspondente reunindo-os, sempre que esses caminhos convergirem para uma mesma continuação do processo. Omitir esse gateway de convergência torna o diagrama ambíguo: quem lê o modelo não consegue identificar com clareza onde os caminhos alternativos se encerram e o fluxo principal é retomado, o que pode gerar interpretações equivocadas sobre a lógica do processo.

Para corrigir, insira um gateway **XOR (exclusivo)** de convergência antes da tarefa *"Enviar oferta ao candidato"*. Faça com que tanto o caminho *"Oferta recusada → Selecionar outro candidato"* quanto o fluxo principal cheguem a esse gateway antes de seguir para o envio da oferta. Dessa forma, fica explícito que, independentemente de qual candidato foi escolhido, o processo sempre converge para a mesma etapa seguinte — tornando o diagrama mais legível e formalmente correto.

---

## O que você acertou

Você demonstrou domínio amplo das convenções BPMN ao longo de toda a modelagem. Veja os principais destaques:

- **Sintaxe e conectores:** os fluxos de sequência foram utilizados corretamente, conectando apenas elementos dentro de uma mesma piscina, e todos os gateways e tarefas estão devidamente ligados ao restante do processo, sem elementos soltos.
- **Estrutura de piscina e raias:** cada ator do processo está representado em sua própria raia, as tarefas estão associadas a apenas uma raia por vez e o nome da piscina corresponde corretamente ao processo modelado.
- **Eventos:** há exatamente um evento de início por piscina, os eventos de início e fim estão presentes e rotulados, e os eventos esperados para o processo foram todos modelados.
- **Gateways:** os desvios necessários foram identificados e modelados, cada gateway possui mais de um fluxo de saída e todos estão conectados por fluxos de sequência.
- **Tarefas:** as tarefas esperadas foram contempladas, estão escritas com verbo no infinitivo acompanhado de substantivo, possuem descrições breves e objetivas, não utilizam siglas ou abreviações, representam ações (e não resultados) e não há redundâncias.
- **Legibilidade geral:** o diagrama está limpo, bem organizado e de fácil leitura.

---

Parabéns pelo excelente trabalho! Uma nota de 9,80 reflete o quanto você já internalizou as boas práticas de modelagem BPMN. O único ajuste necessário — incluir gateways de convergência — é um detalhe refinado que, uma vez incorporado ao seu repertório, elevará ainda mais a qualidade dos seus diagramas. Continue com essa atenção e rigor; você está no caminho certo.