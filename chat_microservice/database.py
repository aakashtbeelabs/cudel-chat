# app/database.py
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
load_dotenv()
MONGODB = os.getenv("MONGODB")
async def get_database():
    client = AsyncIOMotorClient(MONGODB)
    try:
        yield client.cudel_chat
    finally:
        client.close()
