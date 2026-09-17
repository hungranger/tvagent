import asyncio
import json
import threading
from typing import Any

from tvagent.core.models import RenderState


def state_to_json(state: RenderState) -> str:
    return json.dumps({"person": state.person, "text": state.text, "card": state.card})


class WebDisplay:
    def __init__(self, port: int = 8765) -> None:
        self.port = port
        self._clients: set[Any] = set()
        self._last = state_to_json(RenderState(person="", text="Listening…"))
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        import websockets  # noqa: PLC0415 -- lazy

        ws_lib: Any = websockets
        asyncio.set_event_loop(self._loop)

        async def handler(ws: Any) -> None:
            self._clients.add(ws)
            await ws.send(self._last)
            try:
                async for _ in ws:
                    pass
            finally:
                self._clients.discard(ws)

        async def main() -> None:
            async with ws_lib.serve(handler, "localhost", self.port):
                await asyncio.Future()

        self._loop.run_until_complete(main())

    def render(self, state: RenderState) -> None:
        self._last = state_to_json(state)

        async def broadcast() -> None:
            for ws in list(self._clients):
                try:
                    await ws.send(self._last)
                except Exception:
                    self._clients.discard(ws)

        asyncio.run_coroutine_threadsafe(broadcast(), self._loop)
