from tvagent.audio import PlaybackReference


def test_reads_fifo_then_zero_pads_when_drained() -> None:
    # The AEC far-end: what the assistant just played. Reads consume in order and,
    # when nothing is buffered (silence between/after playback), return zeros so a
    # frame is always the requested size.
    ref = PlaybackReference()
    ref.write(b"\x01\x02\x03\x04")
    assert ref.read(2) == b"\x01\x02"  # FIFO
    assert ref.read(4) == b"\x03\x04\x00\x00"  # remainder + zero pad to size
    assert ref.read(2) == b"\x00\x00"  # empty -> far-end silence


def test_clear_drops_buffered_audio() -> None:
    ref = PlaybackReference()
    ref.write(b"\xaa\xbb")
    ref.clear()
    assert ref.read(2) == b"\x00\x00"  # cleared -> silence, not stale audio
