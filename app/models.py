from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
from bson import ObjectId

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def get_ist_time():
    # Get current UTC time and add 5:30 hours for IST
    return datetime.utcnow() + timedelta(hours=5, minutes=30)

class Message(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    chat_id: str
    sender_id: str
    content: str
    timestamp: datetime = Field(default_factory=get_ist_time)
    read: bool = False
    mssg_type: Optional[str] = None
    file_type: Optional[str] = None
    file_name: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

class Chat(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    participants: List[str]
    created_at: datetime = Field(default_factory=get_ist_time)
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            ObjectId: str,
            datetime: lambda dt: dt.isoformat()
        }
        populate_by_name = True

# Other response models
class MessageDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default_factory=PyObjectId, alias="_id")
    chat_id: str
    messages: List[dict] = Field(default_factory=list)

class ChatResponse(BaseModel):
    id: str
    participants: List[str]
    created_at: datetime
    last_message: Optional[str] = None
    last_message_time: Optional[datetime] = None

class MessgaeResponse(BaseModel):
    id: str
    chat_id: str
    sender_id: str
    content: str
    timestamp: datetime
    read: bool