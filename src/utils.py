import logging
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional, List, Union, Dict, Any, Tuple

import streamlit as st
import openai

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

def handle_file_upload(uploaded_files: List[st.runtime.uploaded_file_manager.UploadedFile], current_user: User) -> None:
    """
    Handle the file upload process for the current user.
    
    This function processes files uploaded through the Streamlit interface,
    uploads them to OpenAI, and saves their metadata in the database.
    
    Args:
        uploaded_files: List of files uploaded through Streamlit's file uploader
        current_user: Current authenticated user object
        
    Returns:
        None
        
    Displays:
        Warning or success messages to the user in the Streamlit interface
    """
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
    """
    Upload a file to OpenAI and return the file ID.
    
    Args:
        named_upload_buffer: BytesIO subclass containing the file data with a name attribute
        filename: Name of the file being uploaded
        
    Returns:
        str: The OpenAI file ID of the uploaded file
        
    Raises:
        Exception: If the file upload fails
    """
    try:
        response = client.files.create(file=named_upload_buffer, purpose='assistants')
        logging.debug(f"File '{filename}' uploaded to OpenAI with ID: {response.id}")
        return response.id
    except Exception as e:
        logging.error(f"Failed to upload file {filename}: {str(e)}")
        st.sidebar.error(f"Failed to upload file {filename}: {str(e)}")
        raise e

def get_user_files(user: User) -> List[File]:
    """
    Retrieve all files uploaded by the user.
    
    Args:
        user: User object whose files should be retrieved
        
    Returns:
        List of File objects belonging to the user
    """
    return File.objects(user=user)

def create_vector_store(name: str, selected_file_ids: List[str], current_user: User) -> str:
    """
    Create a new vector store and associate selected files, or reuse existing one.
    
    This function checks if a vector store with the exact same set of files already exists,
    and reuses it if found. Otherwise, it creates a new vector store.
    
    Args:
        name: Name for the new vector store
        selected_file_ids: List of OpenAI file IDs to include in the vector store
        current_user: User creating the vector store
        
    Returns:
        str: The ID of the created or reused vector store
        
    Raises:
        Exception: If vector store creation fails
    """
    try:
        # Check for existing vector stores with same files
        existing_vector_stores = VectorStore.objects(user=current_user)
        
        for vs in existing_vector_stores:
            try:
                vs_files = client.beta.vector_stores.files.list(vector_store_id=vs.vector_store_id)
                vs_file_ids = [file.id for file in vs_files.data]
                
                # Check if existing vector store has the exact same files
                if set(vs_file_ids) == set(selected_file_ids) and len(vs_file_ids) == len(selected_file_ids):
                    logging.info(f'Reusing existing vector store "{vs.name}" with ID: {vs.vector_store_id}')
                    # Return the existing vector store ID WITHOUT updating its name
                    return vs.vector_store_id
            except Exception as e:
                logging.warning(f'Error checking files for vector store {vs.vector_store_id}: {str(e)}')
                continue
                
        # No matching vector store found, create a new one
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
    """Create an assistant using the provided vector_store_id or reuse existing one."""
    try:
        # Check if an assistant already exists for this vector store
        vector_store = VectorStore.objects(vector_store_id=vector_store_id).first()
        existing_assistant = Assistant.objects(vector_store=vector_store, user=user).first()
        
        if existing_assistant:
            logging.info(f"Reusing existing assistant with ID: {existing_assistant.assistant_id}")
            # Set success message in session state
            st.session_state.assistant_created = True
            return existing_assistant.assistant_id
            
        # Define the assistant's instructions and tools
        assistant_instructions = (
            "You are an AI study assistant called 'Study Buddy'. Your role is to help students learn and understand various concepts in their field of study.\n\n"
            "When a student asks a question, provide clear and concise explanations of the relevant topics. Break down complex concepts into easily understandable parts. Share helpful resources, such as academic papers, tutorials, or online courses, that can further enhance their understanding.\n\n"
            "Engage in meaningful discussions with the student to deepen their understanding of the subject matter. Encourage them to think critically and ask questions. Help them develop problem-solving skills and provide guidance on practical applications of the concepts they are learning.\n\n"
            "Be friendly, supportive, and patient in your interactions. Motivate the student to stay curious and persistent in their learning journey. Foster a positive and encouraging learning environment.\n\n"
            "Tailor your responses to the student's level of understanding and learning style. Adapt your explanations and examples to make the content more relatable and accessible.\n\n"
            "Remember, your goal is to empower the student to grasp the material effectively and develop a strong foundation in their chosen field of study."
        )
        
        # Generate a default name based on the vector store if not provided
        if not name or name.strip() == '':
            name = f"Assistant for {vector_store.name}" if vector_store else "Study Buddy Assistant"
            
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

def create_thread(title: str = 'New thread', assistant_id: Optional[str] = None, 
                 vector_store_id: Optional[str] = None, user: Optional[User] = None) -> Optional[Thread]:
    """
    Create a new conversation thread.
    
    This function creates a new thread in OpenAI and stores it in the database.
    It associates the thread with an assistant, vector store, and user.
    
    Args:
        title: Title of the new thread (default: 'New thread')
        assistant_id: ID of the assistant to associate with the thread (optional)
        vector_store_id: ID of the vector store to associate with the thread (optional)
        user: User who owns the thread (optional)
        
    Returns:
        Thread: The newly created thread object or None if creation fails
        
    Raises:
        Exception: If thread creation fails
    """
    try:
        # Create the thread in OpenAI
        thread_response = client.beta.threads.create()
        
        # Create and save the thread in the database
        thread = Thread(
            thread_id=thread_response.id,
            vector_store=VectorStore.objects(vector_store_id=vector_store_id).first() if vector_store_id else None,
            assistant_id=assistant_id or "",
            title=title,
            user=user,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        thread.save()
        
        logging.debug(f"Thread created with ID: {thread.thread_id}")
        return thread
    except openai.APIError as e:
        logging.error(f"OpenAI API returned an API Error creating thread: {e}")
        st.error(f"Error creating study session: {str(e)}")
        return None
    except openai.APIConnectionError as e:
        logging.error(f"Failed to connect to OpenAI API when creating thread: {e}")
        st.error(f"Connection error. Please check your internet connection and try again.")
        return None
    except openai.RateLimitError as e:
        logging.error(f"OpenAI API request exceeded rate limit when creating thread: {e}")
        st.error(f"Too many requests. Please wait a moment and try again.")
        return None
    except Exception as e:
        logging.error(f"Error creating thread: {str(e)}")
        st.error(f"Error creating study session: {str(e)}")
        return None

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

def save_message(thread_id: str, role: str, content: str) -> Optional[Message]:
    """
    Save a new message to a conversation thread.
    
    This function creates a new Message object and saves it to the database,
    associating it with the specified thread.
    
    Args:
        thread_id: ID of the thread the message belongs to
        role: Role of the message sender (e.g., 'user', 'assistant')
        content: Text content of the message
        
    Returns:
        Message: The newly created message object or None if creation fails
    """
    try:
        thread = Thread.objects(thread_id=thread_id).first()
        if not thread:
            logging.error(f"Thread with ID {thread_id} not found")
            return None
        
        message = Message(
            thread=thread,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc)
        )
        message.save()
        
        # Update the thread's last updated timestamp
        thread.updated_at = datetime.now(timezone.utc)
        thread.save()
        
        logging.debug(f"Message saved to thread {thread_id}")
        return message
    except Exception as e:
        logging.error(f"Error saving message: {str(e)}")
        return None

def get_messages(thread_id: str) -> List[Message]:
    """
    Retrieve all messages from a specific thread.
    
    Args:
        thread_id: ID of the thread to get messages from
        
    Returns:
        List[Message]: List of message objects belonging to the thread,
                       sorted by creation time
    """
    try:
        thread = Thread.objects(thread_id=thread_id).first()
        if not thread:
            logging.warning(f"Thread with ID {thread_id} not found when retrieving messages")
            return []
        
        messages = Message.objects(thread=thread).order_by('+created_at')
        return messages
    except Exception as e:
        logging.error(f"Error retrieving messages for thread {thread_id}: {str(e)}")
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

def get_or_create_user_from_google(email: str, name: str) -> User:
    """
    Get an existing user by email or create a new one from Google authentication data.
    
    This function checks if a user with the given email exists in the database.
    If found, it returns that user. If not, it creates a new user with the provided
    Google authentication information.
    
    Args:
        email: User's email address from Google authentication
        name: User's full name from Google authentication
        
    Returns:
        User: The existing or newly created user object
    """
    try:
        # Check if user exists already
        existing_user = User.objects(email=email).first()
        
        if existing_user:
            logging.debug(f"Found existing user with email: {email}")
            return existing_user
        
        # Create new user - generate a username from email
        username = email.split('@')[0]
        
        # Make sure username is unique (append numbers if needed)
        base_username = username
        counter = 1
        while User.objects(username=username).first():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create and save the new user
        new_user = save_user(username, name, email)
        logging.debug(f"Created new user with email: {email}")
        return new_user
    except Exception as e:
        logging.error(f"Error in get_or_create_user_from_google: {str(e)}")
        # In this case, we need to raise the exception as the app cannot proceed without a user
        raise Exception(f"Error retrieving or creating user: {str(e)}")

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

def check_existing_vector_store(selected_file_ids, current_user):
    """
    Check if a vector store with the exact same files already exists.
    Returns (exists, vector_store) tuple where:
    - exists: boolean indicating if a match was found
    - vector_store: the matching VectorStore object if found, None otherwise
    """
    existing_vector_stores = VectorStore.objects(user=current_user)
    
    for vs in existing_vector_stores:
        try:
            vs_files = client.beta.vector_stores.files.list(vector_store_id=vs.vector_store_id)
            vs_file_ids = [file.id for file in vs_files.data]
            
            # Check if existing vector store has the exact same files
            if set(vs_file_ids) == set(selected_file_ids) and len(vs_file_ids) == len(selected_file_ids):
                logging.info(f'Found existing vector store "{vs.name}" with ID: {vs.vector_store_id}')
                return True, vs
        except Exception as e:
            logging.warning(f'Error checking files for vector store {vs.vector_store_id}: {str(e)}')
            continue
    
    return False, None

def delete_file(file_id, current_user):
    """Delete a file and cascade the deletion to associated vector stores and assistants.
    
    Args:
        file_id: The OpenAI file ID to delete
        current_user: The user requesting the deletion
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Find the file in the database
        file = File.objects(file_id=file_id, user=current_user).first()
        if not file:
            logging.error(f"File with ID {file_id} not found for user {current_user.username}")
            return False
            
        # Find vector stores containing this file
        vector_stores_to_check = VectorStore.objects(user=current_user)
        affected_vector_stores = []
        
        for vs in vector_stores_to_check:
            try:
                vs_files = client.beta.vector_stores.files.list(vector_store_id=vs.vector_store_id)
                vs_file_ids = [file.id for file in vs_files.data]
                
                if file_id in vs_file_ids:
                    affected_vector_stores.append(vs)
            except Exception as e:
                logging.error(f"Error checking files in vector store {vs.vector_store_id}: {str(e)}")
                continue
        
        # For each affected vector store, decide whether to delete it or remove the file
        for vs in affected_vector_stores:
            try:
                vs_files = client.beta.vector_stores.files.list(vector_store_id=vs.vector_store_id)
                vs_file_ids = [file.id for file in vs_files.data]
                
                # If this is the only file in the vector store, delete the entire vector store
                if len(vs_file_ids) == 1 and vs_file_ids[0] == file_id:
                    delete_vector_store(vs.vector_store_id, current_user)
                else:
                    # Otherwise, just remove this file from the vector store
                    client.beta.vector_stores.files.delete(
                        vector_store_id=vs.vector_store_id,
                        file_id=file_id
                    )
                    logging.info(f"Removed file {file_id} from vector store {vs.vector_store_id}")
            except Exception as e:
                logging.error(f"Error managing vector store {vs.vector_store_id} during file deletion: {str(e)}")
                continue
        
        # Delete the file from OpenAI
        try:
            response = client.files.delete(file_id)
            if not response.deleted:
                logging.error(f"OpenAI API reported file {file_id} was not deleted")
                return False
        except Exception as e:
            logging.error(f"Error deleting file {file_id} from OpenAI: {str(e)}")
            return False
            
        # Delete the file from our database
        file.delete()
        logging.info(f"File {file_id} successfully deleted")
        
        return True
    except Exception as e:
        logging.error(f"Error in delete_file for file {file_id}: {str(e)}")
        return False

def delete_vector_store(vector_store_id, current_user):
    """Delete a vector store and cascade the deletion to associated assistants and threads.
    
    Args:
        vector_store_id: The OpenAI vector store ID to delete
        current_user: The user requesting the deletion
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Find the vector store in the database
        vector_store = VectorStore.objects(vector_store_id=vector_store_id, user=current_user).first()
        if not vector_store:
            logging.error(f"Vector store with ID {vector_store_id} not found for user {current_user.username}")
            return False
            
        # Find and delete all associated assistants
        assistants = Assistant.objects(vector_store=vector_store, user=current_user)
        for assistant in assistants:
            delete_assistant(assistant.assistant_id, current_user)
            
        # Find and delete all threads associated with this vector store
        threads = Thread.objects(vector_store=vector_store, user=current_user)
        for thread in threads:
            delete_thread(thread.thread_id)
            
        # Delete the vector store from OpenAI
        try:
            response = client.beta.vector_stores.delete(vector_store_id)
            if not response.deleted:
                logging.error(f"OpenAI API reported vector store {vector_store_id} was not deleted")
                return False
        except Exception as e:
            logging.error(f"Error deleting vector store {vector_store_id} from OpenAI: {str(e)}")
            return False
            
        # Delete the vector store from our database
        vector_store.delete()
        logging.info(f"Vector store {vector_store_id} successfully deleted")
        
        return True
    except Exception as e:
        logging.error(f"Error in delete_vector_store for vector store {vector_store_id}: {str(e)}")
        return False

def delete_assistant(assistant_id, current_user):
    """Delete an assistant and all associated threads.
    
    Args:
        assistant_id: The OpenAI assistant ID to delete
        current_user: The user requesting the deletion
        
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    try:
        # Find the assistant in the database
        assistant = Assistant.objects(assistant_id=assistant_id, user=current_user).first()
        if not assistant:
            logging.error(f"Assistant with ID {assistant_id} not found for user {current_user.username}")
            return False
            
        # Find and delete all threads associated with this assistant
        threads = Thread.objects(assistant_id=assistant_id, user=current_user)
        for thread in threads:
            delete_thread(thread.thread_id)
            
        # Delete the assistant from OpenAI
        try:
            response = client.beta.assistants.delete(assistant_id)
            if not response.deleted:
                logging.error(f"OpenAI API reported assistant {assistant_id} was not deleted")
                return False
        except Exception as e:
            logging.error(f"Error deleting assistant {assistant_id} from OpenAI: {str(e)}")
            return False
            
        # Delete the assistant from our database
        assistant.delete()
        logging.info(f"Assistant {assistant_id} successfully deleted")
        
        return True
    except Exception as e:
        logging.error(f"Error in delete_assistant for assistant {assistant_id}: {str(e)}")
        return False
