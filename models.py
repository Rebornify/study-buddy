from datetime import datetime

from mongoengine import Document, StringField, EmailField, ReferenceField, DateTimeField, CASCADE

class User(Document):
    username = StringField(required=True, unique=True)
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    created_at = DateTimeField(default=datetime.now)

class Thread(Document):
    thread_id = StringField(required=True, unique=True)
    vector_store_id = StringField(required=True)
    assistant_id = StringField(required=True)
    title = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)  # Reference to the User
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Message(Document):
    thread = ReferenceField(Thread, required=True)
    role = StringField(required=True)
    content = StringField(required=True)
    created_at = DateTimeField()