from datetime import datetime

from mongoengine import Document, ListField, StringField, EmailField, ReferenceField, DateTimeField, CASCADE

class User(Document):
    username = StringField(required=True, unique=True)
    name = StringField(required=True)
    email = EmailField(required=True, unique=True)
    created_at = DateTimeField(default=datetime.now)

class File(Document):
    file_id = StringField(required=True, unique=True)
    name = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)

class VectorStore(Document):
    vector_store_id = StringField(required=True, unique=True)
    name = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Assistant(Document):
    assistant_id = StringField(required=True, unique=True)
    name = StringField(required=False)
    vector_store = ReferenceField(VectorStore, required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)

class Thread(Document):
    thread_id = StringField(required=True, unique=True)
    vector_store = ReferenceField(VectorStore)
    assistant_id = StringField(required=True)
    title = StringField(required=True)
    user = ReferenceField(User, required=True, reverse_delete_rule=CASCADE)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

class Message(Document):
    thread = ReferenceField(Thread, required=True, reverse_delete_rule=CASCADE)
    role = StringField(required=True)
    content = StringField(required=True)
    created_at = DateTimeField()