# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from .utills.rabbitmq import MessagePublisher
from .routers import chat, websocket
from jinja2 import Environment, FileSystemLoader
from dotenv import load_dotenv
import os
from fastapi.middleware.cors import CORSMiddleware
load_dotenv()
BASE_URL = os.getenv("BASE_URL")
templates_env = Environment(loader=FileSystemLoader(""))
app = FastAPI()
origins = [
    "http://localhost:3000",
    "https://admin-staging.cudel.in"
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
message_publisher = MessagePublisher()
app.include_router(chat.router, prefix="/api")
app.include_router(websocket.router)

@app.get("/", response_class=HTMLResponse)
async def get():
    template = templates_env.get_template("index.html")
    rendered_html = template.render(base_url=BASE_URL)
    return HTMLResponse(content=rendered_html)

@app.on_event("startup")
async def startup_event():
    await message_publisher.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await message_publisher.close()

