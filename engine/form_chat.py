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


def question_suggester(state: FormAssistantState) -> FormAssistantState:
    # Example LLM logic
    result = LLMModels().nano.invoke(f"Suggest new questions for this form:\n{state['form']}")
    state["suggested_questions"] = result.json()
    print("question_suggester: ", state.get("suggested_questions", "None"))
    return state

def command_suggester(state: FormAssistantState) -> FormAssistantState:
    result = LLMModels().nano.invoke(f"Suggest commands to edit the form:\n{state['form']}")
    state["suggested_commands"] = result.json()
    print("command_suggester: ", state.get("suggested_commands", "None"))
    return state

def template_retriever(state: FormAssistantState) -> FormAssistantState:
    # You can add vector-based retrieval here
    retriever = init_astradb_retriever()
    state["retrieved_templates"] = retriever(state["user_input"])
    print("template_retriever: ", state.get('retrieved_templates', "None"))
    return state

def context_extractor(state: FormAssistantState) -> FormAssistantState:
    # Optional: Parse form into structured metadata
    state["form_structure"] = f"Current Form Generated {state['form']}"
    print("context_extractor: ", state.get("form_structure", "None"))
    return state

def llm_response_generator(state: FormAssistantState) -> FormAssistantState:
    result = LLMModels().nano.invoke(f"""
    You are a form assistant. Based on:
    - Prompt: {state['original_prompt']}
    - Form: {state['form']}
    - Analysis: {state.get('analysis')}
    - Suggestions: {state.get('suggested_questions') or state.get('suggested_commands')}
    - Templates: {state.get('retrieved_templates')}
    - User input: {state['user_input']}
    
    Reply with a user-facing message.
    """)
    state["messages"].append({"role": "assistant", "content": result.content})
    print("llm_response_generator: ", state.get("messages", "None"))
    return state


def input_analyzer(state: FormAssistantState) -> FormAssistantState:
    
    # *************** Output Parser ***************
    output_parser = PydanticOutputParser(pydantic_object=InputAnalysis)

    # *************** Prompt Template ***************
    prompt = PromptTemplate.from_template(
        """
    You are a form assistant analyzing user input.

    Given the user input:
    {user_input}

    And the current form:
    {form}

    Determine what the user is trying to do. Respond ONLY in JSON format as:

    {format_instructions}
    """
    )
    # Format the prompt with structured output
    formatted_prompt = prompt.format_prompt(
        user_input=state["user_input"],
        form=state["form"],
        format_instructions=output_parser.get_format_instructions()
    )

    # Call LLM and parse response
    raw_response = LLMModels().nano.invoke(formatted_prompt.to_string())
    try:
        parsed = output_parser.parse(raw_response.content)
        state["analysis"] = parsed.model_dump()
    except Exception as e:
        print("Parser Error:", e)
        state["analysis"] = {"intent": "unclear", "reason": "Could not parse response properly."}

    print("input_analyzer:", state["analysis"])
    return state


def suggestion_condition(state: FormAssistantState) -> str:
    intent = state["analysis"]["intent"]
    print("suggestion_condition: ", intent)
    if intent == "suggest_questions":
        return "question_suggester"
    elif intent == "suggest_command":
        return "command_suggester"
    elif intent == "unclear":
        return "template_retriever"
    else:
        return "context_extractor"

def chatbot(state: FormAssistantState) -> FormAssistantState:
    if not state.get("original_prompt"):
        state["original_prompt"] = state["user_input"]
    print("chatbot: ", state.get("messages", "None"))
    return state


def build_chat():
    builder = StateGraph(FormAssistantState)

    # Core nodes
    builder.add_node("chatbot", chatbot)  # receives initial user_input
    builder.add_node("input_analyzer", input_analyzer)
    builder.add_node("question_suggester", question_suggester)
    builder.add_node("command_suggester", command_suggester)
    builder.add_node("template_retriever", template_retriever)
    builder.add_node("context_extractor", context_extractor)
    builder.add_node("llm_response", llm_response_generator)
    # builder.add_node("suggestion_condition", suggestion_condition)

    # Edges
    builder.set_entry_point("chatbot")
    builder.add_edge("chatbot", "input_analyzer")
    builder.add_conditional_edges(
        "input_analyzer",
        suggestion_condition,
        path_map={
            "question_suggester": "question_suggester",
            "command_suggester": "command_suggester",
            "template_retriever": "template_retriever",
            "context_extractor": "context_extractor"
        }
    )

    # Continue flow to context_extractor then response
    builder.add_edge("question_suggester", "context_extractor")
    builder.add_edge("command_suggester", "context_extractor")
    builder.add_edge("template_retriever", "context_extractor")
    builder.add_edge("context_extractor", "llm_response")

    builder.set_finish_point("llm_response")

    return builder.compile()
