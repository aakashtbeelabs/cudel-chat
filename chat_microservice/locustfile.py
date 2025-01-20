import asyncio
import aio_pika
import json
import time
import uuid
from locust import HttpUser, task, between
from websocket import create_connection
import os
from dotenv import load_dotenv

print("Loading environment variables...")
load_dotenv()
RABBITMQ_URL = os.getenv("RABBITMQURL")
print(f"RabbitMQ URL configured: {RABBITMQ_URL}")

class RabbitMQClient:
    def __init__(self):
        print("\n=== Initializing RabbitMQClient ===")
        self.connection = None
        self.channel = None
        self.exchange = None
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        print("RabbitMQClient initialized with new event loop")

    async def connect(self):
        print("\n=== Connecting to RabbitMQ ===")
        self.connection = await aio_pika.connect_robust(RABBITMQ_URL)
        print("Connection established")
        self.channel = await self.connection.channel()
        print("Channel created")
        self.exchange = await self.channel.declare_exchange(
            "chat_exchange",
            aio_pika.ExchangeType.DIRECT
        )
        print("Exchange 'chat_exchange' declared")

    async def publish_message(self, routing_key: str, message: dict):
        print(f"\n=== Publishing message to {routing_key} ===")
        if not self.channel:
            print("No channel exists, connecting first...")
            await self.connect()
        
        message_body = json.dumps(message).encode()
        print(f"Message encoded: {message_body[:100]}...")
        await self.exchange.publish(
            aio_pika.Message(
                body=message_body,
                content_type="application/json"
            ),
            routing_key=routing_key
        )
        print("Message published successfully")

    async def setup_consumer(self, user_id: str):
        print(f"\n=== Setting up consumer for user {user_id} ===")
        if not self.channel:
            print("No channel exists, connecting first...")
            await self.connect()
            
        queue = await self.channel.declare_queue(
            f"user_{user_id}",
            auto_delete=True
        )
        print(f"Queue 'user_{user_id}' declared")
        await queue.bind(
            exchange="chat_exchange",
            routing_key=user_id
        )
        print(f"Queue bound to exchange with routing key: {user_id}")
        return queue

    async def close(self):
        print("\n=== Closing RabbitMQ connection ===")
        if self.connection:
            await self.connection.close()
            print("Connection closed successfully")

    def run_async(self, coro):
        print("\n=== Running async operation ===")
        return self._loop.run_until_complete(coro)

class ChatUser(HttpUser):
    wait_time = between(1, 3)
    
    def __init__(self, *args, **kwargs):
        print("\n=== Initializing ChatUser ===")
        super().__init__(*args, **kwargs)
        self.ws = None
        self.user_id = str(uuid.uuid4())[:8]
        self.partner_id = str(uuid.uuid4())[:8]
        self.booking_id = str(uuid.uuid4())[:8]
        self.chat_id = None
        self.rabbitmq_client = RabbitMQClient()
        print(f"ChatUser initialized with ID: {self.user_id}")
        print(f"Partner ID: {self.partner_id}")
        print(f"Booking ID: {self.booking_id}")
        
    def on_start(self):
        print("\n=== Starting ChatUser session ===")
        try:
            chat_data = {
                "participants": [self.user_id, self.partner_id],
                "bookingId": self.booking_id,
                "created_at": time.strftime('%Y-%m-%d %H:%M:%S'),
                "last_message": "",
                "last_message_time": time.strftime('%Y-%m-%d %H:%M:%S')
            }
            print(f"Creating chat with data: {chat_data}")
            
            with self.client.post("/api/chats", json=chat_data, catch_response=True) as response:
                print(f"Chat creation response status: {response.status_code}")
                if response.status_code == 200:
                    response_data = response.json()
                    self.chat_id = response_data["id"]
                    print(f"Chat created successfully with ID: {self.chat_id}")
                    response.success()
                else:
                    print(f"Failed to create chat: {response.status_code}")
                    response.failure(f"Failed to create chat: {response.status_code}")
                    return

            print("\n=== Setting up WebSocket connection ===")
            start_time = time.time()
            try:
                ws_url = f"ws://{self.host.replace('http://', '')}/ws/{self.user_id}/{self.booking_id}"
                print(f"Connecting to WebSocket URL: {ws_url}")
                self.ws = create_connection(ws_url)
                print("WebSocket connection established")
                
                print("\n=== Setting up RabbitMQ connection ===")
                self.rabbitmq_client.run_async(self.rabbitmq_client.connect())
                self.rabbitmq_client.run_async(self.rabbitmq_client.setup_consumer(self.user_id))
                print("RabbitMQ setup completed")
                
                total_time = int((time.time() - start_time) * 1000)
                print(f"Total setup time: {total_time}ms")
                self.environment.events.request.fire(
                    request_type="WebSocket",
                    name="Connect",
                    response_time=total_time,
                    response_length=0,
                    response=None,
                    context={},
                    exception=None,
                )
            except Exception as e:
                print(f"Error during WebSocket/RabbitMQ setup: {e}")
                total_time = int((time.time() - start_time) * 1000)
                self.environment.events.request.fire(
                    request_type="WebSocket",
                    name="Connect",
                    response_time=total_time,
                    response_length=0,
                    response=None,
                    context={},
                    exception=e,
                )
                raise e
            
        except Exception as e:
            print(f"Error in on_start: {e}")
            raise e
            
    def on_stop(self):
        print("\n=== Stopping ChatUser session ===")
        if self.ws:
            try:
                print("Closing WebSocket connection")
                self.ws.close()
                print("WebSocket connection closed")
            except Exception as e:
                print(f"Error closing websocket: {e}")
                
        try:
            print("Closing RabbitMQ connection")
            self.rabbitmq_client.run_async(self.rabbitmq_client.close())
            print("RabbitMQ connection closed")
        except Exception as e:
            print(f"Error closing RabbitMQ connection: {e}")
    
    @task(3)
    def send_message(self):
        print("\n=== Executing send_message task ===")
        if not self.chat_id:
            print("No chat_id available, skipping message send")
            return
            
        start_time = time.time()
        try:
            message = {
                "chat_id": self.chat_id,
                "sender_id": self.user_id,
                "booking_id": self.booking_id,
                "content": f"Test message from {self.user_id} at {time.time()}",
                "mssg_type": "text",
                "file_type": None,
                "file_name": None,
                "height": None,
                "width": None,
                "size": None,
                "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                "read": False,
                "type": "sms"
            }
            print(f"Preparing to send message: {message}")
            
            self.rabbitmq_client.run_async(
                self.rabbitmq_client.publish_message(
                    routing_key=self.partner_id,
                    message=message
                )
            )
            print(f"Message sent to partner {self.partner_id}")
                    
            total_time = int((time.time() - start_time) * 1000)
            print(f"Message send time: {total_time}ms")
            self.environment.events.request.fire(
                request_type="RabbitMQ",
                name="Send Message",
                response_time=total_time,
                response_length=len(json.dumps(message)),
                response=None,
                context={},
                exception=None,
            )
            
        except Exception as e:
            print(f"Error sending message: {e}")
            total_time = int((time.time() - start_time) * 1000)
            self.environment.events.request.fire(
                request_type="RabbitMQ",
                name="Send Message",
                response_time=total_time,
                response_length=0,
                response=None,
                context={},
                exception=e,
            )

    @task(1)
    def get_messages(self):
        print("\n=== Executing get_messages task ===")
        if not self.chat_id:
            print("No chat_id available, skipping message fetch")
            return
            
        print(f"Fetching messages for chat {self.chat_id}")
        with self.client.get(f"/api/messages/{self.chat_id}", catch_response=True) as response:
            print(f"Get messages response status: {response.status_code}")
            if response.status_code == 200:
                print("Messages fetched successfully")
                response.success()
            else:
                print(f"Failed to fetch messages: {response.status_code}")
                response.failure(f"Failed to fetch messages: {response.status_code}")

    @task(1)
    def upload_file(self):
        print("\n=== Executing upload_file task ===")
        if not self.chat_id:
            print("No chat_id available, skipping file upload")
            return
            
        start_time = time.time()
        try:
            file_content = b"Test file content"
            files = {
                'file': ('test.txt', file_content, 'text/plain')
            }
            print("Preparing to upload test file")
            
            with self.client.post("/api/chat/upload", files=files, catch_response=True) as response:
                print(f"File upload response status: {response.status_code}")
                if response.status_code == 200:
                    file_data = response.json()
                    print(f"File uploaded successfully: {file_data}")
                    
                    message = {
                        "chat_id": self.chat_id,
                        "sender_id": self.user_id,
                        "booking_id": self.booking_id,
                        "content": file_data["fileUrl"],
                        "mssg_type": "file",
                        "file_type": file_data["type"],
                        "file_name": file_data["filename"],
                        "height": file_data.get("height"),
                        "width": file_data.get("width"),
                        "size": file_data["size"],
                        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
                        "read": False,
                        "type": "sms"
                    }
                    print(f"Preparing to send file message: {message}")
                    
                    self.rabbitmq_client.run_async(
                        self.rabbitmq_client.publish_message(
                            routing_key=self.partner_id,
                            message=message
                        )
                    )
                    print(f"File message sent to partner {self.partner_id}")
                    
                    response.success()
                else:
                    print(f"Failed to upload file: {response.status_code}")
                    response.failure(f"Failed to upload file: {response.status_code}")
                    
        except Exception as e:
            print(f"Error in upload_file: {e}")
            if 'response' in locals():
                response.failure(f"Exception during file upload: {str(e)}")