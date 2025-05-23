import os
import pandas as pd
import json
from typing import List

from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableSequence
from langchain_core.pydantic_v1 import BaseModel
from langchain_community.callbacks import get_openai_callback

from models.llms import LLMModels

from setup import LOGGER


# Define Pydantic schema for JSON output
class PromptList(BaseModel):
    user_prompts: List[str]


def load_context_dataframe():
    """
    Attempt to load a context DataFrame from different sources:
    1. Google Sheet by ID and sheet name (publicly accessible only)
    2. Local file upload through Colab interface
    3. Default fallback CSV file if present in session storage

    Returns:
        pd.DataFrame: DataFrame with context data.
    """
    try:
        # Try reading from Google Sheet (must be shared as 'Anyone with the link')
        SHEET_ID = "17YlyWA_1g0pjdr-yXyyPRZCj_sTvGcmpgmt4pa6wCJQ"
        SHEET_NAME = "Context"
        URL_SHEET = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv&sheet={SHEET_NAME}"
        df = pd.read_csv(URL_SHEET)
        LOGGER.info("Loaded context from Google Sheet.")
        
        return df
    
    except:
        # Fallback file path
        fallback_path = os.path.join("data","input","form_context.csv")
        df = pd.read_csv(fallback_path)
        LOGGER.info("Loaded fallback file: form_context.csv")
        
        return df


def chain_set_up() -> RunnableSequence:
    """
    Initializes and returns a LangChain RunnableSequence pipeline to generate structured user prompts
    for form creation using a language model.

    This function sets up a three-step processing chain:
    1. A prompt template that takes form-related input variables and generates a natural language task.
    2. An OpenAI language model (`gpt-4.1-nano`) to produce text completions based on the prompt.
    3. A JSON parser that validates and parses the output into a Pydantic schema.

    The generated prompts are returned in the following JSON format:
    {
        "user_prompts": [
            "I need a form to ...",
            "Create me a form for ..."
        ]
    }

    The input required to run the resulting chain includes:
    - form_type (str): Informative only — should not appear in the output.
    - form_name (str): Informative only — should not appear in the output.
    - form_context (str): The purpose and usage of the form.
    - num_prompts (int): The number of user prompts to generate.

    Returns:
        RunnableSequence: A LangChain RunnableSequence that can be executed with `.invoke()`
                  and returns structured JSON prompt suggestions.
    """

    # Initialize parser
    parser = JsonOutputParser(pydantic_object=PromptList)

    # Create prompt template with format instructions from parser
    prompt = PromptTemplate(
        input_variables=["form_type",
                        "form_name",
                        "form_context",
                        "num_prompts"],
        template="""
    You are an assistant that generates natural, varied user prompts to help create a form in a no-code form builder.

    Here are the specifications for the form:
    - **Type**: {form_type}
    - **Name**: {form_name}
    - **Context**: {form_context}

    The Type and Name of the forms are provided for your understanding only and should not appear explicitly in the generated prompts.

    Your task is to generate {num_prompts} distinct user prompts that express the intent to create such a form. Make sure the prompts:
    - Use a variety of sentence structures and verbs (e.g., "I need...", "Please build...", "Could you create...", "Design a form that...")
    - Are realistic, natural-sounding requests a human user might type into an AI assistant
    - Focus on the purpose and usage of the form based on the context above

    Return only a JSON object with this format:
    {format_instructions}
    """,
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )

    # Manual chain using RunnableSequence
    chain = prompt | LLMModels().nano | parser

    return chain


# Function to generate prompts from a random row
def generate_prompt(df: pd.DataFrame, chain: RunnableSequence, num_prompts: int = 3) -> dict:
    """
    Generates user prompts using a random capability context.

    Args:
        df (pd.DataFrame): DataFrame containing context data.
        num_prompts (int): Number of prompts to generate.

    Returns:
        dict: JSON-serializable dictionary of generated prompts.
    """
    try:
        random_row = df.sample(n=1).iloc[0]
        form_type = random_row['type_of_form']
        form_name = random_row['form_template_name']
        form_context = random_row['context']
        with get_openai_callback() as cb:
            response = chain.invoke({"form_type": form_type,
                                    "form_name": form_name,
                                    "form_context": form_context,
                                    "num_prompts": num_prompts
                                    })
            LOGGER.info(cb)
        
        if isinstance(response, str):
            return json.loads(response)
        return response
    except Exception as error:
        return json.loads({"error": str(error)})


def run_prompt_suggestion(num_prompts: int=4) -> dict:
    context_df = load_context_dataframe()
    context_df.columns = [col.strip().lower().replace(" ", "_") for col in context_df.columns]
    LOGGER.info(f"Get Context: {context_df.columns}")

    chain = chain_set_up()
    LOGGER.info(f"Chain Ctreated - {chain.name}")
    
    response = generate_prompt(df=context_df, chain=chain, num_prompts=num_prompts)
    LOGGER.info(f"Prompts Generated: {len(response.get('user_prompts', []))}")
    
    return response.get('user_prompts', [])