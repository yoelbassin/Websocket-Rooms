![ci workflow](https://github.com/yoelbassin/Websocket-Rooms/actions/workflows/ci.yml/badge.svg)
[![PyPI Version](https://img.shields.io/pypi/v/websocket-rooms?label=pypi%20package)](https://pypi.python.org/pypi/Websocket-Rooms)
[![GitHub](https://img.shields.io/github/license/yoelbassin/Websocket-Rooms)](https://github.com/yoelbassin/Websocket-Rooms/blob/dev/LICENSE)
<!-- ![PyPI - Downloads](https://img.shields.io/pypi/dm/PACKAGE) -->
# Websocket Rooms: `websocket_rooms`

A python library for managing and creating WebSocket rooms, for message sharing or data distribution between multiple connections.

## Installation
Use `pip install websocket-rooms` to install this package.

## About
This library was created after building several real-time web apps and implementing the same mechanism to broadcast real-time messages between clients listening for the same real-time telemetries.
The library simplifies the solution for this issue and proposes a simpler way to handle multiple WebSocket clients that act the same way.

## Basic usage example:
Let's create a chatroom where everyone can post their messages:
```python
from websocket_rooms import Room

chat_room = Room()

@chat_room.on_receive("json")
async def on_receive(room: Room, websocket: WebSocket, message: Any) -> None:
    await room.push_json(message)

@chat_room.on_connection
async def on_chatroom_connection(room: Room, websocket: WebSocket) -> None:
    logging.info("{} joined the chat room".format(websocket.client.host))

@chat_app.websocket("/chat")
async def connect_websocket(websocket: WebSocket):
    await chat_room.connect(websocket)
```
## Advanced use case example

Example of a more advanced use case, with modification to the `Room` base class:
Suppose a class `RoomWithClientId`, where each WebSocket has a `client_id` associated with it, which it receives on connection:
```python
class RoomWithClientId(Room):
    def __init__(self) -> None:
        super().__init__()
        self._id_to_ws = {}

    async def connect(self, websocket: WebSocket, client_id: int) -> None:
        self._id_to_ws[websocket] = client_id
        await super().connect(websocket)

    def get_client_id(self, websocket: WebSocket) -> int:
        return self._id_to_ws.get(websocket)


chat_room = RoomWithClientId()

@chat_room.on_receive("text")
async def on_chatroom_receive(room: RoomWithClientId, websocket: WebSocket, message: Any) -> None:
    await room.push_json(f"{room.get_client_id(websocket)}: '{message}'")

@chat_room.on_connect("before")
async def before_chatroom_connection(room: RoomWithClientId, websocket: WebSocket) -> None:
    await room.push_json(f"{room.get_client_id(websocket)} is about to join the room!")

@chat_room.on_connect("after")
async def after_chatroom_connection(room: RoomWithClientId, websocket: WebSocket) -> None:
    await room.push_json(f"{room.get_client_id(websocket)} has joined the chat room!")
```
