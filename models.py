from mongoengine import Document, StringField, ReferenceField, DateTimeField

class Conversation(Document):
    conversation_id = StringField(required=True, unique=True)
    title = StringField(default='New Chat')
    created_at = DateTimeField()
    updated_at = DateTimeField()

class Message(Document):
    conversation = ReferenceField(Conversation, required=True)
    role = StringField(required=True)
    content = StringField(required=True)
    created_at = DateTimeField()