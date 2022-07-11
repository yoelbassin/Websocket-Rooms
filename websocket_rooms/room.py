from __future__ import annotations
import asyncio
from enum import Enum
from gc import callbacks
import inspect
import json
import logging
from typing import Any, Callable, Dict, List, Union, NoReturn, get_args
from starlette.websockets import WebSocketState, Message, WebSocket, WebSocketDisconnect
import websockets


class ReceiveType(Enum):
    TEXT = "text"
    BYTES = "bytes"
    JSON = "json"


class Room:
    RECEIVE_TYPES = Union[
        ReceiveType.TEXT.value, ReceiveType.JSON.value, ReceiveType.BYTES.value
    ]

    def __init__(self):
        self._websockets: List[WebSocket] = []
        self._on_receive: Dict[
            self.RECEIVE_TYPES, Callable[[Room, WebSocket], None]
        ] = {}

    async def connect(self, websocket: WebSocket) -> NoReturn:
        await websocket.accept()
        self._websockets.append(websocket)
        await self._run_client_lifecycle(websocket)

    async def push_json(self, message: any) -> None:
        """
        Pushes the data as a broadcast to all the room clients

        Parameters
        ----------
        message: any
            the message to be pushed
        """
        living_connections: List[WebSocket] = []
        while len(self._websockets) > 0:
            websocket = self._websockets.pop()
            await websocket.send_json(message)
            living_connections.append(websocket)
        self._websockets = living_connections

    async def push_text(self, message: str) -> None:
        living_connections: List[WebSocket] = []
        while len(self._websockets) > 0:
            websocket = self._websockets.pop()
            await websocket.send_text(message)
            living_connections.append(websocket)
        self._websockets = living_connections

    async def push_bytes(self, message: bytes) -> None:
        living_connections: List[WebSocket] = []
        while len(self._websockets) > 0:
            websocket = self._websockets.pop()
            await websocket.send_bytes(message)
            living_connections.append(websocket)
        self._websockets = living_connections

    async def _run_client_lifecycle(self, websocket: WebSocket) -> NoReturn:
        try:
            while True:
                if websocket.application_state != WebSocketState.CONNECTED:
                    raise RuntimeError(
                        'WebSocket is not connected. Need to call "accept" first.'
                    )
                message: Message = await websocket.receive()
                logging.info(message)
                websocket._raise_on_disconnect(message)

                func = None
                text = None

                if ReceiveType.BYTES.value in message.keys():
                    text = message[ReceiveType.BYTES.value]
                    if ReceiveType.BYTES.value in self._on_receive.keys():
                        func = self._on_receive[ReceiveType.BYTES.value]
                    elif ReceiveType.JSON in self._on_receive.keys():
                        text = json.loads(text.decode("utf-8"))
                        func = self._on_receive[ReceiveType.JSON.value]
                elif ReceiveType.TEXT.value in message.keys():
                    text = message[ReceiveType.TEXT.value]
                    if ReceiveType.TEXT.value in self._on_receive.keys():
                        func = self._on_receive[ReceiveType.TEXT.value]
                    elif ReceiveType.JSON.value in self._on_receive.keys():
                        text = json.loads(text)
                        func = self._on_receive[ReceiveType.JSON.value]

                if func and text:
                    func_res = func(self, websocket, text)
                    if inspect.isawaitable(func_res):
                        await func_res

        except WebSocketDisconnect:
            await self.remove(websocket)
            raise ValueError()


    async def remove(self, websocket: WebSocket):
        try:
            await websocket.close()
        except RuntimeError('Cannot call "send" once a close message has been sent.'):
            logging.warning(f"websocket {websocket.client.host}:{websocket.client.port} is already closed")
        finally:
            self._websockets.remove(websocket)


    async def close(self):
        websockets = self._websockets.copy()
        for websocket in websockets:
            await self.remove(websocket)

    def on_receive(self, mode: Room.RECEIVE_TYPES = ReceiveType.TEXT.value) -> callable:
        if not mode in ["text", "bytes", "json"]:
            raise RuntimeError(
                'The "mode" argument should be "text", "bytes" or "json".'
            )

        def inner(func: Callable[[Room, WebSocket, Any], None]):
            self._on_receive[mode] = func
            return func

        return inner

    # TODO: Add on connect and on disconnect

    def __call__(self) -> Room:
        return self
