import os
import os
import pandas as pd


from langchain_astradb import AstraDBVectorStore
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_openai import OpenAIEmbeddings


from helpers.astradb_connect_helper import get_astradb_form_context

from setup import (
    ASTRADB_API_ENDPOINT,
    ASTRADB_COLLECTION_NAME,
    ASTRADB_NAMESPACE_NAME,
    ASTRADB_TOKEN_KEY,
    LOGGER,
    OPENAI_EMBEDD_API_KEY
)

def convert_csv_to_content():
    """
    Uploads a CSV file from user input, processes it into document format,
    and inserts it into AstraDB using the Astrapy client.
    """

    # Step 1: GET CSV file
    csv_file = os.path.join("data","input","form_context.csv")

    # Step 2: Read and preprocess CSV into a DataFrame
    df = pd.read_csv(csv_file)
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    df = df.fillna("")

    # Step 3: Convert each row into a document for AstraDB
    form_data = []
    for form in df.to_dict(orient="records"):
        context = form.get("context", "").strip()
        
        # Skip if empty
        if context:
            document = {
                "content": context,
                "$vectorize": context,
                "metadata": {
                    "type_of_form": form.get("type_of_form", ""),
                    "template_name": form.get("template_name", ""),
                    "link": form.get("link", "")
                }
            }
            form_data.append(document)
    if form_data:
        insert_content_form(form_data)
    
    else:
        LOGGER.error("No Form Data Template is format created")


def insert_content_form(form_insert: list[dict]):

    # Step 4: Insert into AstraDB
    try:
        collection = get_astradb_form_context()

        response = collection.insert_many(form_insert)
        LOGGER.info(f"Inserted {len(response.inserted_ids)} documents into AstraDB successfully.")

    except Exception as error:
        LOGGER.error(f"Error inserting documents: {error}")


def init_astradb_retriever(close_returned: int = 3) -> VectorStoreRetriever:
    """
    Initializes an AstraDB vector store retriever using OpenAI embeddings.

    Args:
        close_returned (int): Number of top similar results to retrieve. Defaults to 3.

    Returns:
        retriever (langchain.retriever.BaseRetriever): Configured retriever instance.
    """
    # Step 1: Setup embedding model
    embedding = OpenAIEmbeddings(
        model="text-embedding-3-small",
        openai_api_key=OPENAI_EMBEDD_API_KEY
    )

    # Step 2: Connect to AstraDB
    vectorstore = AstraDBVectorStore(
        embedding=embedding,
        collection_name=ASTRADB_COLLECTION_NAME,
        token=ASTRADB_TOKEN_KEY,
        api_endpoint=ASTRADB_API_ENDPOINT,
        namespace=ASTRADB_NAMESPACE_NAME
    )

    # Step 3: Return retriever
    return vectorstore.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={
            "k": close_returned,
            "score_threshold": 0.7
        }
    )
