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
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from tvagent.core.models import AudioClip, RenderState
from tvagent.core.orchestrator import Orchestrator

_PORT = 8765
_ENROLL_SECONDS = 30
_LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")


def _status(orch: Orchestrator) -> dict[str, Any]:
    speaker: Any = orch.speaker
    tts: Any = orch.tts
    return {
        "type": "status",
        "threshold": getattr(speaker, "threshold", None),
        "margin": getattr(speaker, "margin", None),
        "voice": getattr(tts, "voice", None),
        "wake": getattr(orch.wake, "model_name", None),
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


def run_enroll(
    orch: Orchestrator,
    name: str,
    record: Callable[[int], AudioClip],
    emit: Callable[[str, dict[str, object]], None],
) -> None:
    """Record a voice sample and register it, surfacing any mic error to the UI.

    Blocking (records for _ENROLL_SECONDS); the server runs it off its event loop
    on a worker thread. Errors are emitted, never swallowed.
    """
    try:
        emit("enroll_start", {"name": name, "seconds": _ENROLL_SECONDS})
        clip = record(_ENROLL_SECONDS)
        person = orch.speaker.enroll(name, [clip])
        emit("enroll_done", {"name": person.name})
    except Exception as exc:
        emit("error", {"message": f"enroll failed: {exc}"})


def origin_allowed(origin: str | None) -> bool:
    """Reject cross-site WebSocket hijacking: only same-machine callers.

    Residual: file:// pages send Origin "null", which must be allowed for the
    kiosk/console-opened-as-a-file case -- so any LOCAL file page can also
    connect. Closing that would need a token, out of scope for the no-auth POC.
    """
    if origin is None or origin == "null":
        return True
    return urlparse(origin).hostname in _LOCAL_HOSTS


class ListenLoop:
    """Background listen thread with idempotent on/off toggling and never more
    than one live worker thread.

    Stop takes effect after the in-flight turn returns: a real turn blocks in
    wake.wait() on the mic until a wake word fires, so a stop mid-wait is
    honored only once the current wake resolves (openWakeWord has no cancel).
    """

    def __init__(self, run_turn: Callable[[], None]) -> None:
        self._run_turn = run_turn
        self._on = False
        self._thread: threading.Thread | None = None

    @property
    def listening(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        if on == self._on:
            return  # idempotent: no double-start, no spurious stop
        self._on = on
        if on and (self._thread is None or not self._thread.is_alive()):
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def _loop(self) -> None:
        while self._on:
            self._run_turn()


class ConsoleServer:  # pragma: no cover - websocket/thread/mic IO glue, no CI coverage
    def __init__(self, port: int = _PORT) -> None:
        self.port = port
        self.orch: Orchestrator | None = None
        self._clients: set[Any] = set()
        self._listen = ListenLoop(self._run_turn)
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
        return {**_status(self.orch), "listening": self._listen.listening}

    # --- inbound ------------------------------------------------------------
    def _on_message(self, raw: str) -> None:
        if self.orch is None:
            return
        msg: dict[str, Any] = json.loads(raw)
        cmd = msg.get("cmd")
        if cmd == "listen":
            self._listen.set(bool(msg.get("on")))
        elif cmd == "enroll":
            self._enroll(str(msg["name"]))
        else:
            handle_command(self.orch, msg)
        self._broadcast(self._status_msg())

    def _run_turn(self) -> None:
        if self.orch is None:
            return
        try:
            self.orch.run_once(on_event=self._emit)
        except Exception as exc:
            self._emit("error", {"message": str(exc)})

    def _enroll(self, name: str) -> None:
        # The listen loop holds the mic while waiting for a wake word, so enrolling
        # then would fight it for the input device. Require listening off.
        if self._listen.listening:
            self._emit("error", {"message": "Stop listening first, then enroll (mic is in use)."})
            return

        # Record + embed on a worker thread so the 30s capture doesn't freeze the
        # websocket event loop (which would swallow the enroll_start feedback).
        def worker() -> None:
            from tvagent.adapters.audio_vad import record_seconds  # noqa: PLC0415 -- lazy mic

            assert self.orch is not None
            run_enroll(self.orch, name, record_seconds, self._emit)
            self._broadcast(self._status_msg())

        threading.Thread(target=worker, daemon=True).start()

    # --- server -------------------------------------------------------------
    def _serve(self) -> None:
        import websockets  # noqa: PLC0415 -- lazy

        ws_lib: Any = websockets
        asyncio.set_event_loop(self._loop)

        async def handler(ws: Any) -> None:
            req = getattr(ws, "request", None)
            origin = req.headers.get("Origin") if req is not None else None
            if not origin_allowed(origin):
                await ws.close(code=1008, reason="origin not allowed")
                return
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
