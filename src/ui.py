import logging
from typing import Optional, List, Dict, Any, Tuple, Union
from datetime import datetime, timezone, timedelta
import time

import streamlit as st
import openai

from config import client
from models import Thread, File, VectorStore, Assistant, User
from utils import (
    create_vector_store,
    create_assistant,
    create_thread,
    delete_thread,
    get_messages,
    get_threads,
    get_user_files,
    get_user_vector_stores,
    handle_file_upload,
    save_message,
    get_vector_store_files,
    check_existing_vector_store,
    delete_file,
    delete_vector_store
)
from openai.types.beta.assistant_stream_event import ThreadMessageDelta
from openai.types.beta.threads.text_delta_block import TextDeltaBlock

def ensure_navigation_state(page: str) -> None:
    """
    Helper function to set the current navigation page in session state.
    
    Args:
        page: The name of the page to navigate to
        
    Returns:
        None
    """
    st.session_state.current_page = page

def display_home(current_user: User) -> None:
    """
    Display the home page of the application.
    
    This function renders the welcome message and information about the application
    features on the home page.
    
    Args:
        current_user: The currently authenticated user
        
    Returns:
        None
    """
    st.title("Welcome to Study Buddy")
    st.write("""
    **Study Buddy** is your personal AI assistant to help you learn and understand various concepts.

    **What you can do:**
    - **Start a New Study Session:** Upload your study materials and start a conversation with your assistant.
    - **Continue Learning:** Access and continue your previous study sessions.
    - **Manage Files:** Clean up your files and study collections.

    Use the sidebar to navigate between different sections and select your study sessions!
    """)

def create_new_chat(current_user: User) -> None:
    """
    Create a new chat session with the AI assistant.
    
    This function handles the UI for creating a new study session, including
    file upload, vector store and assistant creation, and thread initialization.
    
    Args:
        current_user: The currently authenticated user
        
    Returns:
        None
    """
    st.title("Start a New Study Session")
    
    # Display any persistent success messages from previous actions
    if st.session_state.get('persistent_success_message'):
        st.success(st.session_state.get('persistent_success_message'))
        # Clear after displaying once
        st.session_state.pop('persistent_success_message')

    # Step 1: Select or Upload Files
    st.header("Step 1: Select Your Study Materials")

    # Display user's uploaded files
    user_files = get_user_files(current_user)
    file_options = [f.name for f in user_files]

    selected_files = st.multiselect(
        "Select from your uploaded files:",
        options=file_options
    )

    # Display summary of selected files
    if selected_files:
        st.success(f"Selected {len(selected_files)} file(s)")
        with st.expander("Selected files", expanded=True):
            for file_name in selected_files:
                st.write(f"- {file_name}")
    
    # Allow user to upload new files
    st.write("Or upload new files:")
    
    # Initialize session state for tracking uploaded files if not exists
    if 'uploaded_file_names' not in st.session_state:
        st.session_state.uploaded_file_names = set()
    
    uploaded_files = st.file_uploader(
        'Upload your study materials (.pdf, .txt, etc.)',
        type=['pdf', 'txt'],
        key='file_upload',
        accept_multiple_files=True
    )

    if st.button('Upload File(s)'):
        if uploaded_files:
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            try:
                # Filter out already uploaded files
                new_files = [f for f in uploaded_files if f.name not in st.session_state.uploaded_file_names]
                
                if not new_files:
                    st.info('All selected files have already been uploaded.')
                else:
                    total_files = len(new_files)
                    for idx, file in enumerate(new_files, 1):
                        status_text.text(f'Processing file {idx}/{total_files}: {file.name}')
                        progress_bar.progress(idx/total_files)
                        handle_file_upload([file], current_user)
                        st.session_state.uploaded_file_names.add(file.name)
                    
                    progress_bar.progress(1.0)
                    status_text.text('All files processed successfully!')
                    # Store success message in session state instead of displaying directly
                    st.session_state.persistent_success_message = f'{total_files} new file(s) uploaded successfully!'
                    # Save current navigation state before rerun
                    ensure_navigation_state("New Study Session")
                    st.rerun()
            except Exception as e:
                st.error(f'Error uploading files: {str(e)}')
            finally:
                progress_bar.empty()
                status_text.empty()
        else:
            st.warning('Please select at least one file to upload.')

    # Step 2: Create or Select Study Collection
    st.header("Step 2: Organize Your Study Materials")

    # Get existing vector stores for reuse
    vector_stores = get_user_vector_stores(current_user)
    vector_store_options = [vs.name for vs in vector_stores]
    
    # Allow selection from existing collections or create a new one
    if vector_store_options:
        # Check if we need to force "Use Existing" due to a reused vector store
        if st.session_state.get('force_use_existing', False):
            collection_selection = "Use Existing"
            # Reset the flag after using it
            st.session_state.force_use_existing = False
        else:
            collection_selection = st.radio(
                "Would you like to use an existing collection or create a new one?",
                options=["Use Existing", "Create New"]
            )
    else:
        st.info("You'll need to create a new collection for your study materials.")
        collection_selection = "Create New"

    # Use existing collection
    if collection_selection == "Use Existing":
        # Pre-select the collection if we just reused one
        default_index = 0
        if st.session_state.get('last_used_collection') in vector_store_options:
            default_index = vector_store_options.index(st.session_state.get('last_used_collection'))
        
        selected_collection = st.selectbox(
            "Select a collection of study materials:",
            options=vector_store_options,
            index=default_index
        )
        if selected_collection:
            selected_vs = VectorStore.objects(name=selected_collection, user=current_user).first()
            if selected_vs:
                st.session_state.vector_store_id = selected_vs.vector_store_id
                
                # Get file information first to include in consolidated message
                file_count = 0
                file_list = []
                try:
                    files = get_vector_store_files(selected_vs.vector_store_id)
                    file_count = len(files)
                    file_list = files
                except Exception as e:
                    logging.error(f"Error fetching vector store files: {str(e)}")
                
                # Check for existing assistant for this vector store
                existing_assistant = Assistant.objects(vector_store=selected_vs, user=current_user).first()
                if existing_assistant:
                    st.session_state.assistant_id = existing_assistant.assistant_id
                    
                    # Show a single consolidated info message with file count
                    st.info(f"📚 Study Collection: **{selected_collection}** with assistant ready to use ({file_count} file{'s' if file_count != 1 else ''})")
                else:
                    # No assistant exists yet
                    st.info(f"📚 Study Collection: **{selected_collection}** selected ({file_count} file{'s' if file_count != 1 else ''})")
                    # We'll create the assistant in step 3
                
                # Show files associated with this collection in a more compact way
                if file_list:
                    with st.expander("View files in this collection"):
                        for file in file_list:
                            st.write(f"- {file['name']}")
    # Create new collection
    else:
        vector_store_name = st.text_input(
            'Name for your study materials:',
            placeholder='e.g., Physics Chapter 1, Math Notes, etc.'
        )
        if st.button('Create Collection'):
            if not vector_store_name.strip():
                st.warning('Please enter a name for your study materials.')
            elif selected_files:
                # Get File IDs of selected files
                selected_file_objs = File.objects(name__in=selected_files, user=current_user)
                selected_file_ids = [f.file_id for f in selected_file_objs]

                # First check if a collection with the same files already exists
                exists, existing_vs = check_existing_vector_store(selected_file_ids, current_user)
                
                if exists and existing_vs:
                    # Use the existing vector store instead of creating a new one
                    st.session_state.vector_store_id = existing_vs.vector_store_id
                    st.info(f"Using existing collection '{existing_vs.name}' with the same files instead of creating a duplicate.")
                    
                    # Force the UI to "Use Existing" on next rerun
                    st.session_state.force_use_existing = True
                    st.session_state.last_used_collection = existing_vs.name
                    
                    # Check for existing assistant for this vector store
                    existing_assistant = Assistant.objects(vector_store=existing_vs, user=current_user).first()
                    if existing_assistant:
                        st.session_state.assistant_id = existing_assistant.assistant_id
                        # Store success message in session state instead of displaying directly
                        st.session_state.persistent_success_message = 'Existing study materials and assistant ready to use!'
                    else:
                        # Create assistant if it doesn't exist
                        assistant_id = create_assistant("", existing_vs.vector_store_id, current_user)
                        if assistant_id:
                            st.session_state.assistant_id = assistant_id
                            # Store success message in session state instead of displaying directly
                            st.session_state.persistent_success_message = 'Existing study materials connected to a new assistant!'
                        else:
                            st.error('Failed to set up assistant for your study materials.')
                    
                    # Save current navigation state before rerun
                    ensure_navigation_state("New Study Session")
                    st.rerun()
                else:
                    # Create new vector store and associate files
                    vector_store_id = create_vector_store(vector_store_name, selected_file_ids, current_user)
                    if vector_store_id:
                        st.session_state.vector_store_id = vector_store_id
                        
                        # Automatically create assistant for this vector store
                        assistant_id = create_assistant("", vector_store_id, current_user)
                        if assistant_id:
                            st.session_state.assistant_id = assistant_id
                            # Store success message in session state instead of displaying directly
                            st.session_state.persistent_success_message = 'Study materials and assistant created and ready to use!'
                        else:
                            st.error('Failed to set up assistant for your study materials.')
                        # Save current navigation state before rerun
                        ensure_navigation_state("New Study Session")
                        st.rerun()
                    else:
                        st.error('Failed to create study materials.')
            else:
                st.warning('Please select at least one file above.')

    # Step 3: Start Your Study Session (simplified - no separate assistant creation step)
    st.header("Step 3: Start Your Study Session")
    
    # Show helpful context about what's selected
    if st.session_state.get('vector_store_id'):
        vs = VectorStore.objects(vector_store_id=st.session_state.vector_store_id).first()
        if vs:
            st.info(f"📚 Study Materials: {vs.name}")
    
    session_title = st.text_input('Title for this study session:', 'New study session')
    
    # Check if both vector store and assistant are ready
    start_disabled = not (st.session_state.get('assistant_id') and st.session_state.get('vector_store_id'))
    
    if start_disabled:
        if st.session_state.get('vector_store_id') and not st.session_state.get('assistant_id'):
            # Create an assistant automatically if vector store exists but no assistant
            vector_store_id = st.session_state.get('vector_store_id')
            vs = VectorStore.objects(vector_store_id=vector_store_id).first()
            
            if vs:
                st.info(f"Creating assistant for {vs.name}...")
                try:
                    assistant_id = create_assistant("", vector_store_id, current_user)
                    if assistant_id:
                        st.session_state.assistant_id = assistant_id
                        start_disabled = False
                        # Save current navigation state before rerun
                        ensure_navigation_state("New Study Session")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error creating assistant: {str(e)}")
    
    if st.button('Start Session', disabled=start_disabled):
        try:
            create_thread(
                title=session_title,
                assistant_id=st.session_state.assistant_id,
                vector_store_id=st.session_state.vector_store_id,
                user=current_user
            )
            # Store success message in session state instead of displaying directly
            st.session_state.persistent_success_message = 'Study session started successfully! You can now interact with your assistant from the Previous Sessions section.'
            # Add a flag to redirect to the Previous Sessions page
            st.session_state.redirect_to_sessions = True
            # Make sure the navigation selection matches the redirect
            ensure_navigation_state("Previous Sessions")
            st.rerun()
        except Exception as e:
            logging.error(f"Error creating study session: {str(e)}")
            st.error(f'Error creating study session: {str(e)}')

def select_thread_sidebar(current_user: User) -> Optional[Thread]:
    """
    Display study session selection in the sidebar.
    
    This function shows a dropdown of the user's previous threads in the sidebar
    for navigation between sessions.
    
    Args:
        current_user: The currently authenticated user
        
    Returns:
        Thread: The selected thread object or None if no threads exist
    """
    threads = get_threads(current_user)
    if threads:
        st.sidebar.header("Your Study Sessions")
        
        # Get index for currently selected thread if it exists
        default_index = 0
        thread_ids = [thread.thread_id for thread in threads]
        previous_thread_id = st.session_state.get('thread_id')
        
        if previous_thread_id in thread_ids:
            default_index = thread_ids.index(previous_thread_id)
        
        selected_thread_id = st.sidebar.selectbox(
            "Choose a session:",
            options=thread_ids,
            format_func=lambda x: next((thread.title for thread in threads if thread.thread_id == x), "Untitled Session"),
            index=default_index,
            key="thread_selector"
        )
        
        # Update session state and trigger navigation if selection changed
        if selected_thread_id != previous_thread_id:
            st.session_state.thread_id = selected_thread_id
            ensure_navigation_state("Previous Sessions")
            st.rerun()
        
        return Thread.objects(thread_id=selected_thread_id).first()
    return None

def display_thread(selected_thread: Thread) -> None:
    """
    Display a selected conversation thread and the chat interface.
    
    This function shows the title of the selected thread and renders
    the chat interface for the conversation.
    
    Args:
        selected_thread: The Thread object to display
        
    Returns:
        None
    """
    # Display the thread title and delete button in the main area
    col1, col2 = st.columns([5, 1])
    with col1:
        st.title(selected_thread.title)
    with col2:
        if st.button("Delete Thread", type="primary", use_container_width=True):
            # Set confirmation state for this specific thread
            st.session_state[f"confirm_delete_thread_{selected_thread.thread_id}"] = True
            st.rerun()
    
    # Handle delete confirmation
    if st.session_state.get(f"confirm_delete_thread_{selected_thread.thread_id}", False):
        st.warning("Are you sure you want to delete this study session? This action cannot be undone.")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Yes, Delete", type="primary"):
                if delete_thread(selected_thread.thread_id):
                    st.session_state.thread_id = None
                    st.session_state.pop(f"confirm_delete_thread_{selected_thread.thread_id}", None)
                    st.success("Study session deleted successfully.")
                    ensure_navigation_state("Previous Sessions")
                    st.rerun()
                else:
                    st.error("Failed to delete the study session.")
                    st.session_state.pop(f"confirm_delete_thread_{selected_thread.thread_id}", None)
                    st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.pop(f"confirm_delete_thread_{selected_thread.thread_id}", None)
                st.rerun()
    
    # Render the chat interface
    handle_chat_interface(selected_thread)

def handle_chat_interface(selected_thread: Thread) -> None:
    """
    Handle the chat interface for the selected study session.
    
    This function manages the chat UI, handling message display,
    user input, OpenAI communication, and response streaming.
    
    Args:
        selected_thread: The Thread object for the current conversation
        
    Returns:
        None
    """
    if not selected_thread:
        st.info('No study session selected. Start a new session from the New Study Session tab.')
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
        except (openai.APIError, openai.APIConnectionError, openai.RateLimitError) as e:
            if isinstance(e, openai.APIError):
                st.error(f"OpenAI API returned an error: {str(e)}")
                logging.error(f"OpenAI API Error: {str(e)}")
            elif isinstance(e, openai.APIConnectionError):
                st.error("Connection error. Please check your internet connection and try again.")
                logging.error(f"OpenAI API Connection Error: {str(e)}")
            elif isinstance(e, openai.RateLimitError):
                st.error("Too many requests. Please wait a moment and try again.")
                logging.error(f"OpenAI Rate Limit Error: {str(e)}")
            return
        except Exception as e:
            st.error(f"Failed to send message to OpenAI: {str(e)}")
            logging.error(f"Failed to send message to OpenAI: {str(e)}")
            return

        # Stream the assistant's response
        with st.chat_message('assistant'):
            streaming_display = st.empty()  # Container for displaying streaming content
            assistant_response = ""         # Accumulates the complete response
            
            try:
                stream = client.beta.threads.runs.create(
                    thread_id=st.session_state.thread_id,
                    assistant_id=st.session_state.assistant_id,
                    stream=True
                )
                
                for event in stream:
                    if isinstance(event, ThreadMessageDelta):
                        if isinstance(event.data.delta.content[0], TextDeltaBlock):
                            streaming_display.empty()
                            assistant_response += event.data.delta.content[0].text.value
                            streaming_display.markdown(assistant_response)
                
                # After streaming completes, handle annotations
                messages = client.beta.threads.messages.list(
                    thread_id=st.session_state.thread_id
                )
                
                # Extract the message content
                message_content = messages.data[0].content[0].text
                annotations = message_content.annotations

                # Iterate over the annotations and add footnotes
                for index, annotation in enumerate(annotations, start=1):
                    # Replace the text with a footnote
                    assistant_response = assistant_response.replace(
                        annotation.text, f' <sup>[{index}]</sup>'
                    )
                
                # Update the display with annotations
                streaming_display.markdown(assistant_response, unsafe_allow_html=True)

                # Save the final message with annotations
                save_message(st.session_state.thread_id, 'assistant', assistant_response)
                
            except (openai.APIError, openai.APIConnectionError, openai.RateLimitError) as e:
                if isinstance(e, openai.APIError):
                    st.error(f"OpenAI API returned an error: {str(e)}")
                    logging.error(f"OpenAI API Error during streaming: {str(e)}")
                elif isinstance(e, openai.APIConnectionError):
                    st.error("Connection error. Please check your internet connection and try again.")
                    logging.error(f"OpenAI API Connection Error during streaming: {str(e)}")
                elif isinstance(e, openai.RateLimitError):
                    st.error("Too many requests. Please wait a moment and try again.")
                    logging.error(f"OpenAI Rate Limit Error during streaming: {str(e)}")
            except Exception as e:
                st.error(f"Error during streaming: {str(e)}")
                logging.error(f"Error during streaming: {str(e)}")

def manage_files(current_user: User) -> None:
    """
    Allow users to manage their files, vector stores, and assistants.
    
    This function provides a UI for managing study materials, including
    file deletion, vector store management, and assistant settings.
    
    Args:
        current_user: The currently authenticated user
        
    Returns:
        None
    """
    st.title("Manage Your Files")
    
    # Display any success or error messages
    if 'manage_success_message' in st.session_state:
        st.success(st.session_state.manage_success_message)
        del st.session_state.manage_success_message
    
    if 'manage_error_message' in st.session_state:
        st.error(st.session_state.manage_error_message)
        del st.session_state.manage_error_message
    
    st.write("""
    Here you can manage your study materials, collections, and assistants.
    
    **Warning:** Deleting a file or collection will cascade to delete all dependent resources.
    - Deleting a file will remove it from all collections using it
    - Deleting a collection will also delete its assistant and all associated threads
    - A collection will be automatically deleted if its last file is removed
    """)
    
    # -----------------------------
    # File Management Section
    # -----------------------------
    st.header("Your Files")
    
    user_files = get_user_files(current_user)
    
    if not user_files:
        st.info("You haven't uploaded any files yet.")
    else:
        # Create a dataframe to display files in a table
        file_data = []
        for file in user_files:
            file_data.append({
                "Name": file.name,
                "Upload Date": file.created_at.strftime("%Y-%m-%d %H:%M"),
                "ID": file.file_id
            })
        
        st.dataframe(file_data, use_container_width=True, hide_index=True)
        
        # File deletion section
        st.subheader("Delete Files")
        st.warning("Deleting a file will remove it from all collections using it.")
        
        file_options = {file.name: file.file_id for file in user_files}
        selected_file_to_delete = st.selectbox(
            "Select a file to delete:",
            options=list(file_options.keys()),
            key="file_delete_select"
        )
        
        if st.button("Delete Selected File", key="delete_file_button"):
            file_id = file_options[selected_file_to_delete]
            # Set a confirmation state for this specific file
            confirm_key = f"confirm_delete_file_{file_id}"
            st.session_state[confirm_key] = True
            st.rerun()
        
        # If we're in confirmation mode for this file
        file_id = file_options.get(selected_file_to_delete)
        if file_id:
            confirm_key = f"confirm_delete_file_{file_id}"
            if st.session_state.get(confirm_key, False):
                st.warning(f"Are you sure you want to delete file '{selected_file_to_delete}'? This may affect collections using this file.")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Yes, Delete File", key="confirm_file_yes", type="primary"):
                        success = delete_file(file_id, current_user)
                        if success:
                            # Clear the confirmation state
                            st.session_state.pop(confirm_key, None)
                            st.session_state.manage_success_message = f"File '{selected_file_to_delete}' deleted successfully."
                            st.rerun()
                        else:
                            # Clear the confirmation state
                            st.session_state.pop(confirm_key, None)
                            st.session_state.manage_error_message = f"Failed to delete file '{selected_file_to_delete}'."
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="confirm_file_no"):
                        # Clear the confirmation state
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
    
    # -----------------------------
    # Vector Store Management Section
    # -----------------------------
    st.header("Your Collections")
    
    vector_stores = get_user_vector_stores(current_user)
    
    if not vector_stores:
        st.info("You haven't created any collections yet.")
    else:
        # Create a dataframe to display vector stores in a table
        vs_data = []
        for vs in vector_stores:
            vs_data.append({
                "Name": vs.name,
                "Created": vs.created_at.strftime("%Y-%m-%d %H:%M"),
                "Last Updated": vs.updated_at.strftime("%Y-%m-%d %H:%M"),
                "ID": vs.vector_store_id
            })
        
        st.dataframe(vs_data, use_container_width=True, hide_index=True)
        
        # Collection details and deletion section
        st.subheader("Collection Details & Deletion")
        st.warning("Deleting a collection will also delete its assistant and all chat threads.")
        
        vs_options = {vs.name: vs.vector_store_id for vs in vector_stores}
        selected_vs = st.selectbox(
            "Select a collection:",
            options=list(vs_options.keys()),
            key="vs_select"
        )
        
        if selected_vs:
            vs_id = vs_options[selected_vs]
            
            # Display files in the selected vector store
            try:
                vs_files = get_vector_store_files(vs_id)
                
                if vs_files:
                    st.write("Files in this collection:")
                    for file in vs_files:
                        st.write(f"- {file['name']}")
                else:
                    st.info("This collection has no files.")
            except Exception as e:
                st.error(f"Error loading collection details: {str(e)}")
            
            # Delete the vector store
            if st.button("Delete This Collection", key="delete_vs_button"):
                # Set a confirmation state for this specific collection
                confirm_key = f"confirm_delete_{vs_id}"
                st.session_state[confirm_key] = True
                st.rerun()
            
            # If we're in confirmation mode for this collection
            confirm_key = f"confirm_delete_{vs_id}"
            if st.session_state.get(confirm_key, False):
                st.warning(f"Are you sure you want to delete collection '{selected_vs}'? This will also delete its assistant and all chat threads.")
                
                col1, col2 = st.columns([1, 1])
                with col1:
                    if st.button("Yes, Delete Collection", key="confirm_yes", type="primary"):
                        success = delete_vector_store(vs_id, current_user)
                        if success:
                            # Clear the confirmation state
                            st.session_state.pop(confirm_key, None)
                            st.session_state.manage_success_message = f"Collection '{selected_vs}' deleted successfully."
                            st.rerun()
                        else:
                            # Clear the confirmation state
                            st.session_state.pop(confirm_key, None)
                            st.session_state.manage_error_message = f"Failed to delete collection '{selected_vs}'."
                            st.rerun()
                with col2:
                    if st.button("Cancel", key="confirm_no"):
                        # Clear the confirmation state
                        st.session_state.pop(confirm_key, None)
                        st.rerun()
