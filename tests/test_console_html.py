from pathlib import Path

_HTML = (
    Path(__file__).resolve().parent.parent / "src" / "tvagent" / "web" / "console.html"
).read_text()


def test_console_html_never_uses_innerhtml() -> None:
    # XSS guard (CSWSH sibling): the live log renders untrusted event fields
    # (m.name, m.said, m.reply, m.message). They must reach the DOM as text
    # nodes, never through innerHTML -- otherwise spoken text or an LLM reply
    # containing markup executes in the page. Full DOM building means innerHTML
    # is absent entirely, which is the invariant this asserts.
    assert "innerHTML" not in _HTML
