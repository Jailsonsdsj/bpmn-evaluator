import json
from typing import Any
from agents.contracts import *

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, JsonOutputParser
from langchain_core.runnables import Runnable, RunnableParallel, RunnablePassthrough
from langchain_core.messages import SystemMessage
from langchain_core.language_models import BaseChatModel
from dataclasses import dataclass, asdict

from agents.shared_tools.llm import supports_cache_control

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
                
                IMPORTANTE: Mantenha o feedback BREVE e OBJETIVO (máximo 2-3 linhas). Não repita o critério.
                """
            ),
            # "cache_control": {"type": "ephemeral"} 
        }
    ]
)

def map_assessment_chain(system_message: SystemMessage, llm: BaseChatModel, assessment: BPMNAssessment) -> str:
    """Generate feedback for a single failed criterion via LLM.
    
    Args:
        system_message: System message with context
        llm: Chat model instance
        assessment: Single criterion assessment
    
    Returns:
        str: Personalized feedback (brief, 2-3 lines max)
    
    Raises:
        RuntimeError: If LLM call fails or times out
    """
    # Build messages with full context
    messages = [
        system_message, 
        ("user", f"Item com erro:\nCritério: {assessment.question}\nObservação: {assessment.justification}\n")
    ]
    
    try:
        # Invoke LLM with timeout (if supported by the model)
        if supports_cache_control(llm):
            response = llm.invoke(messages, cache_control={"type": "ephemeral"})
        else:
            response = llm.invoke(messages)
        
        # Extract text from response
        feedback = StrOutputParser().invoke(response)
        
        # Ensure feedback is not empty
        if not feedback or not feedback.strip():
            raise ValueError("LLM returned empty feedback")
        
        # Limit feedback length (prevent excessive verbosity)
        if len(feedback) > 500:
            feedback = feedback[:500] + "..."
        
        return feedback.strip()
    
    except Exception as exc:
        # Log error but don't crash - return empty string for caller to handle
        raise RuntimeError(f"Failed to generate feedback: {str(exc)}") from exc