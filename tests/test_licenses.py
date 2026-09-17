import pathlib


def test_no_noncommercial_weights() -> None:
    text = pathlib.Path("LICENSES.md").read_text()
    lines = text.split("\n")

    # Extract active model table rows (lines starting with "|" that aren't headers)
    table_rows = [line for line in lines if line.startswith("|") and "Component" not in line]

    # Assert no active model row contains NC markers
    nc_markers = ["-nc", "noncommercial", "non-commercial"]
    for row in table_rows:
        lowered_row = row.lower()
        assert not any(marker in lowered_row for marker in nc_markers), (
            f"Active model row contains NC marker: {row}"
        )

    # Assert each active model is recorded in the table
    for name in ["silero", "whisper", "piper", "ecapa", "openwakeword"]:
        assert name in text.lower(), f"Model {name} not recorded in table"

    # Assert the file warns against NC weights (guard proves warning exists)
    lowered_text = text.lower()
    assert "do not add" in lowered_text, "File must warn against adding NC models"
    assert any(marker in lowered_text for marker in nc_markers), (
        "File must mention NC licenses in warning"
    )
