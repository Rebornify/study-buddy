import logging

import streamlit as st

from config import client
from models import Thread, File, VectorStore, Assistant
from utils import (
    create_vector_store,
    create_assistant,
    create_thread,
    delete_thread,
    get_messages,
    get_threads,
    get_user_files,
    get_user_vector_stores,
    get_user_assistants,
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

    # Step 1: Select or Upload Files
    st.header("Step 1: Select or Upload Files")

    # Display user's uploaded files
    user_files = get_user_files(current_user)
    file_options = [f.name for f in user_files]

    selected_files = st.multiselect(
        "Select from your uploaded files:",
        options=file_options
    )

    # Allow user to upload new files
    st.write("Or upload new files:")
    uploaded_files = st.file_uploader(
        'Upload your study materials (.pdf, .txt, etc.)',
        type=['pdf', 'txt'],
        key='file_upload',
        accept_multiple_files=True
    )

    if st.button('Upload File(s)'):
        if uploaded_files:
            handle_file_upload(uploaded_files, current_user)
            # Refresh file options after upload
            st.rerun()
        else:
            st.warning('Please select at least one file to upload.')

    # Step 2: Select Existing Vector Store or Create New Vector Store
    st.header("Step 2: Select Existing Vector Store or Create New Vector Store")

    vector_stores = get_user_vector_stores(current_user)
    vector_store_options = [vs.name for vs in vector_stores]

    if vector_store_options:
        vector_store_selection = st.radio(
            "Would you like to select an existing vector store or create a new one?",
            options=["Select Existing Vector Store", "Create New Vector Store"]
        )
    else:
        st.info("You have no existing vector stores. Please create a new vector store.")
        vector_store_selection = "Create New Vector Store"

    if vector_store_selection == "Select Existing Vector Store":
        selected_vector_store_name = st.selectbox(
            "Select a vector store:",
            options=vector_store_options
        )
        if selected_vector_store_name:
            selected_vector_store = VectorStore.objects(name=selected_vector_store_name, user=current_user).first()
            if selected_vector_store:
                st.session_state.vector_store_id = selected_vector_store.vector_store_id
                st.success(f'Selected vector store: {selected_vector_store.name}')
            else:
                st.error('Selected vector store not found.')
        else:
            st.warning('No vector stores available to select.')
    elif vector_store_selection == "Create New Vector Store":
        vector_store_name = st.text_input(
            'Enter a name for the new vector store:',
            placeholder='e.g., My Study Materials'
        )
        if st.button('Create Vector Store'):
            if not vector_store_name.strip():
                st.warning('Please enter a name for the new vector store.')
            elif selected_files:
                # Get File IDs of selected files
                selected_file_objs = File.objects(name__in=selected_files, user=current_user)
                selected_file_ids = [f.file_id for f in selected_file_objs]

                # Create vector store and associate files
                vector_store_id = create_vector_store(vector_store_name, selected_file_ids, current_user)
                if vector_store_id:
                    st.session_state.vector_store_id = vector_store_id
                    st.success(f'Vector store "{vector_store_name}" created successfully.')
                    st.rerun()  # Refresh the app to update the UI
                else:
                    st.error('Failed to create vector store.')
            else:
                st.warning('Please select at least one file to associate with the vector store.')

    # Step 3: Select Existing Assistant or Create New Assistant
    st.header("Step 3: Select Existing Assistant or Create New Assistant")

    assistants = get_user_assistants(current_user)
    assistant_options = [assistant.name for assistant in assistants]

    if assistant_options:
        assistant_selection = st.radio(
            "Would you like to select an existing assistant or create a new one?",
            options=["Select Existing Assistant", "Create New Assistant"]
        )
    else:
        st.info("You have no existing assistants. Please create a new assistant.")
        assistant_selection = "Create New Assistant"

    if assistant_selection == "Select Existing Assistant":
        selected_assistant_name = st.selectbox(
            "Select an assistant:",
            options=assistant_options
        )
        if selected_assistant_name:
            selected_assistant = Assistant.objects(name=selected_assistant_name, user=current_user).first()
            if selected_assistant:
                st.session_state.assistant_id = selected_assistant.assistant_id
                st.session_state.vector_store_id = selected_assistant.vector_store.vector_store_id
                st.success(f'Selected assistant: {selected_assistant.name}')
                st.info(f"This assistant is associated with vector store: {selected_assistant.vector_store.name}")
            else:
                st.error('Selected assistant not found.')
        else:
            st.warning('No assistants available to select.')

    elif assistant_selection == "Create New Assistant":
        assistant_name = st.text_input(
            'Enter a name for the new assistant:',
            placeholder='e.g., My Study Assistant'
        )
        if st.button('Create Assistant'):
            if not assistant_name.strip():
                st.warning('Please enter a name for the new assistant.')
            elif not st.session_state.get('vector_store_id'):
                st.warning('Please select or create a vector store before creating an assistant.')
            else:
                try:
                    # Create assistant and save to database
                    assistant_id = create_assistant(assistant_name, st.session_state.vector_store_id, current_user)
                    st.session_state.assistant_id = assistant_id
                    st.success('Assistant created successfully!')
                    st.rerun()  # Refresh the app to update the UI
                except Exception as e:
                    st.error(f'Error creating assistant: {str(e)}')

    # Step 4: Start Chatting
    st.header("Step 4: Start Chatting")
    thread_title = st.text_input('Enter a title for this thread:', 'New thread')
    if st.button('Start Chat'):
        if not st.session_state.get('assistant_id'):
            st.warning('Please select or create an assistant before proceeding.')
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
                logging.error(f"Error creating thread: {str(e)}")
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
