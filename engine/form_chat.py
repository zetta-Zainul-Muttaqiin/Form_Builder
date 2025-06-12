# *************** ENHANCED FORM ASSISTANT - AGENTIC AI ***************
import os
import json
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Annotated, List, Optional, Literal, Dict, Any, TypedDict

from langchain.prompts import PromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain.tools import BaseTool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver

from models.llms import LLMModels
from engine.rag_engine import init_astradb_retriever
from engine.form_builder import generate_questions
from setup import LOGGER


class FormAssistantState(TypedDict, total=False):
    form: dict
    form_id: str
    user_input: str
    messages: Annotated[List[dict], add_messages]

    # Core metadata
    original_prompt: Optional[str]
    conversation_context: Optional[dict]
    
    # LLM Analysis
    analysis: Optional[dict]
    form_structure: Optional[str]
    retrieved_templates: Optional[str]
    
    # Suggestion & Edit Flow
    suggested_edit_message: Optional[str]
    suggested_questions: Optional[List[dict]]

    # Confirmation Flow
    needs_confirmation: bool
    confirmation_checked: bool
    confirm_edit: bool
    form_already_edited: bool

    # Error Handling & UX
    preview_mode: bool
    retry_count: int
    errors: List[str]
    warnings: List[str]


class InputAnalysis(BaseModel):
    """
    Analyzes user input to determine their intent in the form assistant system.
    """
    intent: Literal["edit", "suggest_questions", "unclear"] = Field(
        description="User's main intent: 'edit' for changes, 'suggest_questions' for question ideas, or 'unclear' if ambiguous"
    )
    reason: str = Field(
        description="Explanation of why the assistant interpreted the input as that intent."
    )


def get_message_history_str(messages: list) -> str:
    if messages:
        return "\n".join([f"{msg.type.capitalize()}: {msg.content.strip()}" for msg in messages[-6:]])
    return []


# *************** ANALYZE INPUT INTENT ***************
def input_analyzer(state: FormAssistantState) -> FormAssistantState:
    output_parser = PydanticOutputParser(pydantic_object=InputAnalysis)
    prompt = PromptTemplate.from_template("""
You are a form assistant analyzing user input.

Chat history:
{messages}

Input: {user_input}
Form: {form}

Return JSON:
{format_instructions}
""")

    formatted = prompt.format_prompt(
        user_input=state["user_input"],
        form=state["form_structure"],
        messages=get_message_history_str(state.get('messages', [])),
        format_instructions=output_parser.get_format_instructions()
    )

    try:
        raw = LLMModels().nano.invoke(formatted.to_string())
        state["analysis"] = output_parser.parse(raw.content).model_dump()
    except Exception as e:
        LOGGER.error(f"input_analyzer error: {e}")
        state["analysis"] = {"intent": "unclear", "reason": "Failed to parse intent"}

    return state

def context_extractor(state: FormAssistantState) -> FormAssistantState:
    # Optional: Parse form into structured metadata
    path = os.path.join('data', 'form_builder', f"{state['form_id']}.json")
    state['form'] = read_json(path)
    state["form_structure"] = f"Current Form Generated {state['form']}"
    
    LOGGER.info("[Tools]: Read Context")
    return state

# *************** EDIT OR SUGGEST TOOLS ***************
def edit_suggester(state: FormAssistantState) -> FormAssistantState:

    recently_questions_suggest = state.get('suggested_questions', [])
    chat = get_message_history_str(state.get("messages", []))
    result = LLMModels().nano.invoke(f"""
    You are a form assistant. User said: "{state['user_input']}"
    Conversation history:
    {chat}

    Form: {state['form']}

    you can applied from this suggestion(if any):
    {recently_questions_suggest}

    Reply with edit summary in friendly text (no JSON, no full form).
    """)
    state["suggested_edit_message"] = result.content
    state["needs_confirmation"] = True
    LOGGER.info("[Tools]: Giving edit suggesting")
    return state


def question_suggester(state: FormAssistantState) -> FormAssistantState:
    try:
        result = generate_questions(state["user_input"])
        state["suggested_questions"] = result["questions"]
    except Exception as e:
        LOGGER.error(f"question_suggester error: {e}")
        state["suggested_questions"] = []
    LOGGER.info(f"[Tools]: Generate Question suggest {state['suggested_questions']}")
    return state


# *************** CONFIRMATION + EDIT EXECUTION ***************
def confirmation_handler(state: FormAssistantState) -> FormAssistantState:
    """
    Determines if the user has confirmed an edit suggestion.
    """
    confirm_prompt = PromptTemplate.from_template("""
    You are a confirmation agent in a Form Assistance workflow.

    User was shown this edit suggestion:
    "{edit_message}"

    They responded with:
    "{user_input}"
    
    Conversation history:
    {chat}

    Based on the response, classify the intent:
    - Return "yes" if the user confirms the edit or says to proceed.
    - Return "no" if they reject or decline.
    - Return "unknown" if the response is unclear or unrelated.
        
    Respond ONLY with: "yes", "no", or "unknown".
    """)

    formatted_prompt = confirm_prompt.format_prompt(
        edit_message=state.get("suggested_edit_message", ""),
        user_input=state.get("user_input", ""),
        chat=get_message_history_str(state.get("messages", []))
    )

    result = LLMModels().nano.invoke(formatted_prompt.to_string())
    intent = result.content.strip().lower()

    state["confirm_edit"] = intent == "yes"
    state["confirmation_checked"] = True
    LOGGER.info(f"[Tools]: Confirmation Handler = {intent}")
    return state



def form_editor(state: FormAssistantState) -> FormAssistantState:
    """
    Applies the requested form edit based on the confirmed user input.
    """

    form_editor_prompt = PromptTemplate.from_template("""
    You are a form editing agent.

    Here is the current form JSON:
    {form_json}

    The user made the following request:
    "{user_input}"
    
    Conversation history:
    {chat}
    
    Apply the necessary changes to the form based on that input.
    ONLY return updated form in valid JSON format (no explanation, no markdown).
    """)

    try:
        formatted_prompt = form_editor_prompt.format_prompt(
            form_json=json.dumps(state["form"], indent=2),
            user_input=state["user_input"],
            chat = get_message_history_str(state.get("messages", []))
        )
        result = LLMModels().nano.invoke(formatted_prompt.to_string())
        state["form"] = json.loads(result.content)
        file_path = os.path.join('data', 'form_builder', f"{state['form_id']}.json")
        write_json(file_path, state["form"])

        state["form_already_edited"] = True
    except Exception as error:
        LOGGER.error(f"[form_editor] Failed to apply changes: {error}")
    
    LOGGER.info("[Tools]: Form Updated")
    return state



# *************** FINAL RESPONSE GENERATOR FUNCTION ***************
def llm_response_generator(state: FormAssistantState) -> FormAssistantState:
    """
    Final LLM response based on form context, suggestions, and edits.
    Handles both normal and confirmation-required responses.
    """

    # Load variables from state
    user_input = state.get("user_input", "")
    form_description = state.get("form", {}).get("form_content", {}).get("description", "")
    analysis = json.dumps(state.get("analysis", {}), indent=2)
    suggestions = json.dumps(state.get("suggested_questions", []), indent=2)
    templates = state.get("retrieved_templates", "None")
    edit_message = state.get("suggested_edit_message", "")
    confirmation_needed = not state.get("confirmation_checked", False) and state.get("needs_confirmation", False)
    form_edited = state.get('form_already_edited')

    # *************** TEMPLATE FOR NORMAL RESPONSE ***************
    llm_chat_prompt = PromptTemplate.from_template("""
    You are a helpful form assistant.

    The user is trying to adjust or improve their form. Use the following context:

    User Input: {user_input}

    Conversation history:
    {chat}

    Form Description: {form_description}

    Analysis:
    {analysis}

    Suggested Questions (if any):
    {suggestions}

    Similar Template (if available):
    {templates}

    Previous Edit Suggestion (if any):
    {edit_message}

    Based on this, write a friendly, helpful, and clear response. Be conversational and brief.
    """)

    # *************** TEMPLATE FOR CONFIRMATION FLOW ***************
    llm_confirm_prompt = PromptTemplate.from_template("""
    You are a form assistant.

    You proposed this edit:
    "{edit_message}"
    
    Conversation history:
    {chat}

    Ask the user politely: "Do you want to apply this change?".
    Only include the edit summary and the question.
    """)

    llm_edited_prompt = PromptTemplate.from_template("""
    You are a form assistant.

    The user requested an edit to the form:
    "{user_input}"
                                                     
    Conversation history:
    {chat}

    The form has been successfully updated based on this request.

    Summarize what change was applied. Be brief, helpful, and confirm the update.

    Then offer to help further with a follow-up like:
    "Let me know if you'd like to change anything else!"
    """)
    chat = get_message_history_str(state.get("messages", []))
    # Select prompt based on the case
    if form_edited:
        LOGGER.info("Case: Edited")
        formatted = llm_edited_prompt.format_prompt(user_input=user_input, chat=chat)
        state['form_already_edited'] = False
    
    elif edit_message and confirmation_needed:
        LOGGER.info("Case: Confirm")
        formatted = llm_confirm_prompt.format_prompt(edit_message=edit_message.strip(), chat=chat)
        state['confirmation_checked'] = False
        state['needs_confirmation'] = False
    
    else:
        LOGGER.info("Case: Conversation")
        formatted = llm_chat_prompt.format_prompt(
            user_input=user_input,
            form_description=form_description,
            analysis=analysis,
            suggestions=suggestions,
            templates=templates,
            edit_message=edit_message, 
            chat=chat
        )

    # Invoke LLM
    result = LLMModels().nano.invoke(formatted.to_string())
    response = result.content.strip()

    # Append response to chat memory
    state["messages"].append({
        "role": "assistant",
        "content": response
    })

    return state


# *************** GRAPH BUILDER ***************
def build_form_assistant():
    """Build the direct form assistant graph (no confirmation flow)"""
    
    builder = StateGraph(FormAssistantState)

    builder.add_node("get_form_context", context_extractor)
    builder.add_node("input_analyzer", input_analyzer)
    builder.add_node("edit_suggester", edit_suggester)
    builder.add_node("question_suggester", question_suggester)
    builder.add_node("confirmation_handler", confirmation_handler)
    builder.add_node("form_editor", form_editor)
    builder.add_node("llm_response", llm_response_generator)

    builder.set_entry_point("get_form_context")
    builder.add_edge("get_form_context", "input_analyzer")

    builder.add_conditional_edges(
        "input_analyzer",
        lambda state: "edit" if state["analysis"]["intent"] == "edit" else "question",
        path_map={
            "edit": "edit_suggester",
            "question": "question_suggester"
        }
    )

    builder.add_conditional_edges(
        "edit_suggester",
        lambda state: "confirm" if state.get("needs_confirmation") else "respond",
        path_map={
            "confirm": "confirmation_handler",
            "respond": "llm_response"
        }
    )

    builder.add_edge("question_suggester", "llm_response")

    builder.add_conditional_edges(
        "confirmation_handler",
        lambda state: "apply" if state.get("confirm_edit") else "respond",
        path_map={
            "apply": "form_editor",
            "respond": "llm_response"
        }
    )

    builder.add_edge("form_editor", "llm_response")

    builder.set_finish_point("llm_response")
    return builder.compile()

# *************** MAIN EXECUTION FUNCTION ***************
def run_form_assist(user_input: str, form_id: str, session_id: str = None, messages: List[dict] = None) -> Dict[str, Any]:
    """
    Enhanced form assistant with agentic capabilities
    
    Args:
        user_input: User's message
        form_id: ID of the form to work with
        session_id: Optional session ID for conversation persistence
        messages: Optional conversation history
    
    Returns:
        Dict with assistant response and metadata
    """
    
    if messages is None:
        messages = []
    
    if session_id is None:
        session_id = f"session_{form_id}"
    
    # Build the enhanced graph
    graph = build_form_assistant()
    with open('graph.png', 'wb') as f:
        f.write(graph.get_graph().draw_mermaid_png())
    
    # Prepare initial state
    initial_state = {
        "user_input": user_input,
        "form_id": form_id,
        "session_id": session_id,
        "messages": messages,
        "conversation_history": messages,
        "retry_count": 0,
        "errors": [],
        "warnings": [],
        "preview_mode": False
    }
    
    # Execute the graph
    try:
        result = graph.invoke(
            initial_state,
            config={"configurable": {"thread_id": session_id}}
        )
        LOGGER.info(f"Key R: {result.keys()}")
        for key_res in result.keys():
            if result.get(key_res):
                res_str = f"{result[key_res]}"
                LOGGER.info(f"{key_res, res_str[:100]}")

        # Extract response
        assistant_messages = [msg for msg in result["messages"]]
        latest_response = assistant_messages[-1].content if assistant_messages else "I'm sorry, I couldn't generate a response."
        
        # Prepare conversation history
        new_messages = [
            {"role": "user", "content": user_input},
            {"role": "assistant", "content": latest_response}
        ]
        
        return {
            "answer": latest_response,
            "new_history": new_messages,
            "session_id": session_id,
            "form_updated": bool(result.get("form_already_edited")),
            "validation_result": result.get("validation_result"),
            "errors": result.get("errors", []),
            "warnings": result.get("warnings", []),
            "intent": result.get("conversation_context", {}).get("intent"),
            "confidence": result.get("conversation_context", {}).get("confidence", 0.0)
        }
        
    except Exception as e:
        LOGGER.error(f"Enhanced form assistant failed: {e}")
        return {
            "answer": f"I apologize, but I encountered an error: {str(e)}. Please try again.",
            "new_history": messages + [
                {"role": "user", "content": user_input},
                {"role": "assistant", "content": f"Error: {str(e)}"}
            ],
            "session_id": session_id,
            "form_updated": False,
            "errors": [str(e)]
        }


# read JSON file
def read_json(path: str) -> dict:

    with open(path, 'r') as json_file:
        return json.load(json_file)
    
def write_json(file_path, json_input):
    with open(file_path, 'w') as file:
        json.dump(json_input, file, indent=4)


