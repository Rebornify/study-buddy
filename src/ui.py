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
    - **Start a New Study Session:** Upload your study materials and start a conversation with your assistant.
    - **Continue Learning:** Access and continue your previous study sessions.

    Use the sidebar to navigate between different sections and select your study sessions!
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
                    st.success(f'{total_files} new file(s) uploaded successfully!')
                    # Refresh file options after upload
                    st.rerun()
            except Exception as e:
                st.error(f'Error uploading files: {str(e)}')
            finally:
                progress_bar.empty()
                status_text.empty()
        else:
            st.warning('Please select at least one file to upload.')

    # Step 2: Select or Create Vector Store
    st.header("Step 2: Organize Your Study Materials")

    vector_stores = get_user_vector_stores(current_user)
    vector_store_options = [vs.name for vs in vector_stores]

    if vector_store_options:
        vector_store_selection = st.radio(
            "Would you like to use existing study materials or create new ones?",
            options=["Use Existing", "Create New"]
        )
    else:
        st.info("You'll need to create a new collection of study materials.")
        vector_store_selection = "Create New"

    if vector_store_selection == "Use Existing":
        selected_vector_store_name = st.selectbox(
            "Select your study materials:",
            options=vector_store_options
        )
        if selected_vector_store_name:
            selected_vector_store = VectorStore.objects(name=selected_vector_store_name, user=current_user).first()
            if selected_vector_store:
                st.session_state.vector_store_id = selected_vector_store.vector_store_id
                st.success(f'Selected materials: {selected_vector_store.name}')
            else:
                st.error('Selected study materials not found.')
    else:  # Create New
        vector_store_name = st.text_input(
            'Name for your study materials:',
            placeholder='e.g., Physics Chapter 1, Math Notes, etc.'
        )
        if st.button('Create Collection', help='Create a new collection of study materials'):
            if not vector_store_name.strip():
                st.warning('Please enter a name for your study materials.')
            elif selected_files:
                # Get File IDs of selected files
                selected_file_objs = File.objects(name__in=selected_files, user=current_user)
                selected_file_ids = [f.file_id for f in selected_file_objs]

                # Create vector store and associate files
                vector_store_id = create_vector_store(vector_store_name, selected_file_ids, current_user)
                if vector_store_id:
                    st.session_state.vector_store_id = vector_store_id
                    st.success(f'Study materials "{vector_store_name}" created successfully.')
                    st.rerun()
                else:
                    st.error('Failed to create study materials.')
            else:
                st.warning('Please select at least one file above.')

    # Step 3: Select or Create Assistant
    st.header("Step 3: Choose Your Study Assistant")

    assistants = get_user_assistants(current_user)
    assistant_options = [assistant.name for assistant in assistants]

    if assistant_options:
        assistant_selection = st.radio(
            "Would you like to use an existing assistant or create a new one?",
            options=["Use Existing", "Create New"]
        )
    else:
        st.info("You'll need to create a new study assistant.")
        assistant_selection = "Create New"

    if assistant_selection == "Use Existing":
        selected_assistant_name = st.selectbox(
            "Select your study assistant:",
            options=assistant_options
        )
        if selected_assistant_name:
            selected_assistant = Assistant.objects(name=selected_assistant_name, user=current_user).first()
            if selected_assistant:
                st.session_state.assistant_id = selected_assistant.assistant_id
                if selected_assistant.vector_store:
                    st.info(f"This assistant was last used with: {selected_assistant.vector_store.name}")
            else:
                st.error('Selected assistant not found.')
    else:  # Create New
        assistant_name = st.text_input(
            'Name for your study assistant:',
            placeholder='e.g., Physics Tutor, Math Helper, etc.'
        )
        if st.button('Create Assistant', help='Create a new study assistant'):
            if not assistant_name.strip():
                st.warning('Please enter a name for your assistant.')
            elif not st.session_state.get('vector_store_id'):
                st.warning('Please select or create study materials first.')
            else:
                try:
                    assistant_id = create_assistant(assistant_name, st.session_state.vector_store_id, current_user)
                    if assistant_id:
                        st.session_state.assistant_id = assistant_id
                        st.success('Assistant created successfully!')
                        st.rerun()
                except Exception as e:
                    st.error(f'Error creating assistant: {str(e)}')

    # Step 4: Start Your Study Session
    st.header("Step 4: Start Your Study Session")
    
    # Show helpful context about what's selected
    if st.session_state.get('vector_store_id'):
        vs = VectorStore.objects(vector_store_id=st.session_state.vector_store_id).first()
        if vs:
            st.info(f"📚 Study Materials: {vs.name}")
    
    if st.session_state.get('assistant_id'):
        asst = Assistant.objects(assistant_id=st.session_state.assistant_id).first()
        if asst:
            st.info(f"🤖 Study Assistant: {asst.name}")
    
    session_title = st.text_input('Title for this study session:', 'New study session')
    start_disabled = not (st.session_state.get('assistant_id') and st.session_state.get('vector_store_id'))
    
    if st.button('Start Session', disabled=start_disabled):
        try:
            create_thread(
                title=session_title,
                assistant_id=st.session_state.assistant_id,
                vector_store_id=st.session_state.vector_store_id,
                user=current_user
            )
            st.success('Study session started successfully! You can now interact with your assistant from the Previous Sessions section.')
        except Exception as e:
            logging.error(f"Error creating study session: {str(e)}")
            st.error(f'Error creating study session: {str(e)}')

def select_thread_sidebar(current_user):
    """Display study session selection in the sidebar."""
    threads = get_threads(current_user)
    if threads:
        st.sidebar.header("Your Study Sessions")
        selected_thread_id = st.sidebar.selectbox(
            "Choose a session:",
            options=[thread.thread_id for thread in threads],
            format_func=lambda x: next((thread.title for thread in threads if thread.thread_id == x), "Untitled Session")
        )

        if st.sidebar.button("Delete Selected Session"):
            if delete_thread(selected_thread_id):
                st.sidebar.success("Study session deleted successfully.")
                st.session_state.thread_id = None
            else:
                st.sidebar.error("Failed to delete the study session.")

        st.session_state.thread_id = selected_thread_id
        return Thread.objects(thread_id=selected_thread_id).first()
    return None

def display_thread(selected_thread):
    """Display the selected study session and chat interface."""
    st.title(f"Study Session: {selected_thread.title}")
    handle_chat_interface(selected_thread)

def handle_chat_interface(selected_thread):
    """Handle the chat interface for the selected study session."""
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