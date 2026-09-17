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

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        messages: list[dict[str, str]] = []
        for said, replied in history:
            messages.append({"role": "user", "content": said})
            messages.append({"role": "assistant", "content": replied})
        messages.append({"role": "user", "content": user})
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            output_config={"effort": _EFFORT},
            messages=messages,
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
