import pathlib


def test_no_noncommercial_weights() -> None:
    text = pathlib.Path("LICENSES.md").read_text()
    lowered = text.lower()
    nc_markers = ["-nc", "noncommercial", "non-commercial"]
    assert not any(marker in lowered for marker in nc_markers)
    for name in ["silero", "whisper", "piper", "ecapa", "openwakeword"]:
        assert name in lowered  # each active model is recorded
