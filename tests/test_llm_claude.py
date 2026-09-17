from tvagent.adapters.llm_claude import ClaudeLLM


class _StubMessages:
    def __init__(self, outer): self.outer = outer
    def create(self, **kwargs):
        self.outer.seen = kwargs
        class Block: type = "text"; text = "hi Dad"
        class Msg: content = [Block()]
        return Msg()


class _StubClient:
    def __init__(self): self.messages = _StubMessages(self)


def test_respond_extracts_text_and_sends_system():
    stub = _StubClient()
    llm = ClaudeLLM(client=stub)
    out = llm.respond("You are talking to Dad.", "hello", [])
    assert out == "hi Dad"
    assert stub.seen["model"] == "claude-opus-5"
    assert stub.seen["system"] == "You are talking to Dad."
