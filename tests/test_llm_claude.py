from typing import Any, ClassVar

from tvagent.adapters.llm_claude import ClaudeLLM


class _StubClient:
    def __init__(self) -> None:
        self.seen: dict[str, Any] = {}
        self.messages = _StubMessages(self)


class _StubMessages:
    def __init__(self, outer: _StubClient) -> None: self.outer = outer
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
