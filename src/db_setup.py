import logging
from typing import NoReturn

from mongoengine import connect
from models import User, File, VectorStore, Assistant, Thread, Message

def initialize_db(mongo_uri: str) -> NoReturn:
    """
    Connect to MongoDB and ensure collections and indexes exist.
    
    This function establishes a connection to the MongoDB database using the provided
    connection URI and ensures that all required collections and indexes are set up
    for the application's models.
    
    Args:
        mongo_uri: MongoDB connection string URI
        
    Raises:
        Exception: If connection or index creation fails
    """
    try:
        connect(host=mongo_uri)
        logging.debug("Connected to MongoDB.")

        # Ensure indexes are created
        models = [User, File, VectorStore, Assistant, Thread, Message]
        for model in models:
            model.ensure_indexes()
            logging.debug(f"Indexes ensured for {model.__name__}.")

        logging.debug("MongoDB collections and indexes checked successfully.")
    except Exception as e:
        logging.error(f"Database initialization failed: {str(e)}")
        raise e  # Rethrow to handle higher in the app 