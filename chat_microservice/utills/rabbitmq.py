import aio_pika
import json
from datetime import datetime
from fastapi import WebSocket
import os
from dotenv import load_dotenv
load_dotenv()
RABBITMQURL = os.getenv("RABBITMQURL")
CHATEXCHANGE = os.getenv("RABBITMQEXCHANGE")
RABBITMQQUEUE = os.getenv("RABBITMQQUEUE")
class MessagePublisher:
    def __init__(self):
        self.connection = None
        self.channel = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(RABBITMQURL)
        self.channel = await self.connection.channel()
        await self.channel.declare_exchange(CHATEXCHANGE, aio_pika.ExchangeType.DIRECT)

    async def publish_message(self, routing_key: str, message: dict):
        if not self.channel:
            await self.connect()
        exchange = await self.channel.get_exchange(CHATEXCHANGE)
        await exchange.publish(
            aio_pika.Message(
                body=json.dumps(message).encode(),
                content_type="application/json"
            ),
            routing_key=routing_key
        )

    async def close(self):
        if self.connection:
            await self.connection.close()

class MessageConsumer:
    def __init__(self, user_id: str, websocket: WebSocket):
        self.user_id = user_id
        self.websocket = websocket
        self.connection = None
        self.channel = None
        self.queue = None

    async def connect(self):
        self.connection = await aio_pika.connect_robust(
            RABBITMQURL
        )
        self.channel = await self.connection.channel()
        
        # Declare exchange
        exchange = await self.channel.declare_exchange(
            CHATEXCHANGE,
            aio_pika.ExchangeType.DIRECT
        )
        
        # Declare queue with user_id as name
        self.queue = await self.channel.declare_queue(
            f"{RABBITMQQUEUE}_{self.user_id}",
            auto_delete=True
        )
        
        # Bind queue to exchange
        await self.queue.bind(
            exchange=CHATEXCHANGE,
            routing_key=self.user_id
        )

    async def consume(self):
        async with self.queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    try:
                        data = json.loads(message.body.decode())
                        # Forward message to WebSocket
                        await self.websocket.send_json(data)
                    except Exception as e:
                        print(f"Error processing message: {e}")

    async def close(self):
        if self.connection:
            await self.connection.close()

message_publisher = MessagePublisher()

