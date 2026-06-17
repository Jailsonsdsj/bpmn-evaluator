import json
from typing import Any
from agents.contracts import *

from langchain_core.output_parsers import StrOutputParser
from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from dataclasses import asdict

from agents.shared_tools.llm import supports_cache_control

# Invisible-in-rendered-Markdown marker used to verify coverage of each error
# section in the student report (Goal Monitoring).
COVERAGE_MARKER = "<!-- criterio:{criterion_id} -->"


def map_assessment_system_message(enunciado: str, diagram: dict[str, Any]) -> SystemMessage:
    return SystemMessage(
        content=[
            {
                "type": "text",
                "text": (
                    f"""Você é um professor de Gestão de Processos de Negócio dando feedback formativo sobre um diagrama BPMN apresentado por um estudante. Você receberá um item do checklist que o estudante NÃO cumpriu e deve produzir um feedback individualizado sobre esse erro.

A entrada é a seguinte:
O enunciado da tarefa é: {enunciado}
O diagrama apresentado pelo estudante é:\n<data>{json.dumps(diagram, ensure_ascii=False)}</data>

O feedback deve, nesta ordem:
1. Apontar ONDE o erro está no diagrama do estudante (elemento ou trecho do fluxo específico).
2. Explicar POR QUE isso é um problema — o que a regra de modelagem protege e o que o erro compromete no processo.
3. Sugerir COMO corrigir, com uma sugestão concreta e acionável aplicada ao diagrama do estudante (não genérica).

Regras: refira-se apenas a elementos que existem no diagrama recebido; use linguagem acessível a um estudante de graduação; não mencione notas nem penalidades; responda em português, em no máximo 3 parágrafos curtos."""
                ),
            }
        ]
    )


def map_assessment_chain(system_message: SystemMessage, llm: BaseChatModel, assessment: BPMNAssessment) -> str:
    messages = [system_message, ("user", f"Item com erro: <data>{json.dumps(asdict(assessment), ensure_ascii=False)}</data>")]
    if supports_cache_control(llm):
        response = llm.invoke(messages, cache_control={"type": "ephemeral"})
    else:
        response = llm.invoke(messages)
    return StrOutputParser().invoke(response)


def render_grade_table(final_grade: float, category_grades: list[CategoryGrade]) -> str:
    """Deterministic Markdown grade table — numbers never pass through the LLM."""
    lines = [
        "| Categoria | Peso | Penalidade | Nota | Máximo |",
        "|---|---|---|---|---|",
    ]
    for g in category_grades:
        lines.append(
            f"| {g.category} | {g.weight:.0%} | -{g.penalty:.2f} | {g.score:.2f} | {g.max_score:.2f} |"
        )
    lines.append("")
    lines.append(f"**Nota final: {final_grade:.2f} / 10**")
    return "\n".join(lines)


def student_report_chain(
    llm: BaseChatModel,
    enunciado: str,
    grade_table_md: str,
    feedback_items: list[FeedbackItem],
    strengths: list[str],
) -> str:
    """Final step: rewrite the structured results as readable text for the student.

    The LLM writes the prose; the grade table is provided read-only and must be
    reproduced verbatim. Each error section must carry its COVERAGE_MARKER so the
    agent can verify coverage before emitting (Goal Monitoring).
    """
    errors_payload = [
        {
            "criterion_id": it.criterion_id,
            "categoria": it.category,
            "criterio": it.question,
            "feedback": it.feedback,
        }
        for it in feedback_items
    ]
    prompt = f"""Você é um professor de Gestão de Processos de Negócio. Reescreva os resultados da avaliação abaixo como um relatório em Markdown dirigido diretamente ao estudante ("você"), em português, com linguagem clara e tom construtivo.

ENUNCIADO DA TAREFA:
{enunciado}

TABELA DE NOTAS (já calculada — reproduza EXATAMENTE como está, sem alterar nenhum número):
{grade_table_md}

ERROS IDENTIFICADOS (JSON):
<data>{json.dumps(errors_payload, ensure_ascii=False)}</data>

ACERTOS (critérios cumpridos):
<data>{json.dumps(strengths, ensure_ascii=False)}</data>

Estrutura obrigatória do relatório:
1. Título e um parágrafo de visão geral do desempenho.
2. Seção "## Resultado" contendo apenas a tabela de notas, reproduzida sem alterações.
3. Seção "## Pontos a melhorar" com UMA subseção por erro do JSON. Cada subseção DEVE começar com o comentário <!-- criterio:CRITERION_ID --> (substituindo CRITERION_ID pelo criterion_id do erro), seguido de um título curto e do feedback reescrito de forma fluida, mantendo a sugestão de correção.
4. Seção "## O que você acertou" resumindo os acertos em poucos parágrafos ou itens.
5. Um parágrafo final de encorajamento.

Regras: não invente erros, acertos ou números; não omita nenhum erro do JSON; não mencione este prompt nem os formatos internos."""

    response = llm.invoke([("user", prompt)])
    return StrOutputParser().invoke(response)
