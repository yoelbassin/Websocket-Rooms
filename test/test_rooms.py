import asyncio
from ctypes import Union
import logging
from typing import Any, List, Literal
from fastapi import Depends, FastAPI, WebSocket
from websocket_rooms.room import Room
import pytest
from async_asgi_testclient import TestClient

app = FastAPI()

room = Room()


@app.websocket("/ws_test")
async def websocket_endpoint(websocket: WebSocket, room: Room = Depends(room)) -> None:
    await room.connect(websocket)


@pytest.fixture
def test_room():
    _test_room = Room()
    app.dependency_overrides[room] = _test_room
    return _test_room


@pytest.fixture(scope="function")
async def test_client():
    async with TestClient(app, timeout=0.1) as client:
        yield client


@pytest.mark.asyncio
# thats pretty weird - needs further research
@pytest.mark.parametrize(
    "message", ["hi!", "1234", 1234, "\U0001f5ff", b"123", {"hello": "world"}]
)
async def test_on_receive(test_client: TestClient, test_room: Room, message: Any):
    message_buffer = []

    @test_room.on_receive()
    def on_receive_test(room: Room, websocket: WebSocket, recv_message: Any):
        message_buffer.append(recv_message)

    async with test_client.websocket_connect("/ws_test") as ws:
        await ws.send_text(message)

    await asyncio.sleep(0)
    assert message_buffer == [message]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message_type, message",
    [("text", "abcd"), ("bytes", b"abcd"), ("json", {"message": "abcd"})],
)
async def test_on_receive_types(
    test_client: TestClient,
    test_room: Room,
    message_type: Room.RECEIVE_TYPES,
    message: Any,
):
    message_buffer = []

    @test_room.on_receive(message_type)
    def on_receive_test(room: Room, websocket: WebSocket, recv_message: Any):
        message_buffer.append(recv_message)

    async with test_client.websocket_connect("/ws_test") as ws:
        await ws.__getattribute__(f"send_{message_type}")(message)

    await asyncio.sleep(0)
    assert message_buffer == [message]


# thats pretty weird - needs further research
@pytest.mark.asyncio
@pytest.mark.parametrize("messages", [["hi!", "hello", "yes"]])
async def test_multiple_on_receive(
    test_client: TestClient, test_room: Room, messages: List[Any]
):
    message_buffer = []

    @test_room.on_receive()
    def on_receive_test(room: Room, websocket: WebSocket, recv_message: Any):
        message_buffer.append(recv_message)

    async with test_client.websocket_connect("/ws_test") as ws:
        for message in messages:
            await ws.send_text(message)

    await asyncio.sleep(0)
    assert message_buffer == messages


# thats pretty weird - needs further research
@pytest.mark.asyncio
@pytest.mark.parametrize("messages", [["hi!", "hello", "yes"]])
async def test_on_receive_one_after_another(
    test_client: TestClient, test_room: Room, messages: List[Any]
):
    message_buffer = []

    @test_room.on_receive()
    def on_receive_test(room: Room, websocket: WebSocket, recv_message: Any):
        message_buffer.append(recv_message)

    for message in messages:
        async with test_client.websocket_connect("/ws_test") as ws:
            await ws.send_text(message)

    await asyncio.sleep(0)
    assert message_buffer == messages


@pytest.mark.asyncio
@pytest.mark.parametrize("message, client_count", [("hello", 10)])
async def test_multiple_on_receive_simultaniously(
    test_client: TestClient, test_room: Room, message: Any, client_count: int
):
    message_buffer = []

    @test_room.on_receive()
    def on_receive_test(room: Room, websocket: WebSocket, recv_message: Any):
        message_buffer.append(recv_message)

    async def websocket_client(client: TestClient, msg: Any):
        async with client.websocket_connect("/ws_test") as ws:
            await ws.send_text(msg)

    messages = [f"{message}-{i}" for i in range(client_count)]

    await asyncio.gather(*[websocket_client(test_client, msg) for msg in messages])

    assert set(message_buffer) == set(messages)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message", ["hi!", "1234", 1234, "\U0001f5ff", b"123", {"hello": "world"}]
)
async def test_broadcast(test_client: TestClient, test_room: Room, message: Any):
    @test_room.on_receive()
    async def on_receive_test(room: Room, websocket: WebSocket, message: Any):
        await test_room.push_text(message)

    async with test_client.websocket_connect("/ws_test") as ws_1:
        async with test_client.websocket_connect("/ws_test") as ws_2:
            await ws_1.send_text(message)
            recv = await ws_2.receive_text()
            logging.info(message)
            logging.info(type(recv))
            assert recv == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message_type, message",
    [("json", {"message": "hello"}), ("text", "hello"), ("bytes", b"hello")],
)
async def test_types_broadcast(
    test_client: TestClient,
    test_room: Room,
    message_type: Room.RECEIVE_TYPES,
    message: Any,
):
    @test_room.on_receive(message_type)
    async def on_receive_test(room: Room, websocket: WebSocket, message: Any):
        await test_room.__getattribute__(f"push_{message_type}")(message)

    async with test_client.websocket_connect("/ws_test") as ws_1:
        async with test_client.websocket_connect("/ws_test") as ws_2:
            await ws_1.__getattribute__(f"send_{message_type}")(message)
            recv = await ws_2.__getattribute__(f"receive_{message_type}")()
            assert recv == message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "message", ["hi!", "1234", 1234, "\U0001f5ff", b"123", {"hello": "world"}]
)
async def test_multiple_broadcast(
    test_client: TestClient,
    test_room: Room,
    message: Any,
):
    RECEIVERS_NUMBER = 10

    @test_room.on_receive()
    async def on_receive_test(room: Room, websocket: WebSocket, message: Any):
        await test_room.push_text(message)

    async def receiver():
        async with test_client.websocket_connect("/ws_test") as ws:
            recv = await ws.receive_text()
            assert recv == message

    async def sender():
        # wait for all websockets to be created?
        await asyncio.sleep(0.1)
        async with test_client.websocket_connect("/ws_test") as ws:
            await ws.send_text(message)

    await asyncio.gather(*[receiver() for _ in range(RECEIVERS_NUMBER)], sender())


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["hi"])
async def test_message_queue_empty_if_no_connections(
    test_client: TestClient, test_room: Room, message: Any
):
    await test_room.push_text(message + "0")
    async with test_client.websocket_connect("/ws_test") as ws:
        await test_room.push_text(message + "1")
        recv = await ws.receive_text()
        assert recv == message + "1"


@pytest.mark.asyncio
async def test_disconnect(
    test_client: TestClient,
    test_room: Room,
):
    CONNECTION_NUMBER = 10

    async def websocket_connect():
        async with test_client.websocket_connect("/ws_test"):
            assert not test_room._websockets == []

    await asyncio.gather(*[websocket_connect() for _ in range(CONNECTION_NUMBER)])

    assert test_room._websockets == []


@pytest.mark.asyncio
async def test_disconnect_one_after_another(
    test_client: TestClient,
    test_room: Room,
):
    CONNECTION_NUMBER = 10

    for _ in range(CONNECTION_NUMBER):
        async with test_client.websocket_connect("/ws_test") as ws:
            assert not test_room._websockets == []
            await ws.close()
            await asyncio.sleep(0)

    assert test_room._websockets == []


@pytest.mark.asyncio
async def test_close_room(
    test_client: TestClient,
    test_room: Room,
):
    CONNECTION_NUMBER = 10

    connections = []

    for _ in range(CONNECTION_NUMBER):
        websocket = test_client.websocket_connect("/ws_test")
        await websocket.connect()
        connections.append(websocket)

    assert len(test_room._websockets) == 10

    await test_room.close()

    assert test_room._websockets == []

    for connection in connections:
        await connection.close()


@pytest.mark.asyncio
async def test_on_disconnect(
    test_client: TestClient,
    test_room: Room,
):
    CONNECTION_NUMBER = 10

    before_results: List[bool] = []
    after_results: List[bool] = []

    @test_room.on_disconnect("before")
    def on_disconnect_before(test_room: Room, websocket: WebSocket):
        before_results.append(websocket in test_room._websockets)

    @test_room.on_disconnect("after")
    def on_disconnect_after(test_room: Room, websocket: WebSocket):
        after_results.append(websocket not in test_room._websockets)

    async def websocket_connect():
        async with test_client.websocket_connect("/ws_test"):
            pass

    await asyncio.gather(*[websocket_connect() for _ in range(CONNECTION_NUMBER)])

    assert before_results == [True] * CONNECTION_NUMBER
    assert after_results == [True] * CONNECTION_NUMBER


@pytest.mark.asyncio
async def test_on_connect(
    test_client: TestClient,
    test_room: Room,
):
    CONNECTION_NUMBER = 10

    before_results: List[bool] = []
    after_results: List[bool] = []

    @test_room.on_connect("before")
    def on_connect_before(test_room: Room, websocket: WebSocket):
        after_results.append(websocket not in test_room._websockets)

    @test_room.on_connect("after")
    def on_connect_after(test_room: Room, websocket: WebSocket):
        before_results.append(websocket in test_room._websockets)

    async def websocket_connect():
        async with test_client.websocket_connect("/ws_test"):
            pass

    await asyncio.gather(*[websocket_connect() for _ in range(CONNECTION_NUMBER)])

    assert before_results == [True] * CONNECTION_NUMBER
    assert after_results == [True] * CONNECTION_NUMBER
