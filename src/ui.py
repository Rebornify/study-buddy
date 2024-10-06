import logging
from datetime import datetime, timezone

import streamlit as st

from config import client
from models import Thread
from utils import (
    create_assistant,
    create_thread,
    delete_thread,
    get_messages,
    get_threads,
    get_vector_store_files,
    handle_file_upload,
    save_message
)

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

            # Iterate over the annotations and add footnotes
            for index, annotation in enumerate(annotations, start=1):
                # Replace the text with a footnote
                message_content.value = message_content.value.replace(
                    annotation.text, f' <sup>[{index}]</sup>'
                )

            # Display the modified assistant message
            with st.chat_message('assistant'):
                st.markdown(message_content.value, unsafe_allow_html=True)

            # Save the modified message
            save_message(st.session_state.thread_id, 'assistant', message_content.value)
        except Exception as e:
            st.error(f"Failed to retrieve assistant message: {str(e)}")
            logging.error(f"Failed to retrieve assistant message: {str(e)}")
