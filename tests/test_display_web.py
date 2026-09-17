import json

from tvagent.adapters.display_web import state_to_json
from tvagent.core.models import RenderState


def test_state_to_json_shape():
    s = RenderState(person="Dad", text="hi", card={"kind": "weather"})
    out = json.loads(state_to_json(s))
    assert out == {"person": "Dad", "text": "hi", "card": {"kind": "weather"}}


def test_state_to_json_null_card():
    out = json.loads(state_to_json(RenderState(person="Guest", text="hello")))
    assert out["card"] is None
