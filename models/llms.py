# *************** IMPORT FRAMEWORK *************** 
from langchain_openai import ChatOpenAI
from openai import OpenAI
from setup import OPENAI_API_KEY

# *************** Class for Initializing OpenAI LLM Models
class LLMModels:
    """
    A class for initializing and managing OpenAI-based Large Language Models (LLMs).

    Features:
        - Initializes an OpenAI GPT-4o-mini model for processing CV-related tasks.
        - Configures model parameters such as temperature, token limit, and API key.

    Attributes:
        llm_cv (ChatOpenAI): An instance of OpenAI's ChatOpenAI model configured for CV-related tasks.

    Methods:
        create_llm_cv() -> ChatOpenAI:
            Creates and returns an instance of the OpenAI GPT-4o-mini model.
    """

    def __init__(self):
        """
        Initializes the LLMModels class and sets up the OpenAI model for CV processing.
        """
        self.nano = self.nano()
    
    # *************** Define a function for initializing OpenAI LLM
    def nano(self) -> ChatOpenAI:
        """
        Creates and configures an instance of OpenAI's GPT-4o-mini model.

        Returns:
            ChatOpenAI: An instance of the OpenAI model with the specified configuration.

        Configuration:
            - Model: "gpt-4o-mini"
            - Temperature: 1 (high variability in responses)
            - Max Tokens: 4096
            - API Key: Uses predefined `OPENAI_API_KEY`
        """
        llm_model = ChatOpenAI(
            temperature=1,
            max_tokens=4096,
            model="gpt-4.1-nano",
            api_key=OPENAI_API_KEY, 
        )

        return llm_model