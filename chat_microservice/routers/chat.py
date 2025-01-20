# app/routers/chat.py
from typing import List
from fastapi import APIRouter, Depends, Query,UploadFile, File,status,HTTPException
from fastapi.responses import JSONResponse
from ..models import Chat, ChatResponse, GetBookingResponse, GetChats, MessageResponse, MessgaeResponse
from ..database import get_database
from bson import ObjectId
import boto3
import os
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image
import mimetypes
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

@router.post("/chats", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def create_chat(chat: Chat, db=Depends(get_database)):
    try:
        existing_chat = await db.chats.find_one({"bookingId": chat.bookingId})
        if existing_chat:
            return ChatResponse(
                id=str(existing_chat["_id"]),
                participants=existing_chat.get("participants", []),
                bookingId=existing_chat.get("bookingId"),
                created_at=existing_chat.get("created_at"),
                last_message=existing_chat.get("last_message"),
                last_message_time=existing_chat.get("last_message_time")
            )
        chat_dict = chat.dict(by_alias=True)
        result = await db.chats.insert_one(chat_dict)
        message_doc = {"chat_id": str(result.inserted_id), "messages": []}
        await db.messages.insert_one(message_doc)
        created_chat = await db.chats.find_one({"_id": result.inserted_id})
        if not created_chat:
            raise HTTPException(status_code=500, detail="Chat creation failed.")
        return ChatResponse(
            id=str(created_chat["_id"]),
            participants=created_chat.get("participants", []),
            bookingId=created_chat.get("bookingId"),
            created_at=created_chat.get("created_at"),
            last_message=created_chat.get("last_message"),
            last_message_time=created_chat.get("last_message_time")
        )
    except Exception as e:
        # Handle unexpected errors gracefully
        raise HTTPException(status_code=500, detail=str(e))



@router.get("/chats/{user_id}", response_model=List[ChatResponse])
async def get_user_chats(user_id: str, db=Depends(get_database)):
    chats = await db.chats.find({"participants": user_id}).to_list(None)
    return [ChatResponse(
        id=str(chat["_id"]),
        participants=chat["participants"],
        bookingId=chat["bookingId"],
        created_at=chat["created_at"],
        last_message=chat.get("last_message"),
        last_message_time=chat.get("last_message_time")
    ) for chat in chats]

@router.post("/chat/upload")
async def upload_file(file: UploadFile = File(...)):
    # Read file content
    file_content = await file.read()
    s3_key = f"uploads/{file.filename}"
    s3_client.upload_fileobj(
        BytesIO(file_content),
        S3_BUCKET_NAME,
        s3_key,
        ExtraArgs={"ACL": "public-read"}, 
    )
    file_url = f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    
    file_size = len(file_content)
    mime_type, _ = mimetypes.guess_type(file.filename)
    file_type = mime_type.split('/')[0] if mime_type else "unknown" 
    height, width = None, None
    if file_type == "application":
        height, width = 250, 500
    elif file_type == "video":
        height, width = 300, 300
    if file_type == "image":
        try:
            with Image.open(BytesIO(file_content)) as img:
                width, height = img.size
        except Exception:
            pass
    return JSONResponse(
        {
            "fileUrl": file_url,
            "filename": file.filename,
            "size": file_size,
            "type": file_type,
            "width": width,
            "height": height,
            "message": "File uploaded successfully",
        }
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
            chatId=chat_id,
            senderId=msg["sender_id"],
            bookingId=msg.get("booking_id"),
            mssgType=msg.get("mssg_type"),
            fileType=msg.get("file_type"),
            fileName=msg.get("file_name"),
            height=msg.get("height"),
            width=msg.get("width"),
            size=msg.get("size"),
            content=msg["content"],
            timestamp=msg["timestamp"],
            read=msg["read"],
            type="sms"
        )
        for msg in messages
    ]


@router.get("/getChats")
async def get_chats(
    db=Depends(get_database),
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100)
):
    skip = (page - 1) * per_page
    total_count = await db.chats.count_documents({})
    get_chats = (
        await db.chats.find()
        .skip(skip)
        .limit(per_page)
        .to_list(None)
    )
    chats = [
        GetChats(
            id=str(chat["_id"]),
            bookingId=chat["bookingId"],
            participants=chat["participants"],
            createdAt=chat["created_at"],
            lastMessage=chat.get("last_message"),
            lastMessageTime=chat.get("last_message_time")
        )
        for chat in get_chats
    ]

    return {
        "page": page,
        "perPage": per_page,
        "totalCount": total_count,
        "totalPages": (total_count + per_page - 1) // per_page,
        "chats": chats
    }

@router.get("/getChatDetails/{bookingId}", response_model=GetBookingResponse)
async def get_chat_details(bookingId: str, db=Depends(get_database)):
    booking = await db.chats.find_one({"bookingId": bookingId})
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    messages = await db.messages.find(
        {"chat_id": str(booking["_id"])}
    ).sort("timestamp", -1).to_list(length=None)
    if not messages:
        raise HTTPException(status_code=404, detail="Messages not found")
    all_messages = sorted(
        (msg for message_doc in messages for msg in message_doc["messages"]),
        key=lambda x: x["timestamp"],
        reverse=True  # Sort by timestamp descending
    )
    formatted_messages = [
        MessageResponse(
            id=str(msg["_id"]),
            senderId=msg["sender_id"],
            receiverUserType=msg["receiver_user_type"],
            bookingId=msg["booking_id"],
            content=msg["content"],
            timestamp=msg["timestamp"],
            read=msg["read"],
            mssgType=msg["mssg_type"],
            fileType=msg["file_type"],
            fileName=msg["file_name"],
            height=msg["height"],
            width=msg["width"],
            size=msg["size"]
        ) for msg in all_messages
    ]
    
    return GetBookingResponse(
        bookingId=str(booking["_id"]),
        messages=formatted_messages
    )
    