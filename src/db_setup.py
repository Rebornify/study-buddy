import logging
from mongoengine import connect
from models import User, File, VectorStore, Assistant, Thread, Message

def initialize_db(mongo_uri):
    """Connect to MongoDB and ensure collections exist."""
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