# *************** IMPORT FRAMEWORK *************** 
from astrapy import DataAPIClient, Collection
from astrapy.exceptions import DataAPITimeoutException

# *************** LOAD ENVIRONMENT ***************
from setup import (
    ASTRADB_API_ENDPOINT,
    ASTRADB_COLLECTION_NAME,
    ASTRADB_NAMESPACE_NAME,
    ASTRADB_TOKEN_KEY,
)

# *************** Custom Exception for AstraDB Connection Issues
class AstraDBConnectionError(Exception):
    """
    Custom Exception Error for AstraDB.
    Raised when there is a failure connecting to AstraDB.
    """
    pass

# *************** Helper Function to Get AstraDB Collection ***************
def get_astradb_collection(collection_name: str, namespace: str) -> Collection:
    """
    Initialize the DataAPIClient and retrieve the specified AstraDB collection.
    
    Args:
        collection_name (str): Name of the AstraDB collection.
        namespace (str): Namespace for the AstraDB collection.
    
    Returns:
        Collection: The AstraDB collection object.
    
    Raises:
        AstraDBConnectionError: If there is a connection issue with AstraDB.
    """
    try:
        # *************** Client to access to database
        client = DataAPIClient(ASTRADB_TOKEN_KEY)
        database = client.get_database(ASTRADB_API_ENDPOINT)

        # *************** Get access to specific collection
        return database.get_collection(collection_name, namespace=namespace)
    
    except DataAPITimeoutException as error:
        # *************** Handle API timeout errors separately
        raise AstraDBConnectionError(f"AstraDB connection timed out for collection: {collection_name}: {error}")
    
    except Exception as error:
        # *************** Catch all other AstraDB connection failures
        raise AstraDBConnectionError(f"Failed to connect to AstraDB for collection {collection_name}: {error}")

# *************** Specific Collection Functions ***************
def get_astradb_form_context() -> Collection:
    """
    Retrieve the main AstraDB collection or Job Info Vectorized collection.
    
    Returns:
        Collection: The AstraDB main collection object or Job Info Vectorized.
    """
    return get_astradb_collection(ASTRADB_COLLECTION_NAME, ASTRADB_NAMESPACE_NAME)

