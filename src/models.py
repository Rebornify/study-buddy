from datetime import datetime
from typing import Optional

from mongoengine import Document, StringField, EmailField, ReferenceField, DateTimeField, CASCADE

class User(Document):
    """
    User model representing a registered user in the system.
    
    Attributes:
        username: Unique username for the user
        name: Full name of the user
        email: Unique email address of the user
        created_at: Timestamp when the user was created
    """
    username = StringField(required=True, unique=True)
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    created_at = DateTimeField(default=datetime.now)

class File(Document):
    """
    File model representing a file uploaded by a user.
    
    Attributes:
        file_id: Unique identifier for the file in OpenAI
        name: Name of the file
        user: Reference to the user who uploaded the file
        created_at: Timestamp when the file was uploaded
    """
    file_id = StringField(required=True, unique=True)
    name = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)

class VectorStore(Document):
    """
    VectorStore model representing a collection of files for vector-based search.
    
    Attributes:
        vector_store_id: Unique identifier for the vector store in OpenAI
        name: Name of the vector store
        user: Reference to the user who created the vector store
        created_at: Timestamp when the vector store was created
        updated_at: Timestamp when the vector store was last updated
    """
    vector_store_id = StringField(required=True, unique=True)
    name = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Assistant(Document):
    """
    Assistant model representing an AI assistant created for a specific vector store.
    
    Attributes:
        assistant_id: Unique identifier for the assistant in OpenAI
        name: Optional name of the assistant
        vector_store: Reference to the vector store used by the assistant
        user: Reference to the user who created the assistant
        created_at: Timestamp when the assistant was created
    """
    assistant_id = StringField(required=True, unique=True)
    name = StringField(required=False)
    vector_store = ReferenceField(VectorStore, required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)

class Thread(Document):
    """
    Thread model representing a conversation thread in the application.
    
    Attributes:
        thread_id: Unique identifier for the thread in OpenAI
        vector_store: Reference to the vector store associated with the thread
        assistant_id: ID of the assistant used in the thread
        title: Title of the conversation thread
        user: Reference to the user who owns the thread
        created_at: Timestamp when the thread was created
        updated_at: Timestamp when the thread was last updated
    """
    thread_id = StringField(required=True, unique=True)
    vector_store = ReferenceField(VectorStore)
    assistant_id = StringField(required=True)
    title = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Message(Document):
    """
    Message model representing a single message in a conversation thread.
    
    Attributes:
        thread: Reference to the thread this message belongs to
        role: Role of the message sender (e.g., 'user', 'assistant')
        content: Text content of the message
        created_at: Timestamp when the message was created
    """
    thread = ReferenceField(Thread, required=True, reverse_delete_rule=CASCADE)
    role = StringField(required=True)
    content = StringField(required=True)
    created_at = DateTimeField()