from typing import Any, ClassVar

from tvagent.adapters.llm_claude import ClaudeLLM


class _StubClient:
    def __init__(self) -> None:
        self.seen: dict[str, Any] = {}
        self.messages = _StubMessages(self)


class _StubMessages:
    def __init__(self, outer: _StubClient) -> None:
        self.outer = outer

    def create(self, **kwargs: Any) -> Any:
        self.outer.seen = kwargs

        class Block:
            type = "text"
            text = "hi Dad"

        class Msg:
            content: ClassVar = [Block()]

        return Msg()


def test_respond_extracts_text_and_sends_system():
    stub = _StubClient()
    llm = ClaudeLLM(client=stub)
    out = llm.respond("You are talking to Dad.", "hello", [])
    assert out == "hi Dad"
    assert stub.seen["model"] == "claude-opus-5"
    assert stub.seen["system"] == "You are talking to Dad."


def test_respond_includes_prior_turns_in_messages():
    stub = _StubClient()
    llm = ClaudeLLM(client=stub)
    llm.respond("sys", "next question", [("first question", "first answer")])
    assert stub.seen["messages"] == [
        {"role": "user", "content": "first question"},
        {"role": "assistant", "content": "first answer"},
        {"role": "user", "content": "next question"},
    ]


def test_respond_sends_max_tokens_and_output_config():
    stub = _StubClient()
    llm = ClaudeLLM(client=stub, max_tokens=77)
    llm.respond("sys", "hi", [])
    assert stub.seen["max_tokens"] == 77
    assert stub.seen["output_config"] == {"effort": "low"}


def test_respond_joins_only_text_blocks_in_order():
    class _Text:
        def __init__(self, text: str) -> None:
            self.type, self.text = "text", text

    class _NonText:
        type = "tool_use"
        text = "IGNORED"

    class _Msg:
        content: ClassVar = [_Text("hello "), _NonText(), _Text("world")]

    class _Messages:
        def create(self, **kwargs: Any) -> Any:
            return _Msg()

    class _Client:
        messages = _Messages()

    out = ClaudeLLM(client=_Client()).respond("sys", "hi", [])
    assert out == "hello world"
