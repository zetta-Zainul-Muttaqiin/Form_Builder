# *************** IMPORT LIBRARY ***************

from pydantic           import BaseModel, Field
from typing             import Annotated, List, Optional, Literal
from typing_extensions  import TypedDict


from langchain.prompts          import PromptTemplate
from langchain.output_parsers   import PydanticOutputParser
from langgraph.graph            import StateGraph, START, END
from langgraph.graph.message    import add_messages
from langgraph.prebuilt         import ToolNode, tools_condition

from models.llms                import LLMModels

from engine.rag_engine          import init_astradb_retriever

class State(TypedDict):
    # Messages have the type "list". The `add_messages` function
    # in the annotation defines how this state key should be updated
    # (in this case, it appends messages to the list, rather than overwriting them)
    messages: Annotated[list, add_messages]
    form_content: dict


class FormAssistantState(TypedDict):
    form: dict
    original_prompt: str
    user_input: str
    messages: List[dict]
    analysis: Optional[dict]  # from input_analyzer
    suggested_questions: Optional[List[dict]]
    suggested_commands: Optional[List[str]]
    retrieved_templates: Optional[List[dict]]

class InputAnalysis(BaseModel):
    intent: Literal["edit", "suggest_questions", "suggest_command", "unclear"]
    reason: str = Field(..., description="Explanation of the detected intent")

