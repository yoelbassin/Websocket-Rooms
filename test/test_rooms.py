from typing import Any
from fastapi import Depends, FastAPI, WebSocket
from websocket_rooms.room import Room
import pytest
from async_asgi_testclient import TestClient

app = FastAPI()

room = Room()

@app.websocket("/ws_test")
async def websocket_endpoint(websocket: WebSocket, room: Room = Depends(room)) -> None:
    await room.connect(websocket)


@pytest.mark.asyncio
async def test_on_receive():
    test_room = Room()
    app.dependency_overrides[room] = test_room

    message_buffer = []

    @test_room.on_receive()
    def on_receive_test(room: Room, websocket: WebSocket, message: Any):
        message_buffer.append(message)

    print(test_room._on_receive)

    msg = "hi!"

    async with TestClient(app, timeout=0.1) as client:
        async with client.websocket_connect("/ws_test") as ws:
            await ws.send_text(msg)
    assert message_buffer == [msg]
    