import shutil
import subprocess

import pytest

from worker.ingest.ffmpeg_source import FFmpegSource, _parse_rate, probe
from worker.ingest.source import SourceError

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


@pytest.fixture
def clip(tmp_path):
    path = tmp_path / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25", "-t", "1.2",
         "-pix_fmt", "yuv420p", str(path)],
        check=True,
    )  # fmt: skip
    return path


def test_probe_reads_resolution_and_fps(clip):
    info = probe(str(clip), 10, is_file=True)
    assert (info.width, info.height) == (320, 240)
    assert info.fps == pytest.approx(25)


def test_file_source_samples_to_processing_fps(clip, settings):
    source = FFmpegSource(str(clip), fps=10, is_live=False, settings=settings)
    frames = list(source)

    assert 11 <= len(frames) <= 13
    assert frames[0].image.shape == (240, 320, 3)
    assert frames[5].video_ts == pytest.approx(0.5)


def test_corrupt_file_raises_clear_error(tmp_path, settings):
    bad = tmp_path / "bad.mp4"
    bad.write_bytes(b"\x00not a video" * 100)
    with pytest.raises(SourceError, match="cannot open video source|no decodable"):
        FFmpegSource(str(bad), fps=10, is_live=False, settings=settings)


def test_parse_rate():
    assert _parse_rate("30000/1001") == pytest.approx(29.97)
    assert _parse_rate("0/0") is None
    assert _parse_rate(None) is None


def test_private_stream_hosts_are_refused(settings):
    with pytest.raises(SourceError, match="non-public"):
        FFmpegSource("http://127.0.0.1:8000/live.m3u8", fps=10, is_live=True, settings=settings)


def test_network_protocols_cannot_read_local_files(clip):
    with pytest.raises(SourceError):
        probe(f"file:{clip}", 5, is_file=False)
