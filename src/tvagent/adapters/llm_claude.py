class ClaudeLLM:
    def __init__(self, model: str = "claude-opus-5", client=None, max_tokens: int = 512):
        self.model, self.max_tokens = model, max_tokens
        if client is None:
            from anthropic import Anthropic
            client = Anthropic()
        self.client = client

    def respond(self, system: str, user: str, history: list[tuple[str, str]]) -> str:
        messages = []
        for said, replied in history:
            messages.append({"role": "user", "content": said})
            messages.append({"role": "assistant", "content": replied})
        messages.append({"role": "user", "content": user})
        msg = self.client.messages.create(
            model=self.model, max_tokens=self.max_tokens, system=system,
            output_config={"effort": "low"},  # voice latency knob
            messages=messages,
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text").strip()
