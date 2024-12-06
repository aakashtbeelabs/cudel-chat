# app/database.py
from motor.motor_asyncio import AsyncIOMotorClient

async def get_database():
    client = AsyncIOMotorClient("mongodb+srv://aakasht:D4RDJxcGGkpSclWZ@aakash.a5vjvwc.mongodb.net/")
    try:
        yield client.cudel_chat
    finally:
        client.close()
