from collections.abc import Iterator
from typing import Any

_DEFAULT_MODEL = "llama3.2"  # current 3B chat model: fast on-device, good enough for voice
_DEFAULT_BASE_URL = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint
_MAX_TOKENS = 512


class OpenAILLM:
    """Chat LLM over any OpenAI-compatible endpoint.

    One adapter, two homes: local Ollama (default base_url) for a private,
    offline, zero-cost brain, or a hosted endpoint like Cerebras
    (base_url="https://api.cerebras.ai/v1", api_key="csk-...", model="llama-3.3-70b")
    for very fast generation. Same port as ClaudeLLM.
    """

    def __init__(
        self,
        model: str = _DEFAULT_MODEL,
        base_url: str = _DEFAULT_BASE_URL,
        api_key: str | None = None,
        client: Any = None,
        max_tokens: int = _MAX_TOKENS,
    ) -> None:
        self.model, self.max_tokens = model, max_tokens
        if client is None:
            import openai  # noqa: PLC0415 -- lazy

            oa: Any = openai
            # Ollama ignores the key but the SDK requires a non-empty one.
            client = oa.OpenAI(base_url=base_url, api_key=api_key or "not-needed")
        self.client = client

    def _messages(
        self, system: str, user: str, history: list[tuple[str, str]]
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system}]
        for said, replied in history:
            messages.append({"role": "user", "content": said})
            messages.append({"role": "assistant", "content": replied})
        messages.append({"role": "user", "content": user})
        return messages

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=self._messages(system, user, history),
        )
        return (resp.choices[0].message.content or "").strip()

    def stream(self, system: str, user: str, history: list[tuple[str, str]]) -> Iterator[str]:
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=self._messages(system, user, history),
            stream=True,
        )
        for chunk in resp:
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta
