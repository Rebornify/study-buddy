from mongoengine import Document, StringField, ReferenceField, DateTimeField

class Thread(Document):
    thread_id = StringField(required=True)
    vector_store_id = StringField(required=True)
    assistant_id = StringField(required=True)
    title = StringField(required=True)
    created_at = DateTimeField(required=True)
    updated_at = DateTimeField()

class Message(Document):
    thread = ReferenceField(Thread, required=True)
    role = StringField(required=True)
    content = StringField(required=True)
    created_at = DateTimeField()