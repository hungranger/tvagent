from typing import Any

from tvagent.adapters.llm_openai import OpenAILLM


class _Msg:
    def __init__(self, content: str | None) -> None:
        self.message = type("M", (), {"content": content})()


def _delta_chunk(text: str | None) -> Any:
    return type(
        "Chunk", (), {"choices": [type("Ch", (), {"delta": type("D", (), {"content": text})()})()]}
    )()


class _StubClient:
    def __init__(self, content: str = "hello there") -> None:
        self.seen: dict[str, Any] = {}
        self._content = content
        outer = self

        class _Completions:
            def create(self, **kwargs: Any) -> Any:
                outer.seen = kwargs
                if kwargs.get("stream"):
                    # two deltas + a null delta (real servers send empty final chunks)
                    return iter([_delta_chunk("hello "), _delta_chunk("there"), _delta_chunk(None)])
                return type("R", (), {"choices": [_Msg(outer._content)]})()

        self.chat = type("C", (), {"completions": _Completions()})()


def test_respond_prepends_system_and_appends_history_then_user() -> None:
    stub = _StubClient()
    llm = OpenAILLM(model="llama3", client=stub)
    out = llm.respond("You are talking to Roy.", "next", [("q1", "a1")])
    assert out == "hello there"
    assert stub.seen["model"] == "llama3"
    assert stub.seen["messages"] == [
        {"role": "system", "content": "You are talking to Roy."},
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "next"},
    ]


def test_respond_handles_none_content() -> None:
    # OpenAI-compatible servers may return null content; must not crash.
    llm = OpenAILLM(client=_StubClient(content=None))  # type: ignore[arg-type]
    assert llm.respond("sys", "hi", []) == ""


def test_respond_sends_max_tokens() -> None:
    stub = _StubClient()
    OpenAILLM(client=stub, max_tokens=64).respond("sys", "hi", [])
    assert stub.seen["max_tokens"] == 64


def test_stream_yields_text_deltas_and_skips_empty() -> None:
    stub = _StubClient()
    out = list(OpenAILLM(client=stub).stream("sys", "hi", []))
    assert out == ["hello ", "there"]  # null final delta dropped
    assert stub.seen["stream"] is True
