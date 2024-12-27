# app/routers/websocket.py
import asyncio
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from ..utills.connection_manager import ConnectionManager
from ..utills.rabbitmq import MessageConsumer
from ..database import get_database
from bson.errors import InvalidId
import json
from bson import ObjectId
from datetime import datetime
from ..utills.rabbitmq import message_publisher
import pytz
router = APIRouter()
manager = ConnectionManager()

@router.websocket("/ws/{user_id}/{booking_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str,booking_id: str, db=Depends(get_database)):
    await websocket.accept()
    
    consumer = MessageConsumer(user_id, websocket)
    await consumer.connect()
    consumer_task = asyncio.create_task(consumer.consume())
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            chat_id = message_data["chat_id"]
            try:
                IST = pytz.timezone('Asia/Kolkata')
                current_time = datetime.now(IST)
                formatted_time = current_time.replace(tzinfo=None)
                new_message = {
                    "_id": ObjectId(),
                    "sender_id": user_id,
                    "booking_id": booking_id,
                    "content": message_data["content"],
                    "timestamp": formatted_time,
                    "read": False,
                    "mssg_type": message_data["mssg_type"],
                    "file_type": message_data["file_type"],
                    "file_name": message_data["file_name"],
                    "height": message_data["height"],
                    "width": message_data["width"],
                    "size": message_data["size"]
                }
                
                # Add message to the messages document
                result = await db.messages.update_one(
                    {"chat_id": chat_id},
                    {
                        "$push": {
                            "messages": new_message
                        }
                    },
                    upsert=True  # Create if doesn't exist
                )
                
                # Update last message in chat document
                await db.chats.update_one(
                    {"_id": ObjectId(chat_id)},
                    {
                        "$set": {
                            "last_message": message_data["content"],
                            "last_message_time": formatted_time,
                            "booking_id": booking_id
                        }
                    }
                )
                
                # Get chat for participants
                chat = await db.chats.find_one({"_id": ObjectId(chat_id)})
                if not chat:
                    print(f"Chat not found for chat_id: {chat_id}")
                    continue
                iso_timestamp = current_time.strftime('%Y-%m-%d %H:%M:%S %Z%z')
                formatted_timestamp = current_time.strftime('%m/%d/%y, %I:%M %p')
                # Publish message to each participant
                for participant in chat["participants"]:
                    if participant != user_id:
                        await message_publisher.publish_message(
                            routing_key=participant,
                            message={
                                "chat_id": chat_id,
                                "content": message_data["content"],
                                "sender_id": user_id,
                                "booking_id": booking_id,
                                "timestamp": formatted_timestamp,
                                "mssg_type": message_data["mssg_type"],
                                "file_type": message_data["file_type"],
                                "file_name": message_data["file_name"],
                                "height": message_data["height"],
                                "width": message_data["width"],
                                "size": message_data["size"]

                            }
                        )
                        
            except (InvalidId, ValueError) as e:
                print(f"Invalid ObjectId format for chat_id: {chat_id}")
                continue
            except Exception as e:
                print(f"Error processing message: {e}")
                continue
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for user: {user_id}")
    finally:
        consumer_task.cancel()
        await consumer.close()
