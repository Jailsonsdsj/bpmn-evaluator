import json
from typing import Any
from agents.contracts import *

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import Runnable, RunnableParallel, RunnablePassthrough
from langchain_core.messages import SystemMessage
from dataclasses import dataclass, asdict

def map_assessment_system_message(enunciado: str, diagram: dict[str, Any]):
    return SystemMessage(
    content=[
        {
            "type": "text",
            # TODO: colocar esse prompt em algum lugar melhor
            "text": (
                f"""Você é um professor de Gestão de Processos de Negócio. Seu dever é dar feedback sobre um diagrama BPMN apresentado por um estudante, apresentando um feedback individualizado sobre um item do checklist já corrigido.
                
                A Entrada é a seguinte:
                O enunciado da tarefa é: {enunciado}
                O diagrama apresentado pelo estudante é:\n<data>{json.dumps(diagram, ensure_ascii=False)}</data>
                
                A saída deve ser: um feedback que aponta onde o erro está no diagrama, e como o estudante poderia ter feito.
                """
            ),
            "cache_control": {"type": "ephemeral"} 
        }
    ]
)
# TODO: Type temporarily BPMNEvidence until agent 2 is finished
def map_assessment_chain(system_message: SystemMessage, llm, assessment: BPMNEvidence) -> str:
    chain = (
        ChatPromptTemplate.from_messages([
            system_message,
            ("user", "Item com erro: {assessment_json}")
        ])
    ) | llm | StrOutputParser()
    return chain.invoke({"assessment_json": f"<data>{json.dumps(asdict(assessment), ensure_ascii=False)}</data>"})