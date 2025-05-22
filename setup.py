# *************** IMPORTS ***************
import os
import logging

from dotenv import load_dotenv

# *************** CREATE LOGGER ***************
LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)
# *************** Create file handler for logging errors and above (INFO, WARNING, ERROR, CRITICAL)
file_handler = logging.FileHandler('app.log')
file_handler.setLevel(logging.INFO)
# *************** Set format for the logger
formatter = logging.Formatter('%(asctime)s [%(levelname)s] - %(message)s', '%d-%m-%Y %H:%M:%S')
file_handler.setFormatter(formatter)

# Console Handler  
console_handler = logging.StreamHandler()  
console_handler.setFormatter(formatter)  
console_handler.setLevel(logging.INFO)  

LOGGER.addHandler(file_handler)  
LOGGER.addHandler(console_handler) 

# *************** Add handler to the logger
LOGGER.addHandler(file_handler)

# *************** Suppress DEBUG logs from third-party libraries ***************
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# *************** Optional: Suppress third-party DEBUG logs
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("asyncio").setLevel(logging.WARNING)
logging.getLogger("astrapy.request_tools").setLevel(logging.WARNING)
logging.getLogger("astrapy.collection").setLevel(logging.WARNING)

# *************** GET SECRETS ENVIRONMENT ***************
# *************** load .env content in .config directory
load_dotenv(os.path.join(".env"), override=True)

# *************** Set token for openai
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_EMBEDD_API_KEY = os.getenv("EMBEDDING_API_KEY")

# *************** Set token for DataStax
ASTRADB_TOKEN_KEY=os.getenv("ASTRADB_TOOLBOX_TOKEN_KEY")
ASTRADB_API_ENDPOINT=os.getenv("ASTRADB_TOOLBOX_API_ENDPOINT")
ASTRADB_NAMESPACE_NAME=os.getenv("ASTRADB_FORM_NAMESPACE_NAME")
ASTRADB_COLLECTION_NAME=os.getenv("ASTRADB_COLLECTION_NAME")


QUESTION_TYPES = [
    "date", "time", "duration", "email", "text_area_short", "text_area_long",
    "multiple_choice_dropdown_menu", "dropdown_single_option",
    "multiple_option", "single_option", "upload_document"
]