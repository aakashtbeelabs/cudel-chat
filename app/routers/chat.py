# app/routers/chat.py
from typing import List
from fastapi import APIRouter, Depends,UploadFile, File
from fastapi.responses import JSONResponse
from app.models import Chat, ChatResponse, MessgaeResponse
from app.database import get_database
from bson import ObjectId
import boto3
import os
from dotenv import load_dotenv
load_dotenv()
router = APIRouter()
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_REGION=os.getenv("AWS_REGION")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)
@router.post("/chats/", response_model=ChatResponse)
async def create_chat(chat: Chat, db=Depends(get_database)):
    chat_dict = chat.dict(by_alias=True)
    result = await db.chats.insert_one(chat_dict)
    message_doc = {"chat_id": str(result.inserted_id), "messages": []}
    await db.messages.insert_one(message_doc)
    created_chat = await db.chats.find_one({"_id": result.inserted_id})
    return ChatResponse(
        id=str(created_chat["_id"]),
        participants=created_chat["participants"],
        created_at=created_chat["created_at"],
        last_message=created_chat.get("last_message"),
        last_message_time=created_chat.get("last_message_time")
    )

@router.get("/chats/{user_id}", response_model=List[ChatResponse])
async def get_user_chats(user_id: str, db=Depends(get_database)):
    chats = await db.chats.find({"participants": user_id}).to_list(None)
    return [ChatResponse(
        id=str(chat["_id"]),
        participants=chat["participants"],
        created_at=chat["created_at"],
        last_message=chat.get("last_message"),
        last_message_time=chat.get("last_message_time")
    ) for chat in chats]

@router.post("/chat/upload")
async def upload_file(file: UploadFile = File(...)):
    s3_key = f"uploads/{file.filename}"
    s3_client.upload_fileobj(
            file.file,
            S3_BUCKET_NAME,
            s3_key,
            ExtraArgs={"ACL": "public-read"},  # Make the file publicly accessible
        )
    file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"

    return JSONResponse(
            {"file_url": file_url, "message": "File uploaded successfully"}
        )
@router.get("/messages/{chat_id}", response_model=List[MessgaeResponse])
async def get_chat_messages(chat_id: str, db=Depends(get_database)):
    # Find the message document for this chat
    message_doc = await db.messages.find_one({"chat_id": chat_id})
    if not message_doc:
        return []
    
    messages = message_doc.get("messages", [])
    return [
        MessgaeResponse(
            id=str(msg.get("_id", ObjectId())),
            chat_id=chat_id,
            sender_id=msg["sender_id"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            read=msg["read"],
            type="sms"
        )
        for msg in messages
    ]
