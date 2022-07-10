from __future__ import annotations
from enum import Enum
from gc import callbacks
import inspect
import json
from typing import Any, Callable, Dict, List, Union, NoReturn
from starlette.websockets import WebSocketState, Message, WebSocket, WebSocketDisconnect

class ReceiveType(Enum):
    TEXT = "text"
    BYTES = "bytes"
    JSON = "json"


class Room:
    RECEIVE_TYPES = Union[ReceiveType.TEXT.value, ReceiveType.JSON.value, ReceiveType.BYTES.value
    ]

    def __init__(self):
        self._websockets: List[WebSocket] = []
        self._on_receive: Dict[self.RECEIVE_TYPES, Callable[[Room, WebSocket], None]]

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
            await websocket.send_
            living_connections.append(websocket)
        self._websockets = living_connections

    async def push_text(self, message: str) -> None:
        pass

    async def push_bytes(self, message: bytes) -> None:
        pass

    async def _run_client_lifecycle(self, websocket: WebSocket) -> None:
        try:
            if websocket.application_state != WebSocketState.CONNECTED:
                raise RuntimeError(
                    'WebSocket is not connected. Need to call "accept" first.'
                )
            message: Message = await websocket.receive()
            websocket._raise_on_disconnect(message)

            func = None
            text = None

            if ReceiveType.BYTES.value in message.keys():
                text = message[ReceiveType.BYTES.value].decode("utf-8")
                if ReceiveType.BYTES.value in self._on_receive.keys():
                    func = self._on_receive[ReceiveType.BYTES.value]
                elif ReceiveType.JSON in self._on_receive.keys():
                    text = json.loads(text)
                    func = self._on_receive[ReceiveType.JSON.value]
            elif ReceiveType.TEXT.value in message.keys():
                text = message[ReceiveType.TEXT.value]
                if ReceiveType.TEXT.value in self._on_receive.keys():
                    func = self._on_receive[ReceiveType.TEXT.value]
                elif ReceiveType.JSON in self._on_receive.keys():
                    text = json.loads(text)
                    func = self._on_receive[ReceiveType.JSON.value]

            if func and text:
                func_res = func(text)
                if inspect.isawaitable(func_res):
                    await func_res

        except WebSocketDisconnect:
            await self.remove(websocket)

    def on_receive(self, mode: Room.RECEIVE_TYPES = ReceiveType.TEXT.value) -> callable:
        if mode not in self.RECEIVE_TYPES:
            raise RuntimeError('The "mode" argument should be "text", "bytes" or "json".')
        def inner(func: Callable[[Room, WebSocket, Any], None]):
            self._on_receive[mode] = func()

        return inner

    def __call__(self) -> Room:
        return self
