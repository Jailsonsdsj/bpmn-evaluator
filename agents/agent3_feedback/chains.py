import json
from typing import Any
from agents.contracts import *

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import Runnable, RunnableParallel, RunnablePassthrough
from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from dataclasses import dataclass, asdict

try:
    from langchain_anthropic import ChatAnthropic
except ImportError:
    ChatAnthropic = None
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except:
    ChatGoogleGenerativeAI = None

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
            # "cache_control": {"type": "ephemeral"} 
        }
    ]
)
def map_assessment_chain(system_message: SystemMessage, llm: BaseChatModel, assessment: BPMNAssessment) -> str:
    messages = [system_message, ("user", f"Item com erro: <data>{json.dumps(asdict(assessment), ensure_ascii=False)}</data>")]
    if type(llm) is ChatAnthropic:
        response = llm.invoke(messages, cache_control={"type": "ephemeral"})
    else:
        response = llm.invoke(messages)
    return StrOutputParser().invoke(response)