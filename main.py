import os
from datetime import datetime
import time

import openai
import streamlit as st
from dotenv import load_dotenv
from mongoengine import connect

from models import Conversation, Message

load_dotenv()

client = openai.OpenAI()
model = 'gpt-4-0125-preview'

# Connect to MongoDB
connect('chatbot_db', host='localhost', port=27017)

# Initialize session state variables
if 'file_id_list' not in st.session_state:
    st.session_state.file_id_list = []
if 'start_chat' not in st.session_state:
    st.session_state.start_chat = False
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = None
if 'assistant_id' not in st.session_state:
    st.session_state.assistant_id = None

# Set up the frontend page
st.set_page_config(page_title='Study Buddy - Chat and Learn', page_icon=':books:')

def upload_to_openai(filepath):
    with open(filepath, 'rb') as file:
        uploaded_file = client.files.create(file=file.read(), purpose='assistants')
    return uploaded_file.id

def get_conversations():
    conversations = Conversation.objects().order_by("-updated_at")
    return conversations

def save_message(thread_id, role, content):
    conversation = Conversation.objects(conversation_id=thread_id).first()
    if not conversation:
        conversation = Conversation(conversation_id=thread_id, created_at=datetime.utcnow())
        conversation.save()
    message = Message(conversation=conversation, role=role, content=content, created_at=datetime.utcnow())
    message.save()

def get_messages(thread_id):
    conversation = Conversation.objects(conversation_id=thread_id).first()
    if conversation:
        messages = Message.objects(conversation=conversation)
        return messages
    return []

# File upload sidebar
uploaded_files = st.sidebar.file_uploader('Upload your study materials (PDF, TXT, etc.)', type=['pdf', 'txt'], key='file_upload', accept_multiple_files=True)

if st.sidebar.button('Upload File(s)'):
    if uploaded_files:
        uploaded_file_names = {f['name'] for f in st.session_state.file_id_list}
        for file in uploaded_files:
            if file.name not in uploaded_file_names:
                file_path = os.path.join(file.name)
                with open(file_path, 'wb') as file_obj:
                    file_obj.write(file.getbuffer())
                file_id = upload_to_openai(file_path)
                st.session_state.file_id_list.append({'name': file.name, 'id': file_id})
                st.sidebar.success(f'File "{file.name}" uploaded successfully.')
    else:
        st.sidebar.warning('Please select a file to upload.')

# Display uploaded file names
if st.session_state.file_id_list:
    st.sidebar.write('Uploaded Files:')
    for file in st.session_state.file_id_list:
        st.sidebar.write(f'- {file["name"]}')

# Start chat button
if st.sidebar.button('Start Chatting'):
    if st.session_state.file_id_list:
        st.session_state.start_chat = True

        # Check if thread_id exists in the session state
        if not st.session_state.thread_id:
            # Create the chat thread
            chat_thread = client.beta.threads.create()

            # Store the thread_id in the session state
            st.session_state.thread_id = chat_thread.id

            # Create the assistant
            assistant = client.beta.assistants.create(
                name='Study Buddy',
                instructions='''You are an AI study assistant called 'Study Buddy'. Your role is to help students learn and understand various concepts in their field of study.

When a student asks a question, provide clear and concise explanations of the relevant topics. Break down complex concepts into easily understandable parts. Share helpful resources, such as academic papers, tutorials, or online courses, that can further enhance their understanding.

Engage in meaningful discussions with the student to deepen their understanding of the subject matter. Encourage them to think critically and ask questions. Help them develop problem-solving skills and provide guidance on practical applications of the concepts they are learning.

Be friendly, supportive, and patient in your interactions. Motivate the student to stay curious and persistent in their learning journey. Foster a positive and encouraging learning environment.

Tailor your responses to the student's level of understanding and learning style. Adapt your explanations and examples to make the content more relatable and accessible.

Remember, your goal is to empower the student to grasp the material effectively and develop a strong foundation in their chosen field of study.''',
                tools=[{'type': 'retrieval'}],
                model=model,
                file_ids=[file['id'] for file in st.session_state.file_id_list]
            )

            # Store the assistant_id in the session state
            st.session_state.assistant_id = assistant.id

            st.success(f'Chat started. Thread ID: {st.session_state.thread_id}')
    else:
        st.sidebar.warning('Please upload at least one file to start chatting.')

# Main interface
st.title('Study Buddy')
st.write('Learn fast by chatting with your study materials')

# Display the list of conversations
conversations = get_conversations()
if conversations:
    st.subheader("Previous Conversations")
    for conversation in conversations:
        st.write(f"- {conversation.title} (Last updated: {conversation.updated_at})")
        if st.button(f"Resume Conversation: {conversation.title}", key=conversation.conversation_id):
            st.session_state.thread_id = conversation.conversation_id
            st.session_state.start_chat = True
            st.experimental_rerun()
else:
    st.info("No previous conversations found.")

# Check sessions
if st.session_state.start_chat:
    # Retrieve saved messages for the current conversation
    saved_messages = get_messages(st.session_state.thread_id)

    # Display existing messages
    for message in saved_messages:
        with st.chat_message(message.role):
            st.markdown(message.content)

    # User input
    prompt = st.chat_input('Ask a question or send a message')
    if prompt:
        # Display user's message on the screen
        with st.chat_message('user'):
            st.markdown(prompt)

        # Save user's message
        save_message(st.session_state.thread_id, "user", prompt)

        # Add user's message to the existing thread
        client.beta.threads.messages.create(
            thread_id=st.session_state.thread_id,
            role='user',
            content=prompt
        )

        # Create a run with additional instructions
        run = client.beta.threads.runs.create(
            thread_id=st.session_state.thread_id,
            assistant_id=st.session_state.assistant_id,
            instructions='Rely on the information from the provided files to answer questions. If you add any extra details, please format them in **bold** or __underlined__ text to make it clear.'
        )

        # Show a spinner while the assistant is generating a response
        with st.spinner('Generating response...'):
            while run.status != 'completed':
                time.sleep(1)
                run = client.beta.threads.runs.retrieve(
                    thread_id=st.session_state.thread_id,
                    run_id=run.id
                )

            # Retrieve and process assistant's messages for the current run
            messages = client.beta.threads.messages.list(thread_id=st.session_state.thread_id)
            assistant_messages_for_run = [
                message for message in messages
                if message.run_id == run.id and message.role == 'assistant'
            ]

            for message in assistant_messages_for_run:
                # Display assistant's message on the screen
                with st.chat_message('assistant'):
                    st.markdown(message.content[0].text.value, unsafe_allow_html=True)

                # Save assistant's message
                save_message(st.session_state.thread_id, "assistant", message.content[0].text.value)

    else:
        st.info('Type your question or message in the input box below to start chatting.')

else:
    st.info("Please upload at least one study material and click the 'Start Chatting' button to begin.")