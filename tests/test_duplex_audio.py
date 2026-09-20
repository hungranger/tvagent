from typing import Any

import numpy

from tvagent.audio import DuplexAudio

np: Any = numpy


def _no_stream(_cb: Any) -> None:
    return None  # test seam: DuplexAudio without opening a real device


def test_callback_outputs_far_and_captures_near_aligned() -> None:
    # One full-duplex callback must, for the SAME block: play the queued far,
    # expose that far on the far FIFO, and capture the mic (near) on the near
    # queue -- so near[t] and far[t] share one clock (the fix for the AEC drift).
    dux = DuplexAudio(rate=48000, _stream_factory=_no_stream)
    far_in = np.arange(1, 5, dtype=np.int16)  # 4 samples the assistant plays
    dux.enqueue(far_in.tobytes())
    near_in = np.array([10, 20, 30, 40], dtype=np.int16)  # what the mic hears
    outdata = np.zeros((4, 1), dtype=np.int16)
    dux._callback(near_in.reshape(-1, 1), outdata, 4, None, None)  # pyright: ignore[reportPrivateUsage]

    assert np.array_equal(outdata[:, 0], far_in)  # played the queued far
    near_frame, is_speech = next(dux.frames())  # near captured, source-compatible
    assert near_frame == near_in.tobytes()
    assert is_speech is False
    assert dux.far.read(8) == far_in.tobytes()  # far exposed, same block => aligned


def test_callback_zero_pads_when_queue_empty() -> None:
    # No far queued (assistant silent) => output silence, far FIFO gets silence.
    dux = DuplexAudio(rate=48000, _stream_factory=_no_stream)
    outdata = np.ones((4, 1), dtype=np.int16)
    dux._callback(np.zeros((4, 1), dtype=np.int16), outdata, 4, None, None)  # pyright: ignore[reportPrivateUsage]
    assert np.array_equal(outdata[:, 0], np.zeros(4, dtype=np.int16))
    assert dux.far.read(8) == b"\x00" * 8
