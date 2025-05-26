# *************** IMPORT LIBRARY ***************
import json
from typing import TypedDict, Literal, List

from langchain_core.tools import tool
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence
from pydantic import BaseModel, Field
from langchain_community.callbacks import get_openai_callback

from langgraph.graph import END, START, StateGraph

from models.llms import LLMModels

from setup import LOGGER

# *************** GRAPH STATE ***************
class State(TypedDict):
    user_prompt: str
    form_description: str
    form_steps: str
    step_questions: str
    final_form: str

# *************** QUESTIONS SCHEMA ***************
class QuestionItem(BaseModel):
    question_text: str
    question_type: Literal[
        "date", "time", "duration", "email",
        "short_text", "text_area_long",
        "multiple_choice_dropdown_menu", "dropdown_single_option",
        "multiple_option", "single_option", "slider_rating",
        "upload_document"
    ]
    question_description: str
    question_example: str

class QuestionsOutput(BaseModel):
    questions: List[QuestionItem]

# *************** EVALUATOR SCHEMA ***************
class EvaluationFeedback(BaseModel):
    grade: Literal["acceptable", "unacceptable"] = Field(description="Whether the generated content is acceptable")
    feedback: str = Field(description="Suggestions or comments on how to improve the generation")


# *************** TOOL FUNCTIONS ***************
@tool
def generate_description(prompt: str) -> str:
    """Generate a form description from a user prompt"""
    return LLMModels().nano.invoke(f"You are a form builder. Write a concise form description for: '{prompt}'").content


@tool
def generate_steps(prompt: str) -> str:
    """Generate steps of a form from a prompt"""
    return LLMModels().nano.invoke(f"Create steps to structure a form for: '{prompt}'. Write clearly and label each step.").content


@tool
def generate_questions(prompt: str) -> str:
    """Generate detailed questions based on a form prompt"""

    question_prompt = PromptTemplate.from_template("""
You are a form builder. Based on the prompt below, generate a list of form questions.

Prompt:
{prompt}

Output a JSON object with a single key "questions", containing a list of questions.
Each question must have:
- question_text
- question_type (choose ONLY from: date, time, duration, email, short_text, text_area_long, multiple_choice_dropdown_menu, dropdown_single_option, multiple_option, single_option, slider_rating, upload_document)
- question_description
- question_example

Ensure type names match exactly and output is valid JSON.
""")

    question_parser = JsonOutputParser(pydantic_object=QuestionsOutput)

    generate_questions_chain: RunnableSequence = question_prompt | LLMModels().nano | question_parser

    return generate_questions_chain.invoke({"prompt": prompt})

def evaluate_generated_output(prompt: str, content: str, component: str) -> dict:
    """Evaluate the generated description/steps/questions"""
    eval_prompt = f"""
You are an evaluator AI. The following was generated for a form builder task.
Component: {component}

User Prompt:
{prompt}

Generated Content:
{content}

Please assess whether this content is acceptable for final form generation.
""" 
    evaluator = LLMModels().nano.with_structured_output(EvaluationFeedback)
    result = evaluator.invoke(eval_prompt)
    return {"grade": result.grade, "feedback": result.feedback}


# *************** AGGREGATOR FINAL FORM GENERATOR ***************
def generate_final_form(state: State) -> dict:
    """
    Combines description, steps, and questions using LLM to generate structured form JSON.
    """
    prompt = f"""
You are a form builder AI. Based on the following:

Generate a concise description of a form based on the input.
Input:

User Input:
{state.get('user_prompt')}

Form Description:
{state['form_description']}

Steps (raw):
{state['form_steps']}

Questions (raw):
{state['step_questions']}

Generate a structured form JSON like:
{{
  "form_title": "...",
  "description": "...",
  "steps": [
    {{
      "step_name": "...",
      "step_description": "...",
      "step_questions": [
        {{
          "question_text": "...",
          "question_type": "...",
          "question_description": "...",
          "question_example": "..."
        }}
      ]
    }}
  ]
}}

Respond ONLY in valid JSON format. Ensure it's parsable.
"""
    final_result = LLMModels().nano.invoke(prompt)
    return {"final_form": final_result.content}

def intilize_form_node(graph: StateGraph):
    
    # Add nodes
    graph.add_node("generate_description", lambda state: {
        "form_description": generate_description(state["user_prompt"])
    })
    graph.add_node("generate_steps", lambda state: {
        "form_steps": generate_steps(state["user_prompt"])
    })
    graph.add_node("generate_questions", lambda state: {
        "step_questions": generate_questions(state["user_prompt"])
    })

    # Evaluators
    graph.add_node("evaluate_description", lambda state: evaluate_generated_output(state["user_prompt"], state["form_description"], "description"))
    graph.add_node("evaluate_steps", lambda state: evaluate_generated_output(state["user_prompt"], state["form_steps"], "steps"))
    graph.add_node("evaluate_questions", lambda state: evaluate_generated_output(state["user_prompt"], state["step_questions"], "questions"))

    # Final aggregator
    graph.add_node("generate_final_form", generate_final_form)

def agent_flow_form(graph: StateGraph):

    # Edges
    # Generation
    graph.add_edge(START, "generate_description")
    graph.add_edge(START, "generate_steps")
    graph.add_edge(START, "generate_questions")
    # Evaluation
    graph.add_edge("generate_description", "evaluate_description")
    graph.add_edge("generate_steps", "evaluate_steps")
    graph.add_edge("generate_questions", "evaluate_questions")
    # Final Form Generation
    # Assume all evaluations pass — can later add logic to loop back for optimization
    graph.add_edge("evaluate_description", "generate_final_form")
    graph.add_edge("evaluate_steps", "generate_final_form")
    graph.add_edge("evaluate_questions", "generate_final_form")
    graph.add_edge("generate_final_form", END)

def agent_form_builder():
    # *************** BUILD GRAPH ***************
    graph = StateGraph(State)

    intilize_form_node(graph)

    agent_flow_form(graph)

    # Compile the workflow
    workflow = graph.compile()

    return workflow

def convert_json(string_json: str) -> dict[str, list[dict]]:

    converted = json.loads(string_json.replace("```json", '').replace('```', ''))

    return converted


def run_agent_form(user_input: str) -> dict[str, list[dict]]:

    agent_form = agent_form_builder()

    with get_openai_callback() as cb:
        form_result = agent_form.invoke({"user_prompt": user_input})

    if form_result.get('final_form') and isinstance(form_result['final_form'], str):

        final_form = convert_json(form_result.get('final_form'))
    else:
        final_form = form_result['final_form']

    LOGGER.info(f"Form Generated {final_form.keys() if isinstance(final_form, dict) else {'type': f'{final_form}'}} \n{cb}")

    return final_form

