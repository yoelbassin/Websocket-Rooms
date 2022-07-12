from __future__ import annotations
import asyncio
from enum import Enum
import inspect
import json
import logging
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Tuple,
    Union,
    NoReturn,
)
from starlette.websockets import WebSocketState, Message, WebSocket, WebSocketDisconnect


class ReceiveType(Enum):
    TEXT = "text"
    BYTES = "bytes"
    JSON = "json"


class Room:
    RECEIVE_TYPES = Union[
        ReceiveType.TEXT.value, ReceiveType.JSON.value, ReceiveType.BYTES.value
    ]
    _websockets: List[WebSocket]
    _on_connect: Dict[Literal["before", "after"], Callable[[Room, WebSocket], None]]
    _on_receive: Dict[Literal["text", "bytes", "json"], Callable[[Room, WebSocket, Any], None]]
    _on_disconnect: Dict[Literal["before", "after"], Callable[[Room, WebSocket], None]]
    _to_push: asyncio.Queue
    _publisher_task: asyncio.Task

    def __init__(self):
        self._websockets = []
        self._on_receive = {}
        self._on_disconnect = {}
        self._on_connect = {}
        self._to_push = asyncio.Queue()
        self._publisher_task = None

    async def connect(self, websocket: WebSocket) -> NoReturn:
        """
        Accepts a websocket connection and, adds it to the room clients list, and runs the 
        _run_client_lifecycle function to manage the connection.

        Parameters
        ----------
        websocket : WebSocket
            The websocket to connect

        Returns
        -------
        NoReturn
            The function runs for the entire client lifetime.
        """
        if not self._publisher_task:
            self._publisher_task = asyncio.create_task(self._publisher())
        before = self._on_connect.get("before")
        if before:
            await await_if_awaitable(before(self, websocket))
        await websocket.accept()
        self._websockets.append(websocket)
        after = self._on_connect.get("after")
        if after:
            await await_if_awaitable(after(self, websocket))
        await self._run_client_lifecycle(websocket)

    async def _push(self, message_object: Tuple[Any, Literal["text", "bytes", "json"]]):
        """
        Pushes the message object into the message queue.

        Parameters
        ----------
        message_object : Tuple[Any, Literal["text", "bytes", "json"]]
            the message object to be pushed
        """
        if self._publisher_task:
            await self._to_push.put(message_object)

    async def push_json(self, message: dict) -> None:
        """
        Pushes the json data as a broadcast to all the room clients

        Parameters
        ----------
        message : dict
            the message to be pushed
        """
        await self._push((message, "json"))

    async def push_text(self, message: str) -> None:
        """
        Pushes the str data as a broadcast to all the room clients

        Parameters
        ----------
        message: str
            the message to be pushed
        """
        await self._push((message, "text"))

    async def push_bytes(self, message: bytes) -> None:
        """
        Pushes the bytes data as a broadcast to all the room clients

        Parameters
        ----------
        message: bytes
            the message to be pushed
        """
        await self._push((message, "bytes"))

    async def _publisher(self):
        """
        A publisher that runs on the message queue and pushes the message to all the clients.
        This courtine is ran in the background in the _publisher_task task.
        """
        while True:
            (message, message_type) = await self._to_push.get()
            living_connections: List[WebSocket] = []
            while len(self._websockets) > 0:
                websocket = self._websockets.pop()
                try:
                    await websocket.__getattribute__(f"send_{message_type}")(message)
                except WebSocketDisconnect:
                    continue
                living_connections.append(websocket)
            self._websockets = living_connections

    async def _run_client_lifecycle(self, websocket: WebSocket) -> NoReturn:
        """
        Manages the clients lifecycle, calling on_receive callback when a message is received from the websocket.

        Raises
        ------
        RuntimeError('WebSocket is not connected. Need to call "accept" first.')
        """
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
            await self.remove(websocket, closed=True)

    async def remove(self, websocket: WebSocket, closed: bool = False) -> None:
        """
        Remove a websocket from the room, and close it.
        """
        before = self._on_disconnect.get("before")
        if before is not None:
            await await_if_awaitable(before(self, websocket))
        if not closed:
            await websocket.close()
        self._websockets.remove(websocket)
        # kill the publisher task if there are no listeners
        if self._websockets == []:
            self._publisher_task.cancel()
            self._publisher_task = None
        after = self._on_disconnect.get("after")
        if after is not None:
            await await_if_awaitable(after(self, websocket))

    async def close(self) -> None:
        """
        Close the room and all its connections.
        """
        websockets = self._websockets.copy()
        for websocket in websockets:
            await self.remove(websocket)

    def on_receive(
        self, mode: Room.RECEIVE_TYPES = ReceiveType.TEXT.value
    ) -> Callable[[Room, WebSocket, Any], None]:
        """
        The decorator to specify the callbacks that will be run when a message is received from client websocket.

        Parameters
        ----------
        mode : Literal["text", "bytes", "json"]
            The type of the message that callback will be ran on.

        Raises
        ------
        RuntimeError('The "mode" argument should be "text", "bytes" or "json".')

        Returns
        -------
        Callable[[Room, WebSocket, Any], None]
            The function that the decorator receives.

        """
        if not mode in ["text", "bytes", "json"]:
            raise RuntimeError(
                'The "mode" argument should be "text", "bytes" or "json".'
            )

        def inner(func: Callable[[Room, WebSocket, Any], None]):
            self._on_receive[mode] = func
            return func

        return inner

    def on_connect(
        self, mode: Literal["before", "after"] = "after"
    ) -> Callable[[Room, WebSocket], None]:
        """
        The decorator to specify the callbacks that will run on websockets connection.

        Parameters
        ----------
        mode : Literal["before", "after"]
            The execution time of the callback - before / after connecting the websocket.

        Raises
        ------
        RuntimeError('The "mode" argument should be "before" or "after".')

        Returns
        -------
        Callable[[Room, WebSocket], None]
            The function that the decorator receives.
        """
        if mode not in ["before", "after"]:
            raise RuntimeError('The "mode" argument should be "before" or "after".')

        def inner(func: Callable[[Room, WebSocket], None]):
            self._on_connect[mode] = func
            return func

        return inner

    def on_disconnect(
        self, mode: Literal["before", "after"] = "after"
    ) -> Callable[[Room, WebSocket], None]:
        """
        The decorator to specify the callbacks that will run on websockets disconnect.

        Paramaters
        ----------
        mode : Literal["before", "after"]
            The execution time of the callback - before / after disconnecting the websocket.

        Raises
        ------
        RuntimeError('The "mode" argument should be "before" or "after".')

        Returns
        -------
        Callable[[Room, WebSocket], None]
            The function that the decorator receives.
        """
        if mode not in ["before", "after"]:
            raise RuntimeError('The "mode" argument should be "before" or "after".')

        def inner(func: Callable[[Room, WebSocket], None]):
            self._on_disconnect[mode] = func
            return func

        return inner

    def __call__(self) -> Room:
        return self


async def await_if_awaitable(func_res: Any):
    if inspect.isawaitable(func_res):
        await func_res
