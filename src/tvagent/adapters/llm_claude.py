from collections.abc import Iterator
from typing import Any

_MODEL = "claude-opus-5"
_MAX_TOKENS = 512
_EFFORT = "low"  # voice latency knob


class ClaudeLLM:
    def __init__(
        self, model: str = _MODEL, client: Any = None, max_tokens: int = _MAX_TOKENS
    ) -> None:
        self.model, self.max_tokens = model, max_tokens
        if client is None:
            import anthropic  # noqa: PLC0415 -- lazy

            an: Any = anthropic
            client = an.Anthropic()
        self.client = client

    def _messages(self, user: str, history: list[tuple[str, str]]) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for said, replied in history:
            messages.append({"role": "user", "content": said})
            messages.append({"role": "assistant", "content": replied})
        messages.append({"role": "user", "content": user})
        return messages

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            output_config={"effort": _EFFORT},
            messages=self._messages(user, history),
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()

    def stream(self, system: str, user: str, history: list[tuple[str, str]]) -> Iterator[str]:
        with self.client.messages.stream(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            output_config={"effort": _EFFORT},
            messages=self._messages(user, history),
        ) as streamed:
            yield from streamed.text_stream
