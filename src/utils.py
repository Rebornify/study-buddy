import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional

import streamlit as st

from config import MODEL, client
from models import Message, Thread, User, File, VectorStore, Assistant

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

def handle_file_upload(uploaded_files, current_user):
    """Handle the file upload process for the current user."""
    if not uploaded_files:
        st.warning('Please select a file to upload.')
        return

    for file in uploaded_files:
        try:
            # Use the NamedBytesIO subclass
            named_upload_buffer = NamedBytesIO(file.getbuffer(), name=file.name)
            
            # Upload the file to OpenAI
            file_id = upload_to_openai(named_upload_buffer, named_upload_buffer.name)
            logging.debug(f'File "{named_upload_buffer.name}" uploaded to OpenAI with ID: {file_id}')
            st.success(f'File "{named_upload_buffer.name}" uploaded successfully.')

            # Save the file in the File model
            new_file = File(
                file_id=file_id,
                name=file.name,
                user=current_user,
                created_at=datetime.now(timezone.utc)
            )
            new_file.save()
            logging.debug(f'File "{file.name}" saved to database with ID: {file_id}')

        except Exception as e:
            st.error(f'Error uploading file "{file.name}": {str(e)}')
            logging.error(f'Error uploading file "{file.name}": {str(e)}')

    st.info("Files are being processed and will be available shortly.")

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

def get_user_files(user):
    """Retrieve all files uploaded by the user."""
    return File.objects(user=user)

def create_vector_store(name, selected_file_ids, current_user):
    """Create a new vector store and associate selected files."""
    try:
        # Create vector store via OpenAI API
        vector_store = client.beta.vector_stores.create(name=name)
        vector_store_id = vector_store.id

        # Save the vector store in the database
        new_vector_store = VectorStore(
            vector_store_id=vector_store_id,
            name=name,
            user=current_user,
            created_at=datetime.now(timezone.utc)
        )
        new_vector_store.save()
        logging.debug(f'Vector store "{name}" saved to database with ID: {vector_store_id}')

        # Attach selected files to the vector store
        create_vector_store_files(vector_store_id, selected_file_ids)

        return vector_store_id
    except Exception as e:
        logging.error(f'Error creating vector store "{name}": {str(e)}')
        st.error(f'Error creating vector store: {str(e)}')
        return None

def create_vector_store_files(vector_store_id, file_ids):
    """Attach files to a vector store."""
    for file_id in file_ids:
        try:
            client.beta.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file_id
            )
            logging.debug(f'File ID "{file_id}" attached to vector store ID: {vector_store_id}')
        except Exception as e:
            logging.error(f'Error attaching file ID "{file_id}" to vector store "{vector_store_id}": {str(e)}')
            st.error(f'Error attaching file to vector store: {str(e)}')

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

def get_user_vector_stores(user):
    """Retrieve all vector stores created by the user."""
    return VectorStore.objects(user=user)

def create_assistant(name, vector_store_id, user):
    """Create an assistant using the provided vector_store_id and save it to the database."""
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
            name=name,
            tools=[{'type': 'code_interpreter'}, {'type': 'file_search'}],
            tool_resources={'file_search': {'vector_store_ids': [vector_store_id]}},
            model=MODEL,
        )
        if not assistant.id:
            logging.error("Assistant creation returned without an ID.")
            raise ValueError("Assistant creation returned without an ID.")
        logging.debug(f"Assistant created with ID: {assistant.id}")

        # Save the assistant to the database
        vector_store = VectorStore.objects(vector_store_id=vector_store_id).first()
        new_assistant = Assistant(
            assistant_id=assistant.id,
            name=name,
            vector_store=vector_store,
            user=user,
            created_at=datetime.now(timezone.utc)
        )
        new_assistant.save()
        logging.debug(f"Assistant '{name}' saved to database with ID: {assistant.id}")

        # Set success message in session state
        st.session_state.assistant_created = True
        return assistant.id
    except Exception as e:
        logging.exception("Failed to create assistant.")
        raise e

def get_user_assistants(user):
    """Retrieve all assistants created by the user."""
    return Assistant.objects(user=user)

def create_thread(title='New thread', assistant_id=None, vector_store_id=None, user=None):
    """Create a new thread associated with a user."""
    if user is None:
        raise ValueError("User must be provided to create a thread.")

    # Fetch the VectorStore object
    vector_store = VectorStore.objects(vector_store_id=vector_store_id).first()

    # Create a new thread via OpenAI API
    new_thread_id = client.beta.threads.create().id
    new_thread = Thread(
        thread_id=new_thread_id,
        vector_store=vector_store,
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

def get_current_user(username):
    """Fetch the current user from the database based on username."""
    return User.objects(username=username).first()

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
