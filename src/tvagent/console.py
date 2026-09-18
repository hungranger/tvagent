"""Interactive console: browser control panel + TV render over one websocket.

Run:  python -m tvagent.console   (then open src/tvagent/web/console.html)

The ConsoleServer IS the Display adapter (implements render) plus the event
sink, command handler and listen-loop driver -- so the whole UI rides the same
ws://localhost:8765 the TV kiosk already uses. It talks JSON both ways:

  server -> browser : {"type":"render", person, text, card}
                      {"type":"event",  stage, ...}     (per turn stage)
                      {"type":"status", listening, threshold, margin, voice, people}
  browser -> server : {"cmd":"listen", "on":bool}
                      {"cmd":"tune", "threshold":float, "margin":float}
                      {"cmd":"voice", "name":str}
                      {"cmd":"enroll", "name":str}
                      {"cmd":"status"}
"""

import asyncio
import json
import threading
from typing import Any

from tvagent.core.models import RenderState
from tvagent.core.orchestrator import Orchestrator

_PORT = 8765
_ENROLL_SECONDS = 30


def _status(orch: Orchestrator) -> dict[str, Any]:
    speaker: Any = orch.speaker
    tts: Any = orch.tts
    return {
        "type": "status",
        "threshold": getattr(speaker, "threshold", None),
        "margin": getattr(speaker, "margin", None),
        "voice": getattr(tts, "voice", None),
        "people": [p.name for p in orch.memory.list_people()],
    }


def handle_command(orch: Orchestrator, msg: dict[str, Any]) -> dict[str, Any]:
    """Apply a control command that only touches the orchestrator's adapters.

    Returns the resulting status. Listen-toggle and enroll are hardware/loop
    concerns handled by ConsoleServer, not here.
    """
    cmd = msg.get("cmd")
    speaker: Any = orch.speaker
    if cmd == "tune":
        if "threshold" in msg:
            speaker.threshold = float(msg["threshold"])
        if "margin" in msg:
            speaker.margin = float(msg["margin"])
    elif cmd == "voice":
        tts: Any = orch.tts
        tts.set_voice(str(msg["name"]))
    return _status(orch)


class ConsoleServer:  # pragma: no cover - websocket/thread/mic IO glue, no CI coverage
    def __init__(self, port: int = _PORT) -> None:
        self.port = port
        self.orch: Orchestrator | None = None
        self._clients: set[Any] = set()
        self._listening = False
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._serve, daemon=True).start()

    # --- Display port -------------------------------------------------------
    def render(self, state: RenderState) -> None:
        self._broadcast(
            {"type": "render", "person": state.person, "text": state.text, "card": state.card}
        )

    # --- outbound -----------------------------------------------------------
    def _emit(self, stage: str, data: dict[str, object]) -> None:
        self._broadcast({"type": "event", "stage": stage, **data})

    def _broadcast(self, msg: dict[str, Any]) -> None:
        payload = json.dumps(msg)

        async def send_all() -> None:
            for ws in list(self._clients):
                try:
                    await ws.send(payload)
                except Exception:
                    self._clients.discard(ws)

        asyncio.run_coroutine_threadsafe(send_all(), self._loop)

    def _status_msg(self) -> dict[str, Any]:
        if self.orch is None:
            return {"type": "status", "listening": False, "people": []}
        return {**_status(self.orch), "listening": self._listening}

    # --- inbound ------------------------------------------------------------
    def _on_message(self, raw: str) -> None:
        if self.orch is None:
            return
        msg: dict[str, Any] = json.loads(raw)
        cmd = msg.get("cmd")
        if cmd == "listen":
            self._set_listening(bool(msg.get("on")))
        elif cmd == "enroll":
            self._enroll(str(msg["name"]))
        else:
            handle_command(self.orch, msg)
        self._broadcast(self._status_msg())

    def _set_listening(self, on: bool) -> None:
        if on and not self._listening:
            self._listening = True
            threading.Thread(target=self._listen_loop, daemon=True).start()
        else:
            self._listening = False  # loop checks the flag between turns

    def _listen_loop(self) -> None:
        assert self.orch is not None
        while self._listening:
            try:
                self.orch.run_once(on_event=self._emit)
            except Exception as exc:
                self._emit("error", {"message": str(exc)})

    def _enroll(self, name: str) -> None:
        assert self.orch is not None
        from tvagent.adapters.audio_vad import record_seconds  # noqa: PLC0415 -- lazy mic

        self._emit("enroll_start", {"name": name, "seconds": _ENROLL_SECONDS})
        clip = record_seconds(_ENROLL_SECONDS)
        person = self.orch.speaker.enroll(name, [clip])
        self._emit("enroll_done", {"name": person.name})

    # --- server -------------------------------------------------------------
    def _serve(self) -> None:
        import websockets  # noqa: PLC0415 -- lazy

        ws_lib: Any = websockets
        asyncio.set_event_loop(self._loop)

        async def handler(ws: Any) -> None:
            self._clients.add(ws)
            await ws.send(json.dumps(self._status_msg()))
            try:
                async for raw in ws:
                    self._on_message(raw)
            finally:
                self._clients.discard(ws)

        async def serve() -> None:
            async with ws_lib.serve(handler, "localhost", self.port):
                await asyncio.Future()

        self._loop.run_until_complete(serve())


def main() -> None:
    from tvagent.config import build_orchestrator  # noqa: PLC0415 -- lazy heavy deps

    server = ConsoleServer()
    server.orch = build_orchestrator({"display": server})
    print(f"Console up on ws://localhost:{_PORT} — open src/tvagent/web/console.html")
    threading.Event().wait()


if __name__ == "__main__":
    main()
