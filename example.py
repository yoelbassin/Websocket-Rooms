import asyncio
from time import time
from websocket_rooms import Room
from fastapi import Depends, FastAPI, WebSocket
from typing import Any, NoReturn
import logging
from fastapi.responses import HTMLResponse

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Chat</title>
    </head>
    <body>
        <h1>Time websocket</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8000/current_time");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""

app = FastAPI()

@app.get("/")
async def get():
    return HTMLResponse(html)

time_room = Room()

@time_room.on_receive("text")
async def on_receive(room: Room, websocket: WebSocket, message: Any) -> None:
    print("{}:{} just sent '{}'".format(websocket.client.host, websocket.client.port, message))

@time_room.on_connect("after")
async def on_chatroom_connection(room: Room, websocket: WebSocket) -> None:
    print("{}:{} joined the channel".format(websocket.client.host, websocket.client.port))

@time_room.on_disconnect("after")
async def on_chatroom_disconnect(room: Room, websocket: WebSocket) -> None:
    print("{}:{} left the channel".format(websocket.client.host, websocket.client.port))

async def updater_function(room: Room) -> NoReturn:
    while True:
        t = time()
        await room.push_json({"current_time": t})
        await asyncio.sleep(1)

updater_task = asyncio.create_task(updater_function(time_room))

@app.websocket("/current_time")
async def connect_websocket(websocket: WebSocket, room: Room = Depends(time_room)):
    await room.connect(websocket)