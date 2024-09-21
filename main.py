import os
import time
import logging
from datetime import datetime, timezone

from dotenv import load_dotenv
from mongoengine import connect
from openai import OpenAI
import streamlit as st

from models import Thread, Message

# ----------------------------
# Configuration and Setup
# ----------------------------

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

# Load environment variables
load_dotenv()

# Retrieve OpenAI API key from environment variables
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logging.error("OpenAI API key not found in environment variables.")
    st.error("OpenAI API key not found. Please check your .env file.")
else:
    client = OpenAI(api_key=api_key)
    logging.debug("OpenAI API key loaded successfully.")

# Define the model
MODEL = 'gpt-4o-mini'

# Connect to MongoDB
try:
    connect('chatbot_db', host='localhost', port=27017)
    logging.debug("Connected to MongoDB.")
except Exception as e:
    logging.error(f"Failed to connect to MongoDB: {str(e)}")
    st.error(f"Failed to connect to MongoDB: {str(e)}")

# ----------------------------
# Helper Functions
# ----------------------------

def upload_to_openai(filepath):
    """Uploads a file to OpenAI and returns the file ID."""
    try:
        with open(filepath, 'rb') as file:
            response = client.files.create(file=file, purpose='assistants')
            logging.debug(f"File uploaded to OpenAI with ID: {response.id}")
            return response.id
    except Exception as e:
        logging.error(f"Failed to upload file {filepath}: {str(e)}")
        st.sidebar.error(f"Failed to upload file {filepath}: {str(e)}")
        raise e

def get_vector_store_files(vector_store_id):
    """Retrieves the list of uploaded files for a vector store."""
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

def handle_file_upload(uploaded_files):
    """Handles the file upload process."""
    if not uploaded_files:
        st.sidebar.warning('Please select a file to upload.')
        return

    if not st.session_state.get('vector_store_id'):
        st.sidebar.warning('Vector store not created. Please try uploading files again.')
        return

    vector_store_id = st.session_state.vector_store_id
    current_files = {f['name'] for f in get_vector_store_files(vector_store_id)}
    logging.debug(f"Current files in vector store: {current_files}")

    for file in uploaded_files:
        if file.name not in current_files:
            file_path = os.path.join(os.getcwd(), file.name)
            with open(file_path, 'wb') as file_obj:
                file_obj.write(file.getbuffer())
            try:
                file_id = upload_to_openai(file_path)
                client.beta.vector_stores.files.create(
                    vector_store_id=vector_store_id,
                    file_id=file_id
                )
                logging.debug(f'File "{file.name}" attached to vector store ID: {vector_store_id}')
                st.sidebar.success(f'File "{file.name}" uploaded and attached successfully.')
            except Exception as e:
                st.sidebar.error(f'Error uploading file "{file.name}": {str(e)}')
                logging.error(f'Error uploading file "{file.name}": {str(e)}')
            finally:
                os.remove(file_path)

    st.sidebar.info("Files are being processed and will be available shortly.")

def create_thread(title='New thread', assistant_id=None, vector_store_id=None):
    """Creates a new thread."""
    new_thread_id = client.beta.threads.create().id
    new_thread = Thread(
        thread_id=new_thread_id,
        assistant_id=assistant_id,
        vector_store_id=vector_store_id,
        title=title,
        created_at=datetime.now(timezone.utc)
    )
    new_thread.save()
    logging.debug(f"Thread created with ID: {new_thread.thread_id}")
    return new_thread

def create_assistant(vector_store_id):
    """Creates an assistant using the provided thread's vector_store_id."""
    try:
        logging.debug("Initiating assistant creation.")
        assistant_instructions = '''You are an AI study assistant called 'Study Buddy'. Your role is to help students learn and understand various concepts in their field of study.

When a student asks a question, provide clear and concise explanations of the relevant topics. Break down complex concepts into easily understandable parts. Share helpful resources, such as academic papers, tutorials, or online courses, that can further enhance their understanding.

Engage in meaningful discussions with the student to deepen their understanding of the subject matter. Encourage them to think critically and ask questions. Help them develop problem-solving skills and provide guidance on practical applications of the concepts they are learning.

Be friendly, supportive, and patient in your interactions. Motivate the student to stay curious and persistent in their learning journey. Foster a positive and encouraging learning environment.

Tailor your responses to the student's level of understanding and learning style. Adapt your explanations and examples to make the content more relatable and accessible.

Remember, your goal is to empower the student to grasp the material effectively and develop a strong foundation in their chosen field of study.'''
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
        return assistant.id
    except Exception as e:
        logging.exception("Failed to create assistant.")
        raise e

def get_threads():
    """Retrieves all threads from the database."""
    return Thread.objects().order_by('-updated_at')

def save_message(thread_id, role, content):
    """Saves a message to the database."""
    current_thread = Thread.objects(thread_id=thread_id).first()
    if not current_thread:
        raise ValueError(f'No thread found for thread_id: {thread_id}')
    Message(
        thread=current_thread,
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc)
    ).save()
    current_thread.updated_at = datetime.now(timezone.utc)
    current_thread.save()

def get_messages(thread_id):
    """Retrieves messages for a thread."""
    current_thread = Thread.objects(thread_id=thread_id).first()
    if current_thread:
        return Message.objects(thread=current_thread).order_by('created_at')
    return []

def initialize_session_state():
    """Initializes the session state."""
    keys_defaults = {
        'file_id_list': [],
        'start_chat': False,
        'thread_id': None,
        'assistant_id': None,
        'vector_store_id': None,
        'thread': None
    }
    for key, default in keys_defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default
    logging.debug("Session state initialized with keys: " + ", ".join(keys_defaults.keys()))

# ----------------------------
# UI Components
# ----------------------------

def setup_sidebar():
    """Sets up the sidebar with file upload and assistant creation controls."""
    # Step 1: Upload Files
    st.sidebar.header("Step 1: Upload Files")
    uploaded_files = st.sidebar.file_uploader(
        'Upload your study materials (PDF, TXT, etc.)',
        type=['pdf', 'txt'],
        key='file_upload',
        accept_multiple_files=True
    )

    if st.sidebar.button('Upload File(s)'):
        if uploaded_files:
            # Create vector store if it doesn't exist
            if not st.session_state.get('vector_store_id'):
                timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                vector_store = client.beta.vector_stores.create(name=f'Study Buddy Vector Store - {timestamp}')
                st.session_state.vector_store_id = vector_store.id
                logging.debug(f"Vector store created with ID: {vector_store.id}")
            handle_file_upload(uploaded_files)
        else:
            st.sidebar.warning('Please select at least one file to upload.')

    # Display Uploaded Files
    st.sidebar.subheader("Uploaded Files:")
    if st.session_state.get('vector_store_id'):
        files = get_vector_store_files(st.session_state.vector_store_id)
        if files:
            for file in files:
                st.sidebar.write(f'- {file["name"]}')
        else:
            st.sidebar.info("No files uploaded yet.")
    else:
        st.sidebar.info("No vector store created yet.")

    # Step 2: Create Assistant
    st.sidebar.header("Step 2: Create Assistant")
    if st.sidebar.button('Create Assistant'):
        if not st.session_state.get('vector_store_id'):
            st.sidebar.warning('Please upload files before creating assistant.')
            return
        if not st.session_state.get('assistant_id'):
            try:
                assistant_id = create_assistant(st.session_state.vector_store_id)
                st.session_state.assistant_id = assistant_id
                st.sidebar.success(f'Assistant created with ID: {assistant_id}')
                logging.debug(f"Assistant created with ID: {assistant_id}")
            except Exception as e:
                st.sidebar.error(f'Error creating assistant: {str(e)}')
                logging.error(f'Error creating assistant: {str(e)}')
                return
        else:
            st.sidebar.info('Assistant already created.')

    # Step 3: Start Chatting
    st.sidebar.header("Step 3: Start Chatting")
    thread_title = st.sidebar.text_input('Enter a title for this thread:', 'New thread')
    if st.sidebar.button('Start Chatting'):
        if not st.session_state.get('assistant_id'):
            st.sidebar.warning('Please create an assistant before starting chat.')
            return
        if not st.session_state.get('thread'):
            try:
                st.session_state.thread = create_thread(
                    title=thread_title,
                    assistant_id=st.session_state.assistant_id,
                    vector_store_id=st.session_state.vector_store_id
                )
                st.session_state.thread_id = st.session_state.thread.thread_id
                st.session_state.start_chat = True
                st.sidebar.success(f'Chat started. Thread ID: {st.session_state.thread_id}')
                logging.debug(f"Thread '{thread_title}' created with ID: {st.session_state.thread_id}")
                st.rerun()
            except Exception as e:
                st.sidebar.error(f'Error creating thread: {str(e)}')
                logging.error(f'Error creating thread: {str(e)}')
                return
        else:
            st.session_state.start_chat = True
            st.sidebar.info(f'Continuing with existing thread: {st.session_state.thread.title}')

def display_threads():
    """Displays previous threads and allows resuming them."""
    threads = get_threads()
    if threads:
        st.subheader('Previous threads')
        for thread in threads:
            st.write(f'- {thread.title} (Created: {thread.created_at.strftime("%Y-%m-%d %H:%M")} UTC)')
            if st.button(f'Resume: {thread.title}', key=thread.thread_id):
                st.session_state.thread = thread
                st.session_state.thread_id = thread.thread_id
                st.session_state.vector_store_id = thread.vector_store_id
                st.session_state.assistant_id = thread.assistant_id
                st.session_state.start_chat = True
                st.rerun()
    else:
        st.info('No previous threads found.')

def handle_chat_interface():
    """Handles the chat interface."""
    if not st.session_state.start_chat:
        st.info('Please complete all steps in the sidebar to start chatting.')
        return

    # Display saved messages
    saved_messages = get_messages(st.session_state.thread_id)
    for message in saved_messages:
        with st.chat_message(message.role):
            st.markdown(message.content)

    # Get user input
    prompt = st.chat_input('Ask a question or send a message')
    if not prompt:
        st.info('Type your question or message in the input box below to start chatting.')
        return

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

    # Create a run and wait for completion
    try:
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=st.session_state.assistant_id
        )
    except Exception as e:
        st.error(f"Failed to create run: {str(e)}")
        logging.error(f"Failed to create run: {str(e)}")
        return

    with st.spinner('Generating response...'):
        try:
            start_time = time.time()
            timeout = 60  # seconds
            while run.status not in ['completed', 'failed', 'cancelled'] and time.time() - start_time < timeout:
                logging.debug(f"Run status: {run.status}")
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )
            if run.status != 'completed':
                st.error(f'Run failed with status: {run.status}')
                logging.error(f'Run failed with status: {run.status}')
                return
        except Exception as e:
            st.error(f"Error while waiting for run completion: {str(e)}")
            logging.error(f"Error while waiting for run completion: {str(e)}")
            return

    # Retrieve and display assistant's response
    try:
        messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
        assistant_messages_for_run = [
            message for message in messages
            if message.run_id == run.id and message.role == 'assistant'
        ]

        for message in assistant_messages_for_run:
            with st.chat_message('assistant'):
                st.markdown(message.content[0].text.value, unsafe_allow_html=True)
            save_message(st.session_state.thread_id, 'assistant', message.content[0].text.value)
    except Exception as e:
        st.error(f"Failed to retrieve assistant messages: {str(e)}")
        logging.error(f"Failed to retrieve assistant messages: {str(e)}")

# ----------------------------
# Main Application
# ----------------------------

def main():
    """Main function to run the Streamlit app."""
    st.set_page_config(page_title='Study Buddy - Chat and Learn', page_icon=':books:')
    st.title('Study Buddy')
    st.write('Learn fast by chatting with your study materials')

    initialize_session_state()
    setup_sidebar()
    display_threads()
    handle_chat_interface()

if __name__ == "__main__":
    main()
