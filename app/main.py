# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from app.utills.rabbitmq import MessagePublisher
from app.routers import chat, websocket
from jinja2 import Environment, FileSystemLoader
templates_env = Environment(loader=FileSystemLoader("app"))
app = FastAPI()
message_publisher = MessagePublisher()
app.include_router(chat.router, prefix="/api")
app.include_router(websocket.router)

@app.get("/", response_class=HTMLResponse)
async def get():
    template = templates_env.get_template("index.html")
    rendered_html = template.render()
    return HTMLResponse(content=rendered_html)

@app.on_event("startup")
async def startup_event():
    await message_publisher.connect()

@app.on_event("shutdown")
async def shutdown_event():
    await message_publisher.close()