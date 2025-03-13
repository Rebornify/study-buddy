import logging
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from db_setup import initialize_db

# ----------------------------
# Configuration and Setup
# ----------------------------

# Set up the Streamlit page configuration
st.set_page_config(
    page_title='Study Buddy - Chat and Learn',
    layout="wide",
    page_icon=':books:'
)

# Configure logging settings
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# Load environment variables from '.env' file or assume production environment
env_path = Path('.') / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    ENVIRONMENT = "development"
    logging.debug(".env file loaded.")
else:
    ENVIRONMENT = "production"
    logging.debug("Assuming production environment.")

def get_env_variable(var_name):
    """Retrieve environment variables based on the environment."""
    return st.secrets.get(var_name) if ENVIRONMENT == "production" else os.getenv(var_name)

def get_and_validate_env(var_name, display_name):
    """Retrieve and validate an environment variable."""
    value = get_env_variable(var_name)
    if not value:
        logging.error(f"{display_name} not found.")
        st.error(f"{display_name} not found. Please check your .env file or Streamlit Secrets.")
    return value

# Retrieve and validate necessary environment variables
api_key = get_and_validate_env("OPENAI_API_KEY", "OpenAI API key")
mongo_uri = get_and_validate_env("MONGO_CONNECTION_STRING", "MongoDB connection string")

# Initialize OpenAI client and MongoDB connection if keys are present
if api_key:
    client = OpenAI(api_key=api_key)
    logging.debug("OpenAI API key loaded successfully.")

if mongo_uri:
    try:
        initialize_db(mongo_uri)
    except Exception as e:
        logging.error(f"Failed to initialize MongoDB: {str(e)}")
        st.error(f"Failed to initialize MongoDB: {str(e)}")

# Define the model to be used for the assistant
MODEL = 'gpt-4o-mini'
