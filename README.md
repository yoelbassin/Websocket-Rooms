A python library for creating WebSocket rooms, for message sharing or data distribution to multiple connections.

# Proposed API:
## Basic use:
Let's create a chatroom where everyone can post their messages:
### Using API #1
```python
room = Room()

@room.on_receive("json")
async def on_receive(room: Room, websocket: WebSocket, message: Any) -> None:
    await room.push(message)

@room.on_connection
async def on_chatroom_connection(room: Room, websocket: WebSocket) -> None:
    logging.info("{} joined the chat room".format(websocket.client.host))

@app.websocket("/chat")
async def connect_websocket(websocket: WebSocket):
    await room.connect(websocket, client_id)
```
### Using API #2
```python
room = Room()

@app.websocket("/chat")
async def connect_websocket(websocket: WebSocket):
    async with room.connect(websocket):
        logging.info("{} joined the chat room".format(websocket.client.host))
        async for message in websocket.iter_text():
            room.push(message)
```
## Advanced usage

Example of a more advanced use case, with modification to the `Room` base class:
Suppose a class `RoomWithClientId`, where each WebSocket has a `client_id` associated with it, which it receives on connection:
```python
class RoomWithClientId(Room):
    def __init__(self, base_room: Optional[BaseRoom] = None) -> None:
        super().__init__(base_room)
        self._id_to_ws = {}

    async def connect(self, websocket: WebSocket, client_id: int) -> None:
        self._id_to_ws[websocket] = client_id
        await super().connect(websocket)

    def get_client_id(self, websocket: WebSocket) -> int:
        return self._id_to_ws.get(websocket)


chat_room = RoomWithClientId()
```
### Using API #1
Simpler, but much more limited (see appendix 1):
```python
@chat_room.on_receive("json")
async def on_chatroom_receive(room: RoomWithClientId, websocket: WebSocket, message: Any) -> None:
    await room.push(message)

@chat_room.on_connection
async def on_chatroom_connection(room: RoomWithClientId, websocket: WebSocket, client_id: int) -> None:
    logging.info("{} joined the chat room".format(client_id))


@app.websocket("/chat/{client_id}")
async def connect_websocket(websocket: WebSocket, client_id: int):
    await chat_room.connect(websocket, client_id)
```

### Using API #2
A little complicated, exposing the `WebSocket` itself to the user, however, allows more freedom:
```python
# An endpoint for websockets that are sending and receiving data
@app.websocket("/chat_ws/{client_id}")
async def connect_chat_websocket(websocket: WebSocket, client_id: int):
    async with chat_room.connect(websocket, client_id):
        logging.info("{} joined the chat room".format(client_id))
        async for message in websocket.iter_text():
            chat_room.push(message)


# An endpoint for websockets that only receive data
@app.websocket("/listening_ws/{client_id}")
async def connect_listening_websocket(websocket: WebSocket, client_id: int):
    await chat_room.connect(websocket, client_id)
    logging.info("{} joined as a listener to the chat room".format(client_id))
    await chat_room.listen(websocket) # A subject to change - listen / keep_alive / ...
```

# Appendix

1. A solution to this may be creating an option to create a basic `BaseRoom` that connections (?) can use: 
```python
# for websockets that are sending and receiving data
chat_connection = ConnectionsManager(chat_room)

@chat_connection.on_receive("json")
async def on_chatroom_receive(room: RoomWithClientId, websocket: WebSocket, message: Any) -> None:
    await room.push(message)

@chat_connection.on_connection
async def on_chat_connection(room: RoomWithClientId, websocket: WebSocket, client_id: int) -> None:
    logging.info("{} joined the chat room".format(client_id))

@app.websocket("/chat_ws/{client_id}")
async def connect_chat_websocket(websocket: WebSocket, client_id: int) -> None:
    await chat_connection.connect(websocket, client_id)

# for websockets that are only receiving data
listener_connection = ConnectionsManager(chat_room)

@listener_connection.on_connection
async def on_chat_connection(room: RoomWithClientId, websocket: WebSocket, client_id: int) -> None:
    logging.info("{} joined as a listener to the the chat room".format(client_id))


@app.websocket("/listening_ws/{client_id}")
async def connect_listening_websocket(websocket: WebSocket, client_id: int) -> None:
    await listener_connection.connect(websocket, client_id)
```