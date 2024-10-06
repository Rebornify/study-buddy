import logging
import os
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mongoengine import connect
from openai import OpenAI
import streamlit as st
import streamlit_authenticator as stauth
import yaml
from yaml.loader import SafeLoader

from models import Message, Thread, User

# ----------------------------
# Configuration and Setup
# ----------------------------

# Set up the Streamlit page configuration
st.set_page_config(
    page_title='Study Buddy - Chat and Learn',
    layout="wide",
    page_icon=':books:'
)

# Load configuration from 'config.yaml' file
with open('config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

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
        connect(host=mongo_uri)
        logging.debug("Connected to MongoDB.")
    except Exception as e:
        logging.error(f"Failed to connect to MongoDB: {str(e)}")
        st.error(f"Failed to connect to MongoDB: {str(e)}")

# Define the model to be used for the assistant
MODEL = 'gpt-4o-mini'

# ----------------------------
# Custom BytesIO Subclass
# ----------------------------

class NamedBytesIO(BytesIO):
    """
    A subclass of BytesIO that includes a 'name' attribute.
    """
    def __init__(self, initial_bytes: Optional[bytes] = None, name: Optional[str] = None) -> None:
        super().__init__(initial_bytes)
        self.name = name

# ----------------------------
# Helper Functions
# ----------------------------

def upload_to_openai(named_upload_buffer: NamedBytesIO, filename: str) -> str:
    """Upload a file to OpenAI and return the file ID."""
    try:
        response = client.files.create(file=named_upload_buffer, purpose='assistants')
        logging.debug(f"File '{filename}' uploaded to OpenAI with ID: {response.id}")
        return response.id
    except Exception as e:
        logging.error(f"Failed to upload file {filename}: {str(e)}")
        st.sidebar.error(f"Failed to upload file {filename}: {str(e)}")
        raise e

def get_vector_store_files(vector_store_id):
    """Retrieve the list of uploaded files for a vector store."""
    try:
        files_list = client.beta.vector_stores.files.list(vector_store_id=vector_store_id)
        file_details = [
            {'name': client.files.retrieve(file.id).filename, 'id': file.id}
            for file in files_list.data
        ]
        logging.debug(f"Retrieved files from vector store {vector_store_id}: {file_details}")
        return file_details
    except Exception as e:
        logging.error(f"Failed to retrieve files for vector store {vector_store_id}: {str(e)}")
        return []

def handle_file_upload(uploaded_files, current_user):
    """Handle the file upload process for the current user."""
    if not uploaded_files:
        st.sidebar.warning('Please select a file to upload.')
        return

    vector_store_id = st.session_state.get('vector_store_id')
    if not vector_store_id:
        st.sidebar.warning('Vector store not created. Please try uploading files again.')
        return

    current_files = {f['name'] for f in get_vector_store_files(vector_store_id)}
    logging.debug(f"Current files in vector store: {current_files}")

    for file in uploaded_files:
        if file.name not in current_files:
            try:
                # Use the NamedBytesIO subclass
                named_upload_buffer = NamedBytesIO(file.getbuffer(), name=file.name)
                
                # Upload the file to OpenAI and associate it with the vector store
                file_id = upload_to_openai(named_upload_buffer, named_upload_buffer.name)
                client.beta.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=file_id
                )
                logging.debug(f'File "{named_upload_buffer.name}" attached to vector store ID: {vector_store_id}')
                st.sidebar.success(f'File "{named_upload_buffer.name}" uploaded and attached successfully.')
            except Exception as e:
                st.sidebar.error(f'Error uploading file "{file.name}": {str(e)}')
                logging.error(f'Error uploading file "{file.name}": {str(e)}')

    st.sidebar.info("Files are being processed and will be available shortly.")

def create_thread(title='New thread', assistant_id=None, vector_store_id=None, user=None):
    """Create a new thread associated with a user."""
    if user is None:
        raise ValueError("User must be provided to create a thread.")

    # Create a new thread via OpenAI API
    new_thread_id = client.beta.threads.create().id
    new_thread = Thread(
        thread_id=new_thread_id,
        vector_store_id=vector_store_id,
        assistant_id=assistant_id,
        title=title,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        user=user
    )
    new_thread.save()
    logging.debug(f"Thread '{title}' created with ID: {new_thread.thread_id} for user: {user.username}")
    return new_thread

def delete_thread(thread_id):
    """Delete a thread and its associated messages from the database and OpenAI."""
    try:
        thread = Thread.objects(thread_id=thread_id).first()
        if thread:
            # Delete the thread from OpenAI
            try:
                response = client.beta.threads.delete(thread_id)
                if not response.deleted:
                    logging.error(f"Failed to delete thread {thread_id} from OpenAI.")
                    return False
            except Exception as e:
                logging.error(f"Error deleting thread {thread_id} from OpenAI: {str(e)}")
                return False

            # Delete associated messages from local database
            Message.objects(thread=thread).delete()
            
            # Delete the thread from local database
            thread.delete()
            
            logging.debug(f"Thread {thread_id} and its messages deleted successfully from both OpenAI and local database.")
            return True
        else:
            logging.warning(f"Thread {thread_id} not found for deletion.")
            return False
    except Exception as e:
        logging.error(f"Error deleting thread {thread_id}: {str(e)}")
        return False

def create_assistant(vector_store_id):
    """Create an assistant using the provided vector_store_id."""
    try:
        # Define the assistant's instructions and tools
        assistant_instructions = (
            "You are an AI study assistant called 'Study Buddy'. Your role is to help students learn and understand various concepts in their field of study.\n\n"
            "When a student asks a question, provide clear and concise explanations of the relevant topics. Break down complex concepts into easily understandable parts. Share helpful resources, such as academic papers, tutorials, or online courses, that can further enhance their understanding.\n\n"
            "Engage in meaningful discussions with the student to deepen their understanding of the subject matter. Encourage them to think critically and ask questions. Help them develop problem-solving skills and provide guidance on practical applications of the concepts they are learning.\n\n"
            "Be friendly, supportive, and patient in your interactions. Motivate the student to stay curious and persistent in their learning journey. Foster a positive and encouraging learning environment.\n\n"
            "Tailor your responses to the student's level of understanding and learning style. Adapt your explanations and examples to make the content more relatable and accessible.\n\n"
            "Remember, your goal is to empower the student to grasp the material effectively and develop a strong foundation in their chosen field of study."
        )
        # Create the assistant via OpenAI API
        assistant = client.beta.assistants.create(
            instructions=assistant_instructions,
            name='Study Buddy',
            tools=[{'type': 'code_interpreter'}, {'type': 'file_search'}],
            tool_resources={'file_search': {'vector_store_ids': [vector_store_id]}},
            model=MODEL,
        )
        if not assistant.id:
            logging.error("Assistant creation returned without an ID.")
            raise ValueError("Assistant creation returned without an ID.")
        logging.debug(f"Assistant created with ID: {assistant.id}")

        # Set success message in session state
        st.session_state.assistant_created = True
        return assistant.id
    except Exception as e:
        logging.exception("Failed to create assistant.")
        raise e

def save_user(username, name, email):
    """Save the newly registered user to MongoDB."""
    if not User.objects(username=username).first():
        new_user = User(
            username=username,
            name=name,
            email=email
        )
        new_user.save()
        logging.debug(f"User {username} successfully saved to MongoDB.")
    else:
        logging.warning(f"User {username} already exists in the database.")

def get_threads(user):
    """Retrieve all threads for a specific user."""
    return Thread.objects(user=user).order_by('-updated_at')

def save_message(thread_id, role, content):
    """Save a message to the database."""
    current_thread = Thread.objects(thread_id=thread_id).first()
    if not current_thread:
        raise ValueError(f'No thread found for thread_id: {thread_id}')
    Message(
        thread=current_thread,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc)
    ).save()
    current_thread.update(updated_at=datetime.now(timezone.utc))  # Use update for efficiency

def get_messages(thread_id):
    """Retrieve messages for a thread."""
    current_thread = Thread.objects(thread_id=thread_id).first()
    if current_thread:
        return Message.objects(thread=current_thread).order_by('created_at')
    return []

def initialize_session_state():
    """Initialize the session state with default values."""
    defaults = {
        'file_id_list': [],
        'thread_id': None,
        'assistant_id': None,
        'vector_store_id': None
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)
    logging.debug(f"Session state initialized with keys: {', '.join(defaults.keys())}")

def get_current_user(username):
    """Fetch the current user from the database based on username."""
    return User.objects(username=username).first()

# ----------------------------
# UI Components
# ----------------------------

def display_home(current_user):
    """Display the home page."""
    st.title("Welcome to Study Buddy")
    st.write("""
    **Study Buddy** is your personal AI assistant to help you learn and understand various concepts.

    **What you can do:**
    - **Start a New Chat:** Upload your study materials and initiate a new conversation with your assistant.
    - **View Chat History:** Access and continue your previous study sessions.

    Use the sidebar to navigate between different sections and select chat threads!
    """)

def create_new_chat(current_user):
    """Create a new chat session."""
    st.title("Start a New Chat")

    # Step 1: Upload Files
    st.header("Step 1: Upload Files")
    uploaded_files = st.file_uploader(
        'Upload your study materials (.pdf, .txt, etc.)',
        type=['pdf', 'txt'],
        key='file_upload',
        accept_multiple_files=True
    )

    if st.button('Upload File(s)'):
        if uploaded_files:
            # Create vector store and handle file upload
            timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
            vector_store = client.beta.vector_stores.create(name=f'Study Buddy Vector Store - {timestamp}')
            st.session_state.vector_store_id = vector_store.id
            handle_file_upload(uploaded_files, current_user)
        else:
            st.warning('Please select at least one file to upload.')

    # Display Uploaded Files
    if st.session_state.get('vector_store_id'):
        st.subheader("Uploaded Files:")
        files = get_vector_store_files(st.session_state.vector_store_id)
        if files:
            for file in files:
                st.write(f'- {file["name"]}')
        else:
            st.info("No files uploaded yet.")

    # Step 2: Create Assistant
    st.header("Step 2: Create Assistant")
    if st.button('Create Assistant'):
        if not st.session_state.get('vector_store_id'):
            st.warning('Please upload files before creating assistant.')
        else:
            try:
                assistant_id = create_assistant(st.session_state.vector_store_id)
                st.session_state.assistant_id = assistant_id
                st.success('Assistant created successfully!')
            except Exception as e:
                st.error(f'Error creating assistant: {str(e)}')

    # Step 3: Start Chatting
    st.header("Step 3: Start Chatting")
    thread_title = st.text_input('Enter a title for this thread:', 'New thread')
    if st.button('Start Chatting'):
        if not st.session_state.get('assistant_id'):
            st.warning('Please create an assistant before starting chat.')
        else:
            try:
                create_thread(
                    title=thread_title,
                    assistant_id=st.session_state.assistant_id,
                    vector_store_id=st.session_state.vector_store_id,
                    user=current_user
                )
                st.success('Chat started successfully! You can now interact with your assistant from the Chat History section.')
            except Exception as e:
                st.error(f'Error creating thread: {str(e)}')

def select_thread_sidebar(current_user):
    """Display thread selection in the sidebar."""
    threads = get_threads(current_user)
    if threads:
        st.sidebar.header("Select Chat Thread")
        selected_thread_id = st.sidebar.selectbox(
            "Choose a thread:",
            options=[thread.thread_id for thread in threads],
            format_func=lambda x: next((thread.title for thread in threads if thread.thread_id == x), "Unknown Thread")
        )

        if st.sidebar.button("Delete Selected Thread"):
            if delete_thread(selected_thread_id):
                st.sidebar.success("Thread deleted successfully.")
                st.session_state.thread_id = None
            else:
                st.sidebar.error("Failed to delete the thread.")

        st.session_state.thread_id = selected_thread_id
        return Thread.objects(thread_id=selected_thread_id).first()
    return None

def display_thread(selected_thread):
    """Display the selected thread and chat interface."""
    st.title(f"Chat: {selected_thread.title}")
    handle_chat_interface(selected_thread)

def handle_chat_interface(selected_thread):
    """Handle the chat interface for the selected thread."""
    if not selected_thread:
        st.info('No chat selected. Start a new chat from the New Chat tab.')
        return

    thread_id = selected_thread.thread_id
    st.session_state.thread_id = thread_id
    st.session_state.assistant_id = selected_thread.assistant_id

    # Display saved messages
    saved_messages = get_messages(st.session_state.thread_id)
    for message in saved_messages:
        with st.chat_message(message.role):
            st.markdown(message.content, unsafe_allow_html=True)

    # Get user input
    prompt = st.chat_input('Ask a question or send a message')
    if prompt:
        # Display user message
        with st.chat_message('user'):
            st.markdown(prompt)

        # Save and send user message
        save_message(st.session_state.thread_id, 'user', prompt)
        try:
            client.beta.threads.messages.create(
                thread_id=st.session_state.thread_id,
                role='user',
                content=prompt
            )
        except Exception as e:
            st.error(f"Failed to send message to OpenAI: {str(e)}")
            logging.error(f"Failed to send message to OpenAI: {str(e)}")
            return

        with st.spinner('Generating response...'):
            try:
                run = client.beta.threads.runs.create_and_poll(
                    thread_id=st.session_state.thread_id,
                    assistant_id=st.session_state.assistant_id,
                )
            except Exception as e:
                st.error(f"Failed to create and poll run: {str(e)}")
                logging.error(f"Failed to create and poll run: {str(e)}")
                return

            # Check the run status after create_and_poll
            if run.status != 'completed':
                st.error(f'Run failed with status: {run.status}')
                logging.error(f'Run failed with status: {run.status}')
                return

        # Retrieve and display the latest assistant's response with annotations handling
        try:
            messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)

            # Extract the message content
            message_content = messages.data[0].content[0].text
            annotations = message_content.annotations
            # citations = []

            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations, start=1):
                # Replace the text with a footnote
                message_content.value = message_content.value.replace(
                    annotation.text, f' <sup>[{index}]</sup>'
                )

                # # Gather citations based on annotation attributes
                # if (file_citation := getattr(annotation, 'file_citation', None)):
                #     cited_file = client.files.retrieve(file_citation.file_id)
                #     # citations.append(f'[{index}] {file_citation.quote} from {cited_file.filename}')
                # elif (file_path := getattr(annotation, 'file_path', None)):
                #     cited_file = client.files.retrieve(file_path.file_id)
                #     # citations.append(f'[{index}] Click <here> to download {cited_file.filename}')
                #     # Note: File download functionality not implemented above for brevity

            # # Add footnotes to the end of the message before displaying to user
            # message_content.value += '\n' + '\n'.join(citations)

            # Display the modified assistant message
            with st.chat_message('assistant'):
                st.markdown(message_content.value, unsafe_allow_html=True)

            # Save the modified message
            save_message(st.session_state.thread_id, 'assistant', message_content.value)
        except Exception as e:
            st.error(f"Failed to retrieve assistant message: {str(e)}")
            logging.error(f"Failed to retrieve assistant message: {str(e)}")

# ----------------------------
# Main Application
# ----------------------------

def main():
    """Main function to run the Streamlit app."""
    # Initialize the authenticator object using the credentials from the config
    authenticator = stauth.Authenticate(
        'config.yaml',
        config['cookie']['name'],
        config['cookie']['key'],
        config['cookie']['expiry_days']
    )

    # Access the authentication status from st.session_state
    authentication_status = st.session_state.get('authentication_status')

    # If the user is authenticated, hide login/register and show the app content
    if authentication_status:
        # Sidebar for navigation after successful login
        st.sidebar.title(f"Welcome, {st.session_state['name']}")
        authenticator.logout('Logout', 'sidebar')

        # Get current user details based on the username (stored in session state)
        current_user = get_current_user(st.session_state['username'])

        # Navigation in sidebar
        app_page = st.sidebar.radio("Navigate to", ["Home", "New Chat", "Chat History"])

        if app_page == "Home":
            display_home(current_user)
        elif app_page == "New Chat":
            create_new_chat(current_user)
        elif app_page == "Chat History":
            selected_thread = select_thread_sidebar(current_user)
            if selected_thread:
                display_thread(selected_thread)
            else:
                st.info("No thread selected or no threads available. Start by creating a new chat.")

    # If the user is not authenticated, show login/register options
    else:
        # Option for Login or Registration
        page = st.sidebar.radio("Choose Action", ["Login", "Register"])

        if page == "Login":
            # Authentication process (No need to unpack return values when using 'main')
            authenticator.login('main')

            # Handle authentication status from session state
            if st.session_state.get('authentication_status') == False:
                st.error("Username/password is incorrect")
            elif st.session_state.get('authentication_status') is None:
                st.warning("Please enter your username and password")

        elif page == "Register":
            st.title("Register")
            # Allow new user registration even if credentials exist
            try:
                email, username, name = authenticator.register_user(location='main', key='register')
                if email:
                    st.success("User registered successfully! You can now log in.")
                    # Save the user to MongoDB
                    save_user(username, name, email)
            except Exception as e:
                st.error(f"Registration failed: {str(e)}")

if __name__ == "__main__":
    main()
